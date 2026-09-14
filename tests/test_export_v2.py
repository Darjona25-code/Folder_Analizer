"""Phase 6 tests: v2 enriched, deterministic, zero-reclassification exports.

The v2 export functions must:
- consume ONLY the ScanResult captured at scan time (no re-scan, no
  re-classification, no knowledge-base/classifier access);
- enrich the v1 report with assessment + composition data;
- serialize each node's composition as its FULL RECURSIVE aggregation across
  the whole subtree (own direct bytes + every descendant), equal to the
  direction FolderAggregation.total_descendant_size;
- localize every producible reason_key in the actual CSV/HTML row output;
- be byte-identical for identical input (canonical ordering + injectable
  scan_date);
- keep the v1 export functions intact for backward compatibility.
"""

import csv
import hashlib
import html
import inspect
import json
import os
import re
import tempfile
from unittest import mock

import pytest

import folder_analyzer.exporter as exporter
from folder_analyzer.engine import classifier
from folder_analyzer.engine import explain
from folder_analyzer.engine import kb
from folder_analyzer.engine import recommender
from folder_analyzer.engine.models import (
    Assessment,
    ConfidenceLevel,
    DeletionRecommendation,
    FolderAggregation,
    FolderComposition,
    ScanResult,
    SystemImpact,
)
from folder_analyzer.scanner import FolderInfo, Scanner
from folder_analyzer.i18n import I18n

_FIXED_SCAN_DATE = "2026-01-01T00:00:00"


@pytest.fixture
def sandbox():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "sub1"))
        os.makedirs(os.path.join(tmpdir, "sub2"))
        os.makedirs(os.path.join(tmpdir, "cache"))
        for name in ["file1.txt", "file2.txt"]:
            with open(os.path.join(tmpdir, name), "w") as f:
                f.write("x" * 1000)
        with open(os.path.join(tmpdir, "sub1", "file3.txt"), "w") as f:
            f.write("y" * 500)
        with open(os.path.join(tmpdir, "sub2", "file4.tmp"), "w") as f:
            f.write("z" * 2000)
        with open(os.path.join(tmpdir, "cache", "tmp.bin"), "w") as f:
            f.write("w" * 3000)
        yield tmpdir


def _scan(tmpdir):
    scanner = Scanner(max_workers=16)
    root = scanner.scan(tmpdir)
    return root, scanner.scan_result(), scanner


def _digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _assert_nodes_canonically_sorted(node):
    children = node.get("children", [])
    paths = [c["path"] for c in children]
    assert paths == sorted(paths, key=os.path.normpath)
    for child in children:
        _assert_nodes_canonically_sorted(child)


@pytest.mark.parametrize(
    ("fmt", "fn"),
    [
        ("json", exporter.export_json_v2),
        ("csv", exporter.export_csv_v2),
        ("html", exporter.export_html_v2),
    ],
)
def test_byte_identical_determinism(sandbox, fmt, fn):
    root, scan_result, _ = _scan(sandbox)
    out1 = os.path.join(sandbox, f"a.{fmt}")
    out2 = os.path.join(sandbox, f"b.{fmt}")
    fn(root, I18n("en"), out1, scan_result, scan_date=_FIXED_SCAN_DATE)
    fn(root, I18n("en"), out2, scan_result, scan_date=_FIXED_SCAN_DATE)
    assert _digest(out1) == _digest(out2)
    assert os.path.getsize(out1) > 0


def test_json_v2_schema_and_enrichment(sandbox):
    root, scan_result, _ = _scan(sandbox)
    out = os.path.join(sandbox, "report.json")
    exporter.export_json_v2(root, I18n("en"), out, scan_result, scan_date=_FIXED_SCAN_DATE)

    with open(out, encoding="utf-8") as f:
        data = json.load(f)

    assert data["schema_version"] == 2
    assert data["scan_date"] == _FIXED_SCAN_DATE
    assert data["root_path"] == os.path.normpath(sandbox)
    assert data["total_size"] == root.total_size
    assert data["total_files"] == root.file_count
    assert data["total_folders"] == root.folder_count
    assert data["files_analyzed"] == scan_result.files_analyzed
    assert data["records_retained"] == scan_result.records_retained
    assert data["inaccessible_count"] == scan_result.inaccessible_count
    assert isinstance(data["folder_errors"], list)
    assert isinstance(data["root_assessment"], dict)
    assert isinstance(data["root_composition"], dict)
    assert isinstance(data["tree"], dict)

    comp = data["root_composition"]
    assert (
        comp["disposable_bytes"]
        + comp["user_value_bytes"]
        + comp["protected_critical_bytes"]
        + comp["known_non_disposable_bytes"]
        + comp["unknown_bytes"]
        == comp["total_bytes"]
    )
    for key in (
        "total_bytes", "disposable_bytes", "user_value_bytes",
        "protected_critical_bytes", "known_non_disposable_bytes",
        "unknown_bytes", "not_resolvable_count", "by_category",
    ):
        assert key in comp

    assessment = data["tree"]["assessment"]
    assert assessment["recommendation"] in ("safe_to_delete", "review_first", "do_not_delete")
    assert assessment["confidence"] in ("high", "medium", "low")
    assert assessment["impact"] in ("none", "low", "moderate", "high", "critical", "unknown")
    assert isinstance(assessment["reason_key"], str)

    tree = data["tree"]
    assert tree["analysis_state"] == "analyzed"
    assert tree["files_analyzed"] == 2
    assert tree["records_retained"] == 2

    def _sum_analyzed(node):
        return node["files_analyzed"] + sum(_sum_analyzed(c) for c in node["children"])

    assert _sum_analyzed(tree) == scan_result.files_analyzed
    _assert_nodes_canonically_sorted(tree)


def test_composition_recursive_across_levels(sandbox):
    """Verification point 1: each node's composition is the FULL recursion —
    own direct bytes plus every descendant's — not the direct set only."""
    root, scan_result, _ = _scan(sandbox)
    out = os.path.join(sandbox, "report.json")
    exporter.export_json_v2(root, I18n("en"), out, scan_result, scan_date=_FIXED_SCAN_DATE)
    with open(out, encoding="utf-8") as f:
        data = json.load(f)

    comp = data["root_composition"]
    assert comp["total_bytes"] == data["total_size"] == root.total_size
    # The pre-fix defect: root_composition carried only the root's DIRECT bytes
    # (2 direct files, 2000 B) while the subtree held 7500 B.
    assert comp["total_bytes"] > root.direct_size
    assert comp["total_bytes"] == scan_result.total_descendant_size
    assert (
        comp["disposable_bytes"]
        + comp["user_value_bytes"]
        + comp["protected_critical_bytes"]
        + comp["known_non_disposable_bytes"]
        + comp["unknown_bytes"]
        == comp["total_bytes"]
    )

    # Each file belongs to exactly one folder's DIRECT set, so the root folder's
    # recursive composition equals the sum over ALL per-folder compositions.
    total_direct = 0
    by_category = {}
    for agg in scan_result.per_folder.values():
        if agg.composition is None:
            continue
        c = agg.composition
        total_direct += c.total_bytes
        for category, size in c.by_category.items():
            by_category[category] = by_category.get(category, 0) + size
    assert comp["total_bytes"] == total_direct
    assert comp["by_category"] == dict(sorted(by_category.items()))

    # Per-node tree composition == the subtree sum (node + descendants).
    tree_comps = {}

    def _collect(node):
        tree_comps[os.path.normpath(node["path"])] = node["composition"]
        for child in node["children"]:
            _collect(child)

    _collect(data["tree"])
    full = scan_result.per_folder
    for path, node_comp in tree_comps.items():
        subtree = sum(
            agg.composition.total_bytes
            for norm, agg in full.items()
            if agg.composition is not None
            and (norm == path or norm.startswith(path + os.sep))
        )
        assert node_comp["total_bytes"] == subtree

    # Leaf folders (no descendants) report exactly their own direct bytes.
    leaf_dirs = [
        norm
        for norm in full
        if not any(other.startswith(norm + os.sep) for other in full)
    ]
    for norm in leaf_dirs:
        assert tree_comps[norm]["total_bytes"] == full[norm].composition.total_bytes


def test_json_v2_is_language_neutral(sandbox):
    root, scan_result, _ = _scan(sandbox)
    out = os.path.join(sandbox, "report.json")
    exporter.export_json_v2(root, I18n("es"), out, scan_result, scan_date=_FIXED_SCAN_DATE)
    with open(out, encoding="utf-8") as f:
        data = json.load(f)
    assert data["tree"]["assessment"]["reason_key"] is not None
    assert "schema_version" in data


def test_files_analyzed_full_coverage(sandbox):
    root, scan_result, _ = _scan(sandbox)
    assert scan_result.files_analyzed == root.file_count
    assert scan_result.files_analyzed == 5


def test_csv_v2_headers_rows_sorted_and_reason_localized(sandbox):
    root, scan_result, _ = _scan(sandbox)
    out = os.path.join(sandbox, "report.csv")
    exporter.export_csv_v2(root, I18n("en"), out, scan_result, scan_date=_FIXED_SCAN_DATE)

    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    header = rows[0]
    assert header[0] == "Folder"
    assert "Recommendation" in header
    assert "Confidence" in header
    assert "Impact" in header
    assert "Reason" in header
    assert "Analysis State" in header
    assert "Files Analyzed" in header
    assert "Records Retained" in header

    body = rows[1:]
    assert body
    paths = [os.path.normpath(r[0]) for r in body]
    assert os.path.normpath(sandbox) not in paths
    sizes = [int(r[1]) for r in body]
    assert sizes == sorted(sizes, reverse=True)
    for a, b in zip(body, body[1:]):
        if int(a[1]) == int(b[1]):
            assert os.path.normpath(a[0]) <= os.path.normpath(b[0])
    for row in body:
        assert row[6] in ("safe_to_delete", "review_first", "do_not_delete")
        assert row[7] in ("high", "medium", "low")
        assert row[8] in ("none", "low", "moderate", "high", "critical", "unknown")
        assert row[9].strip() != ""
        assert row[10] == "analyzed"
        assert int(row[11]) >= 0
        assert int(row[12]) >= 0


def test_csv_v2_es_headers_localized(sandbox):
    root, scan_result, _ = _scan(sandbox)
    out = os.path.join(sandbox, "report.csv")
    exporter.export_csv_v2(root, I18n("es"), out, scan_result, scan_date=_FIXED_SCAN_DATE)
    with open(out, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert "Carpeta" in header
    assert "Recomendacion" in header
    assert "Confianza" in header
    assert "Impacto" in header
    assert "Motivo" in header
    assert "Registros conservados" in header


def test_html_v2_columns_and_es_localization(sandbox):
    root, scan_result, _ = _scan(sandbox)
    out = os.path.join(sandbox, "report.html")
    exporter.export_html_v2(root, I18n("es"), out, scan_result, scan_date=_FIXED_SCAN_DATE)
    with open(out, encoding="utf-8") as f:
        text = f.read()
    assert "Analizador de Carpetas" in text
    assert "Recomendacion" in text
    assert "Confianza" in text
    assert "Impacto" in text
    assert "Motivo" in text
    assert "Estado de analisis" in text
    assert "Registros conservados" in text
    assert "analyzed" in text


def test_v1_exporters_preserved(sandbox):
    root, scan_result, _ = _scan(sandbox)
    out = os.path.join(sandbox, "v1.json")
    exporter.export_json(root, I18n("en"), out)
    with open(out, encoding="utf-8") as f:
        data = json.load(f)
    assert "tree" in data
    assert "scan_date" in data
    assert "schema_version" not in data


def _export_module_holds_classifier_or_kb_refs() -> bool:
    forbidden = ("folder_analyzer.engine.kb", "folder_analyzer.engine.classifier")
    for name, obj in vars(exporter).items():
        if callable(obj) and getattr(obj, "__module__", "").startswith(forbidden):
            return True
    return False


def test_zero_classification_during_export(sandbox):
    """Verification point 2: scan_result() is a pure fold over tallies and the
    tree — it is exercised here UNDER the patchers and must make zero
    classifier/KB calls, exactly like the export calls themselves."""
    root, scan_result, scanner = _scan(sandbox)
    assert not _export_module_holds_classifier_or_kb_refs()

    targets = [
        (kb, "classify"),
        (kb, "prepare_scan_folder"),
        (kb, "classify_scan_path"),
        (kb, "classify_content"),
        (classifier, "classify_path"),
        (classifier, "classify_scan"),
        (classifier, "classify_entry"),
        (classifier, "assessment_from_scan_record"),
    ]
    patchers = [mock.patch.object(mod, name, wraps=getattr(mod, name)) for mod, name in targets]
    mocks = [p.start() for p in patchers]

    try:
        re_fold = scanner.scan_result()
        assert re_fold.files_analyzed == scan_result.files_analyzed
        for name, fn in (
            ("a.json", exporter.export_json_v2),
            ("b.csv", exporter.export_csv_v2),
            ("c.html", exporter.export_html_v2),
        ):
            fn(root, I18n("en"), os.path.join(sandbox, name), scan_result, scan_date=_FIXED_SCAN_DATE)
        for m in mocks:
            assert m.call_count == 0, f"classifier/kb call during export: {m._extract_mock_name()}"
    finally:
        for p in patchers:
            p.stop()


# ---------------------------------------------------------------------------
# Verification point 3 — reason_key localization through ACTUAL CSV/HTML rows.
# ---------------------------------------------------------------------------


def _assessment_for_reason(key: str) -> Assessment:
    """An Assessment carrying *key* that survives the constructor's I9/I3/I7
    demotion (REVIEW_FIRST for every key; r5_safe_to_delete legitimately stays
    SAFE_TO_DELETE with HIGH confidence and non-UNKNOWN, non-user impact)."""
    params = {
        "confidence_gate_promoted": {"confidence": "High"},
        "r3_unknown": {"unknown_share": 0.05},
        "r4_known_non_disposable_share": {"known_share": 0.20, "review_share": 0.15},
        "r5_safe_to_delete": {
            "disposable_share": 0.95,
            "safe_min_share": 0.85,
            "known_non_disposable_ceiling": 0.10,
        },
    }
    recommendation = (
        DeletionRecommendation.SAFE_TO_DELETE
        if key == "r5_safe_to_delete"
        else DeletionRecommendation.REVIEW_FIRST
    )
    return Assessment(
        impact=SystemImpact.NONE,
        confidence=ConfidenceLevel.HIGH,
        reason_key=key,
        recommendation=recommendation,
        reason_params=params.get(key),
    )


@pytest.fixture
def reason_key_scan(tmpdir):
    """One subtree node per registered reason_key, each a real export row."""
    keys = sorted(explain.REASONS["en"])
    root = FolderInfo(path=os.path.normpath(str(tmpdir)), name=os.path.basename(str(tmpdir)))
    per_folder = {}
    for key in keys:
        node_path = os.path.join(str(tmpdir), "node_" + key)
        root.children.append(
            FolderInfo(path=node_path, name="node_" + key, total_size=1024,
                       file_count=1, folder_count=0, direct_size=1024)
        )
        per_folder[os.path.normpath(node_path)] = FolderAggregation(
            files_analyzed=1,
            records_retained=1,
            composition=FolderComposition(
                total_bytes=1024, disposable_bytes=1024, by_category={"test": 1024}
            ),
            assessment=_assessment_for_reason(key),
        )
    root.total_size = 1024 * len(keys)
    root.file_count = root.folder_count = len(keys)
    scan_result = ScanResult(
        root_path=root.path,
        files_analyzed=len(keys),
        records_retained=len(keys),
        per_folder=per_folder,
    )
    return root, scan_result


def test_every_registered_reason_key_localizes_in_actual_csv_rows(reason_key_scan, tmpdir):
    root, scan_result = reason_key_scan
    for lang in ("en", "es"):
        out = os.path.join(str(tmpdir), f"reasons_{lang}.csv")
        exporter.export_csv_v2(root, I18n(lang), out, scan_result, scan_date=_FIXED_SCAN_DATE)
        with open(out, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        reason_cells = {os.path.normpath(r[0]): r[9] for r in rows[1:]}
        for key in explain.REASONS["en"]:
            params = _assessment_for_reason(key).reason_params
            cell = reason_cells[os.path.normpath(os.path.join(str(tmpdir), "node_" + key))]
            expected = explain.resolve_reason(key, lang=lang, params=params)
            assert cell == expected
            assert cell.strip()  # non-empty
            assert cell != key  # resolved, not raw-key fallback
            assert "{" not in cell  # params interpolated, no raw braces


def test_every_registered_reason_key_localizes_in_actual_html_rows(reason_key_scan, tmpdir):
    root, scan_result = reason_key_scan
    for lang in ("en", "es"):
        out = os.path.join(str(tmpdir), f"reasons_{lang}.html")
        exporter.export_html_v2(root, I18n(lang), out, scan_result, scan_date=_FIXED_SCAN_DATE)
        with open(out, encoding="utf-8") as f:
            text = f.read()
        reason_cells = set(re.findall(r'<td class="reason">(.*?)</td>', text))
        expected = {
            html.escape(explain.resolve_reason(key, lang=lang,
                                               params=_assessment_for_reason(key).reason_params))
            for key in explain.REASONS["en"]
        }
        assert reason_cells == expected
        assert all(cell != "<reason_key>" for cell in reason_cells)


def test_item_demotion_reason_keys_are_exactly_the_model_keys():
    """The Assessment constructor's I9/I3/I7 demotion produces exactly
    {confidence_gate_promoted, user_data, uncertain} and each resolves."""
    produced = {
        "low_confidence": Assessment(
            impact=SystemImpact.NONE, confidence=ConfidenceLevel.LOW,
            reason_key="anything", recommendation=DeletionRecommendation.SAFE_TO_DELETE,
        ).reason_key,
        "user_data": Assessment(
            impact=SystemImpact.NONE, confidence=ConfidenceLevel.HIGH,
            reason_key="anything", recommendation=DeletionRecommendation.SAFE_TO_DELETE,
            is_user_data=True,
        ).reason_key,
        "unknown_impact": Assessment(
            impact=SystemImpact.UNKNOWN, confidence=ConfidenceLevel.HIGH,
            reason_key="anything", recommendation=DeletionRecommendation.SAFE_TO_DELETE,
        ).reason_key,
    }
    assert set(produced.values()) == {"confidence_gate_promoted", "user_data", "uncertain"}
    for key in produced.values():
        for lang in ("en", "es"):
            text = explain.resolve_reason(key, lang=lang)
            assert text != key and text.strip()


def test_every_producible_reason_key_is_registered():
    """Audit: every reason the current producers can emit must resolve through
    REASONS — no raw reason_key can ever leak into an exported row."""
    folder_keys = set(re.findall(
        r'reason_key="([a-z0-9_]+)"', inspect.getsource(recommender)))
    assert folder_keys
    bucket_keys = set(classifier._REASON_BY_BUCKET.values()) | {"not_resolvable"}
    item_keys = {"user_data", "uncertain", "confidence_gate_promoted"}
    producible = folder_keys | bucket_keys | item_keys
    registered = set(explain.REASONS["en"])
    assert registered == set(explain.REASONS["es"])
    missing = producible - registered
    assert not missing, f"unregistered producible reason_keys: {sorted(missing)}"