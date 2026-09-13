# Folder Analyzer — Safety Model & Deletion Security

Status: **Phase 5 — Recommendation Engine + Folder Composition wired into the scan.**
The three-axis safety model (enums, `Assessment`, construction-time confidence
gate, explainability) is implemented in Phase 2 and documented in §6. Phase 3
adds per-file metadata + bounded retention (Level-1 analysis only). Phase 4
adds the Knowledge Base (`folder_analyzer/engine/kb/`): tiered **path**
classification plus **bounded Level 2/3 content** detection, exposed as
`KBResult` objects. Phase 5 wires it in: every scanned file is classified
through the KB and carried into an `Assessment`/`ScanAssessment`, per-folder
`CompositionBucket`s (byte shares sum to 100% of descendant bytes) drive
`derive_folder_recommendation` (roadmap §11 short-circuits), and
`ScanResult`/`FileEntry`/`FolderAggregation` expose live assessments and
recommendations. Item-level authority is preserved (I10): a validated
`SAFE_TO_DELETE`+`HIGH` item beneath a folder-derived `REVIEW_FIRST` remains
deletable — the folder recommendation gates only the folder-as-a-whole action.
The KB never fabricates `Assessment`s (failed/content analysis stays
`NOT_RESOLVABLE` and aggregates to `UNKNOWN`).

---

## 1. Scope of this document

This document is the formal reference for everything security-relevant in Folder
Analyzer. It is written to be honest about guarantees and limitations, never to
overclaim.

## 2. Deletion Security Model (Phase 1 — implemented)

**Deletion Security = Containment security + Protected-path policy + Deletion
authorization + Deletion operation.** These are related but distinct concepts, and must
be treated as such.

### 2.1 Six-condition deletion guard

1. **Valid path input** — non-empty, correct type, no NUL bytes, adversarially-formatted
   input rejected.
2. **Safe canonicalization** — per-component `realpath` + `normcase` over a single
   canonical reference form (identity comparison).
3. **Containment** — canonical target is a descendant of the canonical active scan root,
   checked by path-component boundary logic (never a raw string prefix).
4. **Root protection** — canonical target ≠ canonical scan root. Root and all ancestors
   are never deletable. The ancestor check is a **special case of containment**: any
   ancestor of the root is by definition outside the boundary, so no redundant
   separate condition exists.
5. **Reparse-point integrity** — no symlink/junction/reparse in the canonical chain may
   resolve outside the authorized tree. If resolution cannot be determined with
   confidence, deletion is **denied/deferred — never guessed**.
6. **Final revalidation** — conditions 1–5 re-checked against the freshly canonicalized
   target **immediately before** the deletion operation.

### 2.2 Protected-path policy

A declarative, data-driven list (Knowledge Base Tier 0 plus known Windows system
locations) that forbids deletion regardless of containment. In Phase 1 this is the
existing critical/app protected path logic (see `folder_analyzer/safety.py` and
`is_protected_path`).

### 2.3 Deletion authorization

User consent. The UI enables destructive action only for SAFE_TO_DELETE items; the CLI
requires explicit confirmation; REVIEW_FIRST / KEEP / DO_NOT_DELETE never enter the
normal delete workflow. Authorization is **not** the same as containment or protected
paths.

### 2.4 Deletion operation

Recycle Bin via `send2trash` (recoverable). Never silent permanent erasure.

## 3. Long-path / unresolvable-path policy

Two and only two outcomes are recognized:

- **Case A — Resolved and safely validated:** the path is successfully canonicalized
  (including Windows extended-length `\\?\` forms), containment + root + reparse +
  protected-path checks pass, and final revalidation succeeds. Deletion proceeds.
- **Case B — Cannot be safely represented, resolved, or operated on** by the current
  runtime/environment.

**Operational definition of "deferred" (Case B):** the path is marked `DEFERRED` exactly
**once per scan or delete attempt**. There is **no automatic retry and no silent retry
loop / backoff**. A fresh, explicit user action (new scan, or a delete attempt after the
environment changed) re-evaluates the path from scratch. "Deferred" never means
"guessing a safe identity" and never means "keep retrying until it works."

There is **no blanket 260-character limit**. The rule is: reject or defer any path that
cannot be **safely represented, resolved, or operated on** by the current
runtime/environment.

**Required behavior matrix (Case B, NOT_RESOLVABLE):**

| Concern | Behavior |
|---|---|
| Auto-retry | No. Single attempt, no backoff, no silent infinite retry. |
| Deletion result | **Denied** at delete time — Phase 1 implements this path. Never falls back to an unsafe comparison. |
| Scan classification (Phase 1) | **NOT IMPLEMENTED in Phase 1.** A scan/analysis-time `NOT_RESOLVABLE` flag, a Confidence value, and a "cannot be validated" scan status are **Phase 3 (file analysis) / Phase 5 (recommendation engine)** work. The Phase 1 scanner does not flag `NOT_RESOLVABLE`; its only per-folder signal is the pre-existing `FolderInfo.error` field (permission/OS errors), which is **not equivalent** to a `NOT_RESOLVABLE` classification and must not be read as one. |
| Scan results (Phase 1) | No `NOT_RESOLVABLE`/confidence data is surfaced in scan output. See the row above — deferred to Phases 3/5. |
| CLI | Explicit per-target message ("cannot be safely validated — not deleted"); counted as deferred; never implies success. (Implemented in Phase 1.) |
| API | `400` with `error_code: "UNRESOLVABLE_PATH"` and a human-readable reason. (Implemented in Phase 1.) |
| Web / Desktop UI | NOT IMPLEMENTED. Status "cannot be validated" + reasoning + delete control disabled are Phase 7 (web) / Phase 9–10 (desktop) work; the API already exposes `UNRESOLVABLE_PATH` for UIs to surface. |
| Audit/result record | Outcome `deferred`, canonicalization attempt, reason. (Implemented in Phase 1.) |
| Security bottom line | If canonical identity and containment cannot be safely established, deletion **must** be denied/deferred. |

## 4. Internal canonical paths vs user-facing paths

`\\?\` extended-length forms and any canonical/normalized identity are **internal
representations only**. They may be used solely for: canonicalization, identity
comparison, containment checks, reparse-point validation, security decisions, and
filesystem operations where the runtime requires them.

They **MUST NOT** become the normal user-facing representation. CLI, Web, Desktop,
exports (where human-readable paths are intended), and audit/log output display the
**original human-readable path** supplied or discovered, subject to normal safe
formatting. If the original path cannot be displayed exactly, a documented
human-readable fallback is shown — internal `\\?\` forms are never leaked to the UI
merely because they were used for validation.

## 5. Security roles

- `os.access(path, os.W_OK)` is **diagnostics only** — it may be used for a pre-flight
  warning, but it is **never** proof of authorization and **never** part of the security
  boundary.
- The security boundary relies exclusively on: canonical containment, protected-path
  checks, reparse-point validation, deletion authorization, and final validation.

## 6. Three-axis safety model (Phase 2 — implemented)

Each item ultimately receives a single immutable `Assessment`. Folder-level
aggregation arrives in Phase 5; Phase 2 defines the value space and its
invariants.

**Value spaces** (`folder_analyzer/engine/enums.py`):

- `SystemImpact` — NONE / LOW / MODERATE / HIGH / CRITICAL / UNKNOWN
- `DeletionRecommendation` — SAFE_TO_DELETE / REVIEW_FIRST / KEEP / DO_NOT_DELETE
- `ConfidenceLevel` — HIGH / MEDIUM / LOW. Confidence is confidence **in the
  classification**, not confidence in deletion safety (`docs/ROADMAP.md §5`).

**`Assessment`** (`folder_analyzer/engine/models.py`) — frozen dataclass with
fields `impact`, `recommendation`, `confidence`, `reason_key`, `reason_params`,
`detected_category`, `app_id`, `is_user_data`, `is_temporary`.

### Confidence gate (I9) — as implemented

Enforced **inside construction** (`Assessment.__post_init__`), so the invalid
combination is structurally unrepresentable — no post-hoc validator exists that
could be skipped:

```python
def apply_confidence_gate(recommendation, confidence):
    if recommendation == SAFE_TO_DELETE and confidence is not HIGH:
        return REVIEW_FIRST
    return recommendation
```

`__post_init__` applies the same gate plus the I3 (UNKNOWN impact) and I7
(`is_user_data`) floors: both force `SAFE_TO_DELETE` → `REVIEW_FIRST` at
construction. **Reason coherence:** any such demotion also rewrites `reason_key`
(/`reason_params`) to the cause of the demotion (`confidence_gate_promoted` /
`uncertain` / `user_data`), so a `REVIEW_FIRST` result never carries a
safe-to-delete rationale. All of this is verified in
`tests/test_safety_invariants.py` (incl. exhaustive `itertools` products).

**Explainability** (`folder_analyzer/engine/explain.py`): Phase 2 `reason_key`
strings resolve to localized EN/ES text following the `i18n.py` pattern. The
full single-source i18n migration is Phase 7.

### Content-analysis levels & retention (Phase 4 status)

- **Level 1 (metadata/path, no file I/O) is implemented** by the scanner
  (`folder_analyzer/scanner.py`, `engine/models.py` `FileEntry`): per-file
  path/filename/extension/size/timestamps/attributes collected during traversal
  with **zero additional syscalls** (reuses the single `entry.stat()` per file).
  Records stay `category="unknown"` and `assessment=None`.
- **Level 2 (magic bytes, ≤512 B) and Level 3 (targeted bounded inspection,
  ≤4 KB) are implemented** inside the KB package (`folder_analyzer/engine/kb/content.py`)
  but are **standalone only** — reachable via `kb.classify_content(path, level)`,
  never called by the scanner. Level 2 resolves ambiguous/extensionless types by
  bounded prefix reads; Level 3 re-confirms SQLite within the window and detects
  Ollama manifests (paths containing `ollama`+`manifests` + OCI JSON fields ≤4 KB).
  Both levels are proved by an instrumented bounded-read test on a >100 MB sparse
  file (≤512 B / ≤4 KB respectively). The scanner never reads file contents
  (analysis/composition time stays 0.0 in the benchmark).
- **Bounded retention** (`engine/retention.py`): configurable global budget
  (default 10,000 records) and per-folder cap (default 200); priority
  **non-safe → representative → largest → path**. Since Phase 5 the scanner
  attaches real `ScanAssessment`s, so the `non_safe` component discriminates
  genuine (non-`SAFE_TO_DELETE`) priorities against the retirement budget
  (verified end-to-end in `test_scanner_retention_discriminates_non_safe_via_real_classification`).
  Assertions remain lightweight: per-file `ScanAssessment` (bucket precomputed),
  with full `Assessment`s materialized only for the retained subset.
- **Three-stage lifecycle:** ANALYZED always covers **100% of accessible files**;
  RETAINED is the bounded subset. Eviction reduces `records_retained` only —
  never `files_analyzed`. Folders whose records were evicted are re-analyzed on
  demand (single-folder re-scan) for drill-down.
- **Relevant defense:** "not retained" must never be presented as "not analyzed";
  the analyzer counts every accessible file independently of retention.

## 7. TOCTOU / race conditions (honest statement)

Canonicalization does not completely solve race conditions. This document states
explicitly:

- **Mitigated:** the guard canonicalizes at validation time and re-canonicalizes the
  actual target immediately before deletion, with all conditions re-checked. Most
  swapped-path / reparse-swap scenarios are detected.
- **Remains possible:** filesystem state can change between validation and deletion
  (TOCTOU window) — the final check narrows but cannot eliminate this window in every
  case.
- **Final deletion-time validation:** re-runs conditions 1–5 on the freshly resolved
  path right before `send2trash`.
- **Practical guarantee:** the guard prevents accidental deletion outside the authorized
  tree under normal conditions and detects most race scenarios.
- **Limitations:** we do not claim cryptographic-level race safety against an active
  adversary swapping paths in the window. Full atomicity would require delete-by-handle
  semantics (e.g., Windows `FILE_FLAG_OPEN_REPARSE_POINT`); this is documented as future
  hardening and is out of scope for now.

## 8. Deletion audit log

A lightweight, **append-only JSON Lines** log (`deletion_audit.jsonl` by default,
overridable via configuration) recording, **per deletion attempt (including denied)**:

- timestamp (ISO 8601)
- original human-readable path
- canonical/internal path if safely available (internal use; not displayed as the
  normal user-facing path)
- status: `success` / `denied` / `deferred` / `failure`
- reason / error code
- risk/assessment snapshot available at Phase 1 (risk level; Phase 5 pipes the
  three-axis `Assessment` snapshot)

The log is append-only; no in-place mutation.

## 9. Safety invariants (Phase 1 deletion-security + Phase 2 model implemented)

Status per invariant (implemented = enforced by code + covered by automated
tests; `tests/test_safety_invariants.py` = Phase 2 model, Phase 1 suite =
deletion security):

- **I1 — Core principle** *(implemented)* — "Uncertainty must reduce deletion
  authority, never increase it." Asserted exhaustively for UNKNOWN impact.
- **I2 — Positive evidence** *(implemented as a Phase 2 contract)* — SAFE_TO_DELETE
  requires positive, high-confidence evidence; no SAFE without HIGH confidence,
  non-UNKNOWN impact, and a positive-evidence reason key. Prohibited chains in
  `docs/ROADMAP.md §6`.
- **I3 — UNKNOWN (strict)** *(implemented)* — any UNKNOWN item ⇒ ≤ REVIEW_FIRST;
  any folder with any UNKNOWN descendant ⇒ ≤ REVIEW_FIRST (folder aggregation
  since Phase 5, roadmap §11 R3 + `UNKNOWN_BLOCK = 0.0`).
- **I4 — Containment** *(implemented, Phase 1)* — deletion only inside the active
  scanned root.
- **I5 — Root/ancestor protection** *(implemented, Phase 1)*.
- **I6 — Protected paths** *(implemented, Phase 1)*.
- **I7 — User value** *(model floor implemented)* — personal/user-value content is
  never SAFE_TO_DELETE; enforced by `is_user_data` at Assessment construction.
- **I8 — Explainability** *(model foundation implemented)* — every classification
  carries confidence + reason (`reason_key` → localized text via explain.py);
  full UI/exports tooltips are Phase 7.
- **I9 — Confidence gate** *(implemented)* — SAFE_TO_DELETE requires HIGH confidence;
  enforced at Assessment construction, not post-hoc.
- **I10 — Item-level authority** *(implemented, Phase 5 integration test)* —
  item authority = the item's own immutable `Assessment`; a `SAFE_TO_DELETE`+`HIGH`
  item beneath a folder-derived `REVIEW_FIRST` remains guard-validated; the folder
  recommendation gates only folder-as-a-whole actions (see `tests/test_i10_integration.py`
  and the Phase 2 `test_i10_*` suite).

## 10. Safety limitations

1. The Phase 1 guard proves containment and protected-path compliance; scan-time
   assessment (Phase 5) is advisory — the guard itself never blocks on
   classification, it enforces path security.
2. Race-condition atomicity is bounded (§7); delete-by-handle hardening is future work.
3. Long-path handling depends on the runtime and OS long-path support; real edge cases
   are validated with the path-representation tests.
4. Symlink/junction tests degrade gracefully where OS privileges prevent reparse-point
   creation.
5. The Phase 2 three-axis `Assessment` is fully wired since Phase 5 (scan-time
   assessments, folder aggregation, composition). Stil progress: only the UI-side
   delete gating that *renders* the assessment is not consumed by the CLI/API yet
   (surfacing polish is Phase 7/12 work).
6. Phase 3/4 file analysis is **metadata only (Level 1)** at scan time; the KB
   package *can* classify bounded content prefixes but the scanner never reads file
   contents (analysis/composition time stays 0.0 in the benchmark). Since Phase 5
   every accessible file is path-classified into its `ScanAssessment`; a failed or
   unfounded classification stays `NOT_RESOLVABLE` and aggregates to `UNKNOWN` —
   the default/unknown outcome must never be read as a safety signal. Confirmed:
   **the KB produces `KBResult` categories only — it never constructs
   `Assessment` objects or `SAFE_TO_DELETE`-style recommendations** (KBResult has
   no assessment/recommendation fields; asserted by tests).

## 11. What Phase 5 added (implemented)

- The full safety engine now evaluates at scan time: `classify_scan` per file
  (KB → policy → `ScanAssessment`) and `derive_folder_recommendation` per folder.
- Folder composition and folder-level aggregation: any folder with an UNKNOWN
  descendant is at most REVIEW_FIRST (I3 folder level); a folder's derived
  recommendation never overrides item-level authority (I10 full).
- Knowledge-base integration (Phase 4) feeding `detected_category` / `app_id` and
  rich reason provenance.
- Composition thresholds (`SAFE_MIN_SHARE` 0.85 / `KNOWN_NON_DISPOSABLE_CEILING`
  0.10 / `REVIEW_SHARE` 0.15 / `UNKNOWN_BLOCK` 0.0, per `docs/ROADMAP.md §5`) as
  named constants in `CompositionConfig`.

Scan-time `NOT_RESOLVABLE` surfacing (confidence flagging, "cannot be validated"
status in scan output) is deliberately **NOT implemented in Phases 1–3**: Phase 3
implemented only the Level-1 metadata/retention foundation; the classification
that would produce a `NOT_RESOLVABLE` flag belongs to **Phase 5 (recommendation
engine)** — see the §3 matrix. Phase 1 implements only delete-time
`NOT_RESOLVABLE` handling. The `FolderInfo.error` field is pre-existing
and is not a `NOT_RESOLVABLE` classification.