# Folder Analyzer — Safety Model & Deletion Security

Status: **Phase 2 — safety model foundation implemented.**
The three-axis safety model (enums, `Assessment`, construction-time confidence
gate, explainability) is implemented in Phase 2 and documented in §6 below.
Folder-level composition and the live recommendation engine are **Phase 5
(composition)** work.

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
construction. All of this is verified exhaustively in
`tests/test_safety_invariants.py`.

**Explainability** (`folder_analyzer/engine/explain.py`): Phase 2 `reason_key`
strings resolve to localized EN/ES text following the `i18n.py` pattern. The
full single-source i18n migration is Phase 7.

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
- **I3 — UNKNOWN (strict)** *(item level implemented; folder level Phase 5)* — any
  UNKNOWN item ⇒ ≤ REVIEW_FIRST; any folder with any UNKNOWN descendant ⇒ ≤
  REVIEW_FIRST (folder aggregation is Phase 5). `UNKNOWN_BLOCK = 0.0` (Phases 5).
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
- **I10 — Item-level authority** *(scaffold implemented; full test in Phase 5)* —
  item authority = the item's own immutable `Assessment`; folder recommendation
  gates only folder-as-a-whole actions (see `test_i10_*` in the Phase 2 suite).

## 10. Safety limitations

1. The Phase 1 guard proves containment and protected-path compliance; it does **not**
   yet classify content (the assessment engine is Phase 5).
2. Race-condition atomicity is bounded (§7); delete-by-handle hardening is future work.
3. Long-path handling depends on the runtime and OS long-path support; real edge cases
   are validated with the path-representation tests.
4. Symlink/junction tests degrade gracefully where OS privileges prevent reparse-point
   creation.
5. The Phase 2 three-axis `Assessment` is a pure value model: nothing in the CLI, API,
   or web consumes it yet. Pipeline integration (scan-time assessments, folder
   aggregation, delete UI gating) is Phase 5+.

## 11. What Phase 5 will add

- The full safety engine: classifier + recommendation engine evaluated at scan time.
- Folder composition and folder-level aggregation: any folder with an UNKNOWN
  descendant is at most REVIEW_FIRST (I3 folder level); a folder's derived
  recommendation never overrides item-level authority (I10 full).
- Knowledge-base integration (Phase 4) feeding `detected_category` / `app_id` and
  rich reason provenance.
- Composition thresholds (`SAFE_MIN_SHARE` 0.85 / `KNOWN_NON_DISPOSABLE_CEILING`
  0.10 / `REVIEW_SHARE` 0.15 / `UNKNOWN_BLOCK` 0.0, per `docs/ROADMAP.md §5`) as
  named constants.

Scan-time `NOT_RESOLVABLE` surfacing (confidence flagging, "cannot be validated"
status in scan output) is deliberately **deferred to Phase 3 (per-file analysis) /
Phase 5 (recommendation engine)** — see the §3 matrix: Phase 1 implements only
delete-time `NOT_RESOLVABLE` handling. The `FolderInfo.error` field is pre-existing
and is not a `NOT_RESOLVABLE` classification.