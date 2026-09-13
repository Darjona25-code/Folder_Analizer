"""Phase 5 — I10 integration: item-level authority vs folder-level recommendation.

Canonical contract: deletion is authorized at ITEM level via
``security_guard.validate_delete_target``. A disposable (SAFE_TO_DELETE / HIGH)
file must remain deletable even when its parent folder derives a
REVIEW_FIRST recommendation from non-safe sibling bytes.
"""

import os

from folder_analyzer.scanner import Scanner
from folder_analyzer.engine.classifier import classify_path
from folder_analyzer.engine.enums import DeletionRecommendation
from folder_analyzer.security_guard import validate_delete_target


def test_item_safe_file_remains_deletable_beneath_review_folder(
    scan_sandbox,
):
    root = str(scan_sandbox)
    cache_dir = os.path.join(root, "Chrome", "Cache")
    os.makedirs(cache_dir)

    # A disposable cache blob inside a Chrome-style layout -> SAFE_TO_DELETE/HIGH.
    safe_item = os.path.join(cache_dir, "f_0001")
    with open(safe_item, "w") as f:
        f.write("x" * 200)

    # Non-safe sibling (user value) makes the folder derive REVIEW_FIRST.
    doc = os.path.join(root, "report.docx")
    with open(doc, "w") as f:
        f.write("important")

    scanner = Scanner(max_workers=1)
    scanner.scan(root)

    result = scanner.scan_result()
    root_agg = result.per_folder[os.path.normpath(root)]

    # Folder-level assessment is gated by the USER_VALUE sibling, not by the
    # disposable blob -> the folder as a whole is NOT safe to delete.
    assert root_agg.assessment is not None
    assert root_agg.assessment.recommendation is DeletionRecommendation.REVIEW_FIRST
    assert root_agg.assessment.reason_key == "r2_user_value"
    # Byte composition is exhaustive over the folder's own analyzed files:
    # 9 bytes of user value vs 0 disposable at the root's direct level.
    assert root_agg.composition.user_value_bytes == 9
    assert root_agg.composition.disposable_bytes == 0
    assert root_agg.total_descendant_size == 209  # subdir bytes still counted

    # The item itself classifies SAFE_TO_DELETE / HIGH by its own evidence.
    entry = classify_path(safe_item)
    assert entry.recommendation is DeletionRecommendation.SAFE_TO_DELETE
    assert entry.confidence == "high"

    # And the security guard authorizes exactly that item for deletion.
    verdict = validate_delete_target(safe_item, scan_root=root)
    assert verdict.ok