# Folder Analyzer — Safety Model & Deletion Security

Status: **Phase 1 — deletion-security foundation.**
Sections 4–6 (three-axis safety model, invariants, composition) are defined in
`docs/ROADMAP.md` and will be expanded here in **Phase 2 (model)** and **Phase 5
(composition)**.

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

## 6. TOCTOU / race conditions (honest statement)

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

## 7. Deletion audit log

A lightweight, **append-only JSON Lines** log (`deletion_audit.jsonl` by default,
overridable via configuration) recording, **per deletion attempt (including denied)**:

- timestamp (ISO 8601)
- original human-readable path
- canonical/internal path if safely available (internal use; not displayed as the
  normal user-facing path)
- status: `success` / `denied` / `deferred` / `failure`
- reason / error code
- risk/assessment snapshot available at Phase 1 (risk level, phases 2+ will extend)

The log is append-only; no in-place mutation.

## 8. Safety invariants (recorded; fully implemented Phase 2/5)

- **I1 — Core principle:** *"Uncertainty must reduce deletion authority, never increase it."*
- **I2 — Positive evidence:** SAFE_TO_DELETE requires positive, high-confidence evidence. Prohibited chains listed in `docs/ROADMAP.md §6`.
- **I3 — UNKNOWN (strict):** any UNKNOWN item/descendant ⇒ ≤ REVIEW_FIRST. `UNKNOWN_BLOCK = 0.0`.
- **I4 — Containment:** deletion only inside the active scanned root.
- **I5 — Root/ancestor protection.**
- **I6 — Protected paths.**
- **I7 — User value:** folders with personal/user-value content are never SAFE_TO_DELETE.
- **I8 — Explainability:** every classification carries confidence + reason.
- **I9 — Confidence gate:** SAFE_TO_DELETE requires HIGH confidence.
- **I10 — Item-level authority:** item authority = the item's own Assessment; folder
  recommendation gates only folder-as-a-whole actions.

## 9. Safety limitations

1. The Phase 1 guard proves containment and protected-path compliance; it does **not**
   yet classify content (Phase 2+).
2. Race-condition atomicity is bounded (§6); delete-by-handle hardening is future work.
3. Long-path handling depends on the runtime and OS long-path support; real edge cases
   are validated with the path-representation tests.
4. Symlink/junction tests degrade gracefully where OS privileges prevent reparse-point
   creation.

## 10. What Phase 2 will add

The three-axis model (System Impact / Deletion Recommendation / Confidence / Reason),
the classifier/invariant engine, and the Confidence semantics. Section 4 of this
document will then be rewritten from "recorded" to "implemented."

Scan-time `NOT_RESOLVABLE` surfacing (confidence flagging, "cannot be validated"
status in scan output) is deliberately **deferred to Phase 3 (per-file analysis) /
Phase 5 (recommendation engine)** — see the §3 matrix: Phase 1 implements only
delete-time `NOT_RESOLVABLE` handling. The `FolderInfo.error` field is pre-existing
and is not a `NOT_RESOLVABLE` classification.