# Folder Analyzer — Master Roadmap v3.0

Status: **APPROVED — Phases 1–8 complete. Phase 8 (Performance & Scale) delivered: O1 single `_policy_for` + inlined bucket, O2 bounded per-folder filename verdict cache, core `ScanCancellation` wired to a `POST /api/scan/cancel` endpoint, reproducible benchmark harness (fixed `--affinity` mask, KB µs/file, cancel probe). Suite 369 passed / 2 skipped. Raw smoke `t_scan` 0.309–0.311 s (−13.6% same-mask vs Phase-7 state), export t_scan 0.3549 s (−7.6%), KB dispatch 2.4–2.7 µs/file, gate 0.26 MiB / 7,400 @ +0%, export bytes byte-identical, cancellation stops ≈8 ms after request. Evidence: ARCHITECTURE §6c + `benchmarks/results/smoke_p8_*.json`. Phase 7 (Web UI + single-source i18n) delivered and submitted for acceptance: single-source `locales/{en,es}.json` (ui + reasons namespaces) consumed by CLI/API/exports/Web UI, schema-v2 API surfaces, I10 folder/file gating, zero re-classification. All 6 verification points answered with evidence (2026-09-14, commit `09e38eb`: new HEAD benchmark side-by-side, I10 `rec`/`deletable` per-item proof, `retained_records_for` no-reanalyze test, `reason_params` interpolation through the real API→UI path, engine `git diff` clean except sanctioned `explain.py`). Pending formal acceptance before Phase 9 (Desktop Architecture & Prototype).**
Version of this document: Phase 1 baseline commit.

This is the implementation contract for the project. It is the single, internally
consistent, implementation-ready roadmap. Any contradiction found between this
document and another source is resolved **in favor of this document** until a
correction is approved in writing.

---

## 1. Executive Summary

Folder Analyzer currently ships as v2.0.0 (CLI + FastAPI web, 81 passing tests,
branch `master`, synced with `origin`). This roadmap takes it to **v3.0.0** through
**12 sequential phases** anchored on a rigorous three-axis safety model, a deletion
security boundary, a trustworthy per-file analysis pipeline, and a new PySide6
desktop product.

- Core engine remains 100% UI-independent (no FastAPI/Rich/PySide6/browser dependencies).
- Safety is defined by **positive evidence**, never by the *absence* of a danger classification.
- Deletion authority is gated by containment, protected paths, reparse-point
  validation, authorization, and final revalidation.
- Total effort: **79–126 hours (~4–7 weeks at 20 hrs/week).** This is the single
  authoritative figure (updated from 75–120 h when the 50k fixture one-time cost was
  added to Phase 1).

## 2. Product Vision

A tool that helps a Windows user understand what is taking space, what can be safely
removed, and what must be preserved — with an engine that can **explain every
conclusion** (System Impact, Deletion Recommendation, Confidence, Reason) and a UI
that **cannot casually delete anything it is not entitled to**. Delivery surfaces:
CLI, optional Web UI, and a native PySide6 desktop app, all consuming one core engine.

## 3. Current State (Phase 1 baseline)

- Repo: `C:\OPENCODE\Folder_Analyzer`, branch `master`, synced with `origin`
  (`https://github.com/Darjona25-code/Folder_Analizer.git`).
- v2.0.0; wheel installs `folder-analyzer-2.0.0`; `folder-analyzer.exe` entry point
  verified (EN+ES, EOF, CSV/HTML export).
- 81 tests pass at Phase 1 start. Live API verified (28/28 checks): root deletion
  blocked, child deletable, System32 blocked, missing path ⇒ `total_deleted == 0`,
  restart clears state.
- Phase 1 introduces: canonical six-condition deletion guard, deletion audit log,
  deletion security tests, deterministic 50k-file smoke benchmark + baseline, and the
  docs foundation.
- Limitations remaining after Phase 1 (addressed by later phases): no three-axis
  safety model, no file analysis/retention, no knowledge base, no recommendation or
  composition engine, no exports v2, no desktop, no packaging.

## 4. Target Architecture

```
                    FOLDER ANALYZER CORE
                            |
             +--------------+--------------+
             |              |              |
            CLI            WEB          DESKTOP
             |              |              |
           Rich          FastAPI        PySide6
```

- **Core** (no UI dependencies): scanner, file analysis, knowledge base, safety engine,
  recommendation engine, folder composition, deletion guard, export/domain functionality.
  Core must not depend on FastAPI, Rich, PySide6, or browser UI.
- **Desktop** uses the core **directly in-process**. Do **not** build
  `Desktop → localhost FastAPI → Core` unless a compelling, documented technical
  requirement appears.
- **Web/API** is retained as an **optional interface** (decision D3). **CLI** remains
  the lightest interface.

## 5. Safety Model — Final Definitions

Three **independent** dimensions plus explanation:

| Dimension | Values |
|---|---|
| **System Impact** | NONE, LOW, MODERATE, HIGH, CRITICAL, UNKNOWN |
| **Deletion Recommendation** | SAFE_TO_DELETE, REVIEW_FIRST, KEEP, DO_NOT_DELETE |
| **Confidence** | HIGH, MEDIUM, LOW |
| **Reason / Explanation** | Always present; human-readable, rule-id traceable |

**Confidence semantics (explicit):** Confidence measures confidence **in the
assessment/classification** — not confidence that deletion is safe. A personal
document may be `System Impact: NONE | Recommendation: REVIEW_FIRST | Confidence:
HIGH` — we are highly confident it is a personal file; we are NOT confident the user
wants it deleted.

At the folder level (Phase 5, §11), derived REVIEW_FIRST confidence measures certainty
of the SINGLE aggregate verdict over the composition — not byte-classification certainty
(item-level, above). A heterogeneous mix of structurally distinct categories is harder
to summarize in one verdict and therefore carries MEDIUM even when every byte is
individually well-classified (Ex6: `unknown_pct = 0` yet MEDIUM, matching Ex4/Ex7);
HIGH is reserved for near-homogeneous or single-policy-determined compositions (Ex1,
Ex2, Ex8, R1 hard rule).

**Confidence gate (mandatory):** `IF recommendation == SAFE_TO_DELETE AND confidence
!= HIGH → promote to REVIEW_FIRST`. A SAFE_TO_DELETE with non-HIGH confidence is not
expressible.

## 6. Safety Invariants

- **I1 — Core principle:** *"Uncertainty must reduce deletion authority, never increase it."*
- **I2 — Positive evidence:** `SAFE_TO_DELETE` requires positive, high-confidence
  evidence. Prohibited chains: `UNKNOWN → … → SAFE_TO_DELETE`; `"not recognized as
  dangerous" → SAFE_TO_DELETE`; `SystemImpact = NONE → auto SAFE_TO_DELETE`;
  `SystemImpact = LOW → auto SAFE_TO_DELETE`; `Confidence = LOW → SAFE_TO_DELETE`.
- **I3 — UNKNOWN (strict):** Any item classified UNKNOWN, or any folder for which any
  descendant remains UNKNOWN, is `REVIEW_FIRST` at most. `UNKNOWN_BLOCK = 0.0`.
  UNKNOWN can only be reclassified through the rule engine; it cannot remain UNKNOWN
  while contributing toward SAFE_TO_DELETE.
- **I4 — Containment:** deletion only ever occurs inside the active scanned root boundary.
- **I5 — Root/ancestor protection:** the scan root and all its ancestors are never
  deletable (root protected explicitly; ancestors are outside the containment boundary).
- **I6 — Protected paths:** protected system paths are never deleted.
- **I7 — User value:** a folder containing personal/user-value content is never
  SAFE_TO_DELETE (floor of REVIEW_FIRST).
- **I8 — Explainability:** every classification carries a confidence and a reason.
- **I9 — Confidence gate invariant:** no derived result may carry SAFE_TO_DELETE with
  MEDIUM or LOW confidence; such a result is re-classified as REVIEW_FIRST.
- **I10 — Item-level authority:** deletion authority is determined by the target item's
  **own** Assessment, independently of its parent folder's derived recommendation. A
  REVIEW_FIRST folder does NOT block deleting an individually SAFE_TO_DELETE/HIGH file
  inside it; only the folder-as-a-whole action is gated by the folder's recommendation.

## 7. Deletion Security Model (Phase 1 implementation)

**Deletion Security = Containment security + Protected-path policy + Deletion
authorization + Deletion operation.** Related but distinct concepts:

1. **Containment security** — the six-condition guard.
2. **Protected-path policy** — declarative list (Tier 0 + Windows system locations).
3. **Deletion authorization** — user consent; UI enables destructive action only for
   SAFE_TO_DELETE; CLI requires explicit action; REVIEW_FIRST/KEEP/DO_NOT_DELETE never
   enter the normal delete workflow.
4. **Deletion operation** — Recycle Bin via `send2trash` (recoverable), never silent
   permanent erasure.

### Six-condition deletion guard

1. **Valid path input** — non-empty, correct type, no NUL bytes.
2. **Safe canonicalization** — per-component `realpath` + `normcase` identity; single
   canonical reference form.
3. **Containment** — canonical target is a descendant of the canonical active scan
   root, via path-component boundary (never raw string prefix).
4. **Root protection** — canonical target ≠ canonical scan root. Ancestor check is a
   special case of containment (any ancestor of the root is outside the boundary).
5. **Reparse-point integrity** — no symlink/junction/reparse in the chain may resolve
   outside the authorized tree; uncertain ⇒ deny/defer, never guess.
6. **Final revalidation** — conditions 1–5 re-checked immediately before the deletion
   operation.

**Long-path / unresolvable-path policy (operational).**

Two outcomes:
- **Case A — Resolved and safely validated**, including Windows extended-length `\\?\`
  forms.
- **Case B — Cannot be safely represented, resolved, or operated on** by the current
  runtime/environment.

**Operational definition of "deferred" (Case B):** marked `DEFERRED` exactly once per
scan or delete attempt; **no automatic retry, no backoff, no silent retry loop**.
A fresh explicit user action (new scan or new delete attempt after the environment
changed) re-evaluates from scratch. Deferred never means guessing, never means
"keep retrying."

| Concern | Behavior (Case B) |
|---|---|
| Auto-retry | No. Single attempt. |
| Deletion result | **Denied** at delete time — Phase 1 implements this path. |
| Scan classification (Phase 1) | **NOT IMPLEMENTED in Phase 1.** A scan/analysis-time `NOT_RESOLVABLE` flag, Confidence value, and "cannot be validated" scan status are **Phase 3 (file analysis) / Phase 5 (recommendation engine)** work. The Phase 1 scanner does not flag `NOT_RESOLVABLE`; its only per-folder signal is the pre-existing `FolderInfo.error` field (permission/OS errors), not equivalent to a `NOT_RESOLVABLE` classification. |
| Scan results (Phase 1) | No `NOT_RESOLVABLE`/confidence data surfaced in scan output; deferred to Phases 3/5. |
| CLI | Explicit per-target message; counted as deferred; never implies success. (Implemented in Phase 1.) |
| API | `400` with `error_code: "UNRESOLVABLE_PATH"` + human-readable reason. (Implemented in Phase 1.) |
| Web / Desktop UI | NOT IMPLEMENTED. Status + reason + delete disabled are Phase 7 (web) / 9–10 (desktop) work; the API exposes `UNRESOLVABLE_PATH` for UIs to surface. |
| Audit/result record | Outcome `deferred`, canonicalization attempt, reason. (Implemented in Phase 1.) |
| Security bottom line | If canonical identity/containment cannot be safely established, deletion **must** be denied/deferred. |

**Internal canonical paths vs user-facing paths.** `\\?\` extended forms and canonical
identities are **internal only** (canonicalization, identity comparison, containment,
reparse validation, security decisions, and filesystem operations where required).
CLI, Web, Desktop, exports (human-readable), and audit output display the **original
human-readable path** (safe formatting, documented fallback). Internal `\\?\` forms are
never leaked to the UI.

**Security roles.** `os.access(path, os.W_OK)` is diagnostics only — never proof of
authorization, never part of the security boundary.

**TOCTOU (honest statement).** The guard canonicalizes at validation and re-canonicalizes
immediately before deletion, detecting most race scenarios. Filesystem state can still
change between validation and deletion; the practical guarantee is: the guard prevents
accidental deletion outside the authorized tree under normal conditions. Full atomicity
(delete-by-handle with `FILE_FLAG_OPEN_REPARSE_POINT`) is documented as future hardening,
out of scope for now. We do not overclaim security.

**Deletion audit log (owned by Phase 1).** Append-only JSON Lines file recording per
deletion attempt: timestamp, original human-readable path, canonical/internal path
(if safely available, internal use), status (`success`/`denied`/`deferred`/`failure`),
reason/error code, risk/assessment snapshot available at Phase 1. Written for every
attempt, including denied.

## 8. File Analysis Model (Phases 3)

Three-state model at record level — **DISCOVERED → ANALYZED → RETAINED**. Distinguishes:
files encountered; files successfully analyzed (all accessible files); records retained
(bounded subset); files inaccessible (permissions/errors, reported separately). Aggregate
statistics computed over ALL analyzed files. UI must NOT imply "not retained = not
analyzed." Content analysis has three targeted, bounded levels (metadata; lightweight
signatures/magic bytes; targeted bounded inspection). No indiscriminate full-file
scanning; no loading huge files into memory. Levels 1–3 only.

## 9. File Retention Model (Phase 3)

No architectural "200 files per folder." Bounded global strategy: memory budget
(initial engineering default ≈25k–50k records, configurable), relevance, risk/
recommendation, largest files, drill-down value, representative records. Priority:
REVIEW_FIRST/non-safe → largest files → representative samples → others as capacity
permits. Explicitly an engineering default, not a universal rule.

## 10. Knowledge Base Strategy (Phase 4)

Six data-driven tiers (0 critical paths, 1 known locations, 2 common app data, 3 file
categories/extensions, 4 high-value app rules, 5 optional registry). Registry is read
**once per scan session** (batch-loaded, cached), never per-path; absence degrades
gracefully. Unknown stays unknown; no exhaustive enumeration of Windows applications.
Tier 0 feeds the protected-path policy.

## 11. Folder Composition Model (Phases 5)

**Rule-evaluation model: short-circuit.** R1, R2, R3 are hard, short-circuit rules:
when triggered, evaluation stops immediately and returns the assigned recommendation.
R4–R6 are only reachable when R1–R3 did not trigger, so at R4 `USER_VALUE`,
`PROTECTED_CRITICAL`, and `UNKNOWN` shares are guaranteed 0.

**Exhaustive, mutually exclusive descendant-byte categories** (every byte in exactly one):

1. **DISPOSABLE** — known high-confidence disposable content (positive evidence).
2. **USER_VALUE** — personal/user-value content, or content the user may reasonably want.
3. **PROTECTED_CRITICAL** — protected Windows/system/application-critical content.
4. **KNOWN_NON_DISPOSABLE** — understood/classified but not positively disposable.
5. **UNKNOWN** — insufficient evidence.

`DISPOSABLE + USER_VALUE + PROTECTED_CRITICAL + KNOWN_NON_DISPOSABLE + UNKNOWN = 100%`
of descendant bytes. No double-counting, no undefined remainder. Classification priority:
`PROTECTED_CRITICAL` > `USER_VALUE` > (DISPOSABLE vs KNOWN_NON_DISPOSABLE by positive
evidence) > `UNKNOWN`.

**NOT_RESOLVABLE aggregation:** items flagged `NOT_RESOLVABLE` (Case B, LOW confidence)
are counted as **UNKNOWN-category bytes** for composition. Any folder with an
unresolvable descendant ⇒ non-zero UNKNOWN share ⇒ R3 ⇒ folder ≤ REVIEW_FIRST.

**Zero-byte handling:** zero-byte files still get a category but contribute 0 bytes;
percentages are over total descendant bytes only. A 0-total-byte tree is resolved by
direct folder assessment (empty + positive direct evidence ⇒ SAFE; otherwise REVIEW_FIRST).

**Rules (initial heuristic thresholds, subject to validation, implemented as named
configurable constants):**

| Constant | Default | Meaning |
|---|---|---|
| `SAFE_MIN_SHARE` | 0.85 | DISPOSABLE / total byte floor for SAFE eligibility (gate, not guarantee) |
| `KNOWN_NON_DISPOSABLE_CEILING` | 0.10 | max allowed KNOWN_NON_DISPOSABLE share for SAFE |
| `REVIEW_SHARE` | 0.15 | KNOWN_NON_DISPOSABLE share threshold for R4 |
| `UNKNOWN_BLOCK` | 0.0 | any UNKNOWN bytes block SAFE |
| `CONFIDENCE_GATE` | HIGH | SAFE requires HIGH confidence |

- **R1 (hard):** `PROTECTED_CRITICAL` bytes present ⇒ DO_NOT_DELETE. Return.
- **R2 (hard):** `USER_VALUE` bytes present ⇒ ≤ REVIEW_FIRST. Return.
- **R3 (hard):** `UNKNOWN` bytes present ⇒ ≤ REVIEW_FIRST (`UNKNOWN_BLOCK = 0.0`). Return.
- **R4:** `KNOWN_NON_DISPOSABLE/TOTAL ≥ REVIEW_SHARE` ⇒ REVIEW_FIRST.
- **R5:** `DISPOSABLE/TOTAL ≥ SAFE_MIN_SHARE` AND `KNOWN_NON_DISPOSABLE/TOTAL ≤
  KNOWN_NON_DISPOSABLE_CEILING` AND positive direct disposable evidence AND confidence
  HIGH ⇒ SAFE_TO_DELETE.
- **R6:** otherwise ⇒ REVIEW_FIRST.

Interaction: with hard rules short-circuited, `DISPOSABLE + KNOWN_NON_DISPOSABLE = 100%`
at R4/R5. `KNOWN_NON_DISPOSABLE_CEILING` (0.10) is deliberately stricter than
`REVIEW_SHARE` (0.15); the 10–15% band fails R5 and falls to R6 (REVIEW_FIRST).

**Zero-tolerance UNKNOWN trade-off (explicit product decision):** folder-level
SAFE_TO_DELETE will realistically occur primarily for small, fully cataloged,
high-confidence disposable folders (e.g., known browser cache trees) and will rarely or
never occur for large real-world trees where at least one file is unclassified. This is
**intentional and acceptable** — not a defect to later "fix." The product prioritizes
deletion trustworthiness over maximizing the number of SAFE_TO_DELETE results.
`UNKNOWN_BLOCK` will not be weakened merely to inflate safe results.

**Canonical examples (internally consistent):**

| # | Scenario | System Impact | Recommendation | Confidence | Reason |
|---|---|---|---|---|---|
| 1 | Pure disposable/cache | NONE | SAFE_TO_DELETE | HIGH | 100% DISPOSABLE, positive evidence, HIGH |
| 2 | Pure critical/system | CRITICAL | DO_NOT_DELETE | HIGH | Tier-0 protected path |
| 3 | Mixed disposable + critical | HIGH | DO_NOT_DELETE | HIGH | R1 hard rule |
| 4 | 95% disposable + 5% UNKNOWN | LOW | REVIEW_FIRST | MEDIUM | R3 strict: any UNKNOWN blocks; majority-safe insufficient |
| 5 | 60% cache + 40% UNKNOWN | UNKNOWN | REVIEW_FIRST | LOW | Large unknown; cannot assess |
| 6 | Personal docs + app data | NONE | REVIEW_FIRST | MEDIUM | R2; user consent required |
| 7 | `C:\Users` (user-profile mix) | NONE | REVIEW_FIRST | MEDIUM | R2; ~5% UNKNOWN; not Tier 0 |
| 8 | `Downloads` | LOW | REVIEW_FIRST | HIGH | Policy; per-file assessments vary |

Ex6 confidence footnote: MEDIUM is the approved-source value (reverted 2026-09-13). The
source's Ex4 (5% unknown) / Ex6 (0% unknown) / Ex7 (~5% unknown) all carry MEDIUM, so
folder-level REVIEW_FIRST confidence does NOT track unknown-byte share — it reflects
certainty of ONE aggregate verdict over a heterogeneous composition (Ex6 spans docs +
config + temp). Folder-level HIGH is reserved for near-homogeneous or single-policy
verdicts (Ex1/Ex2/Ex8/R1). See §24 risk item 8.

Row 7 footnote (corrected 2026-09-14): `C:\Users` is a user-profile mix —
R2-derived REVIEW_FIRST/MEDIUM, matching the approved source. It is NOT a Tier-0
critical root (`kb.classify("C:\Users")` → `unknown`; only `C:\Users\<profile>`
resolves Tier 1 `user_profile`, USER_VALUE bucket). The legacy `safety.py` CAUTION
rating is a guard-layer risk color, not a composition verdict; per-item review
authority (I10) is preserved. See §24 risk item 9.

Examples 4: the 5% UNKNOWN drives the ceiling via R3 (`UNKNOWN_BLOCK = 0.0`). Constraint
example (documented): 100 GB folder with 95 GB cache + 5 GB personal documents ⇒
REVIEW_FIRST (R2), never SAFE_TO_DELETE.

## 12. Recommendation Model (Phases 5)

`SAFE_TO_DELETE` requires:

```
Known disposable purpose
+ high-confidence classification
+ not protected
+ no meaningful user-value concern
+ no known dependency
+ inside deletion boundary
= eligible for SAFE_TO_DELETE
```

(*Conceptual model — not necessarily a single boolean formula.*) Absence of a danger
classification is NOT sufficient. Positive-evidence categories: disposable temporary
files, known application caches, known disposable installers, generated artifacts,
safe-to-remove logs, known temporary system/application data, other explicitly defined
high-confidence categories. **Downloads policy:** folder = LOW/REVIEW_FIRST/HIGH;
individual files vary (installer ⇒ SAFE_TO_DELETE/HIGH; personal doc ⇒ REVIEW_FIRST/HIGH;
unknown file ⇒ UNKNOWN/REVIEW_FIRST/LOW).

**Item vs folder authority (I10):** SAFE_TO_DELETE is evaluated per item; the
folder-derived recommendation gates only the folder-as-a-whole delete.

## 13. CLI / Web / Desktop Strategy

- **CLI** (Rich, optional dep): scan, analyze, export, gated delete.
- **Web** (FastAPI, optional interface, decision D3): scan + assessment views + export + gated delete.
- **Desktop** (PySide6): primary rich experience; core in-process; no FastAPI/browser dependency.
- Core features identical across all three; only presentation differs.

**Delete UI behavior (default):** SAFE_TO_DELETE ⇒ delete enabled. REVIEW_FIRST ⇒ normal
delete disabled, Review/Details provided. KEEP and DO_NOT_DELETE ⇒ delete disabled.
REVIEW_FIRST items never enter the normal delete workflow. Explicit override = future
feature, out of scope.

## 14. Desktop Technology Decision

**APPROVED: PySide6 (Qt6).** Rationale: modern UI, reasonable resource usage,
Python-native, strong Windows desktop experience, maintainability. Constraints: core
UI-independent; no FastAPI/browser in desktop. ADR comparison (Phase 9): PySide6
(selected) vs PyQt6 (GPL/commercial licensing) vs Tkinter (stdlib, limited) vs
Tauri/Electron (web shell, heavier).

## 15. Performance Strategy

No universal guarantee (e.g., "500K files < 30 s"). Reproducible benchmark environment;
representative datasets (synthetic + real); metrics: files/second, total scan time,
analysis time, composition time, peak memory, retained records, cancellation
responsiveness. Numerical goals = engineering targets based on measured results.

Performance is tracked continuously: the **Phase 1 smoke benchmark** (50k fixture)
provides the baseline and is re-run and logged **at the end of every phase** (phase-a
>20% regression vs baseline is a **phase-closing gate**, not informational). Phase 8 is
the authoritative detailed profiling.

## 16. Internationalization (Phase 7)

Single-source `locales/{en,es}.json` replacing the `i18n.py` dict (decision D2). Core
avoids hardcoded display strings; reason strings are rule-id + localized template.
Web + Desktop consume the same locale files.

## 17. Export Strategy (Phase 6)

Schema v2 adds `system_impact`, `recommendation`, `confidence`, `reason` (+
`analysis_state` markers). Formats CSV/HTML/JSON, deterministic, `schema_version=2`.

## 18. Versioning

**v3.0.0** (decisions D1). v2.x = existing CLI/Web architecture. v3.0.0 = new safety
engine, per-file analysis, improved recommendations, desktop product, packaging, and a
breaking API data model. No silent versioning change.

**Git tags:** default = single final `v3.0.0` tag at Phase 12. **Option (not mandatory):**
pre-release tags per completed phase (`v3.0.0-alpha.1` … `v3.0.0-alpha.12`) for portfolio
visibility. If approved, it becomes the tagging convention.

## 19. Testing Strategy

Coherent, layered suites. **Deletion security** (Phase 1, `tests/test_deletion_security.py`):
inside-tree normal; traversal segments; cross-drive; case variation on Windows; symlink/
junction inside/outside (skip-with-note if privileges unavailable); trailing `..`; NUL
byte; overlong path / long-path policy (no blanket 260 cutoff); `\\?\` prefix equivalence;
canonical comparison unaffected by prefix/prefix-equivalence; scan root itself; parent of
scan root; nonexistent path; deleted/renamed-after-scan where feasible; protected Tier 0
path; empty string; spaces/special chars; unresolvable denied/deferred; internal canonical
path not leaked to user-facing output; un-prefix long-path canonical key equality.

**Safety model** (Phase 2/5): UNKNOWN never → SAFE_TO_DELETE; LOW confidence never →
SAFE_TO_DELETE; NONE/LOW impact do not imply SAFE; personal data = NONE + REVIEW_FIRST +
HIGH; critical ⇒ DO_NOT_DELETE; known disposable ⇒ SAFE; reason always present.

**Composition** (Phase 5): mixed folders; unknown; user-value; critical descendants;
large/small unknown; the 8 canonical examples; a folder with a `NOT_RESOLVABLE`
descendant cannot reach SAFE_TO_DELETE (R3 via UNKNOWN aggregation).

**Retention** (Phase 3): all accessible files analyzed; retained bounded; aggregates
include non-retained; UI never claims non-retained were skipped.

Baseline: existing tests remain green at every phase.

## 20. GitHub / Development Workflow

Fixed process (re-affirmed):

1. Before modifying: `git status`, branch, remote, user changes. Never discard user work.
2. After each tested logical change: run relevant tests → inspect diff → update docs →
   professional Conventional Commit → push only after validation.
3. Tests fail ⇒ STOP. Fix. Re-test. Continue only when green. Never push broken code.
4. Push fails ⇒ report exact error; never claim success.
5. No forced-push / destructive git to discard work. No meaningless commits.
6. Strictly sequential per phase: Phase → test → fix → validate → documentation →
   commit → push → next phase. Parallel execution is not the default.

## 21. Documentation Strategy

| Doc | Purpose | Created / updated |
|---|---|---|
| `README.md` | Public entry, quickstart, run commands, features, install | Updated each phase with user-visible changes |
| `docs/ROADMAP.md` | This master roadmap — the implementation contract | Phase 1 start; amended per phase decisions |
| `docs/SAFETY.md` | Safety model + invariants + deletion security + limitations | Phase 1 foundation (deletion security); expanded Phase 2/5 |
| `docs/ARCHITECTURE.md` | Core/CLI/Web/Desktop, module map, flows | Phase 1 scaffold (boundary + module map + baseline placeholder); expanded Phase 3/8/9/10/11 |
| `CHANGELOG.md` | Keep-a-Changelog, per phase/commit | Every phase |
| `SESSION.md` | Working log, decisions, next steps | Every session |

## 22. Complete 12-Phase Roadmap

> Each phase is implementation-ready. Estimates reconcile to §25.

### Phase 1 — Deletion Security Hardening + Safety Boundary
- **Objective:** six-condition canonical containment guard in core, API, CLI; protected-path policy; reparse safety; final revalidation.
- **Why:** current `deleter.py` uses `normpath` only — containment/root/ancestor/reparse escapes possible; all later delete UIs depend on this boundary.
- **Dependencies:** none (starts on v2.0.0; 81-test baseline).
- **Files likely affected:** `folder_analyzer/security_guard.py`, `folder_analyzer/audit.py`, `folder_analyzer/deleter.py`, `api/routes.py`, `api/models.py`, CLI (`__main__.py`), `folder_analyzer/i18n.py`, `tests/test_deletion_security.py`, `benchmarks/`, `docs/ROADMAP.md`, `docs/SAFETY.md`, `docs/ARCHITECTURE.md`.
- **Scope (strictly limited):** containment; canonical path handling (incl. long-path policy); root/ancestor protection; symlink/junction/reparse handling; protected-path validation; deletion-time revalidation; API + CLI deletion boundary; deletion audit log; security regression tests; smoke benchmark + baseline; docs foundation. No assessment model, no recommendation engine.
- **Tests:** full §19 deletion-security list; existing 81 stay green.
- **Manual validation:** live API checks; CLI delete on throwaway tree; root/ancestor/outside/reparse denial; missing ⇒ `total_deleted == 0`.
- **Documentation:** SAFETY.md deletion-security foundation; ROADMAP.md; ARCHITECTURE.md scaffold.
- **Git strategy:** Conventional Commits per logical unit, then push.
- **Acceptance criteria:** all §19 deletion-security tests pass; 81 baseline green; API and CLI share the same guard; smoke benchmark baseline recorded; SAFETY.md honest about TOCTOU; deleted/denied attempts audit-logged.
- **Risks:** symlink/junction test flakiness (privileges); `realpath` Windows behavior; `send2trash` platform quirks.
- **Estimated effort:** 12–20 h (+4–6 h one-time 50k fixture from §15 baseline requirement, included).
- **Uncertainty:** Medium–High (Windows FS edge cases).

### Phase 2 — Safety Engine Model
- **Objective:** three-axis domain model (System Impact / Recommendation / Confidence / Reason) + invariant guards (prohibited chains I1–I3, I9).
- **Why:** Phases 3–6 emit/consume this model; exports/UI need stable types.
- **Dependencies:** none hard on Phase 1 output; order kept per approved sequence.
- **Files likely affected:** `folder_analyzer/safety.py`, `api/models.py`, `tests/test_safety_model.py`, `docs/SAFETY.md`.
- **Scope:** enums; Assessment value; invariant functions; Confidence semantics; rule evaluation deferred to Phase 5.
- **Tests:** §19 safety-model list + confidence-semantics.
- **Manual validation:** OpenAPI shows new fields; REPL sanity.
- **Documentation:** SAFETY.md model section; CHANGELOG.
- **Git strategy:** `feat(core): add safety model (Phase 2)`.
- **Acceptance criteria:** model + invariant tests pass; zero UI/API behavior change.
- **Risks:** over-engineering value objects (scope guard).
- **Estimated effort:** 5–9 h. **Uncertainty:** Low.

### Phase 3 — File Analysis & Data Model
- **Status: COMPLETE (approved scope).** Delivered: per-file Level-1 metadata
  (zero extra syscalls), DISCOVERED/ANALYZED/RETAINED states, per-folder
  `FolderAggregation` + `ScanResult`, bounded prioritized retention (configurable
  global budget 10k + per-folder cap 200, non-safe → representative → largest),
  on-demand single-folder re-analysis, 100%-analyzed invariant under eviction
  (proven by test). Implementation: `folder_analyzer/engine/models.py`,
  `engine/retention.py`, `folder_analyzer/scanner.py` (the roadmap's
  `analysis.py` was folded into `engine/`).
- **Approved re-scoping during Phase 3:** Level 2 (magic bytes ≤512 B) and Level 3
  (targeted inspection ≤4 KB) are **NOT implemented in Phase 3**; they move to
  Phase 4 where ambiguous-type resolution needs them. Classification/composition
  remain Phase 5.
- **Objective:** scanner per-file metadata; 3-level content analysis; DISCOVERED/ANALYZED/RETAINED states; aggregates over all analyzed; bounded prioritized retention.
- **Why:** recommendations/exports need file-level evidence; performance baseline needed before Phase 8.
- **Dependencies:** Phase 2 (types).
- **Files likely affected:** `folder_analyzer/scanner.py`, `folder_analyzer/analysis.py`, `folder_analyzer/models.py`, `tests/test_file_analysis.py`, `test_retention.py`, `docs/ARCHITECTURE.md`.
- **Scope:** levels 1–3 with configurable byte caps; no whole-file reads for large files; §9 retention; inaccessible-file accounting; "analyzed vs retained" distinction.
- **Tests:** §19 retention list; no huge-file read (monkeypatched open); inaccessible simulation.
- **Manual validation:** scan real folder; verify counts, states, memory.
- **Documentation:** ARCHITECTURE.md file-analysis + retention; CHANGELOG.
- **Git strategy:** `feat(core): per-file analysis and bounded retention (Phase 3)`.
- **Acceptance criteria:** caps enforced; aggregates match all analyzed; retention priority respected.
- **Risks:** sparse magic-byte coverage (graceful degradation).
- **Estimated effort:** 8–14 h. **Uncertainty:** Medium.

### Phase 4 — Knowledge Base
- **Objective:** tiered KB (Tiers 0–4; Tier 5 registry optional stub), data-driven rule-id-tagged rules; Tier 0 feeds protected-path policy.
- **Why:** recommendations/safety depend on rules; protected paths declarative.
- **Dependencies:** Phase 3 (FileRecord inputs). No functional dependency on Phase 3 until Phase 5 integration — **possible parallelization opportunity flagged; phase order unchanged** unless approved.
- **Files likely affected:** `folder_analyzer/kb/`, `tests/test_knowledge_base.py`, `docs/SAFETY.md`.
- **Scope:** Tier 0 critical (protected); Tier 1 known locations; Tier 2 common app data; Tier 3 extension table; Tier 4 high-value app rules; Tier 5 registry optional, batch-loaded once per scan, safe-empty.
- **Tests:** loading; Tier-0 matches; Downloads rule; unknown stays unknown; registry-absent path functional.
- **Manual validation:** REPL queries.
- **Documentation:** SAFETY.md protected-path provenance; CHANGELOG.
- **Git strategy:** `feat(core): tiered knowledge base (Phase 4)`.
- **Acceptance criteria:** deterministic; every rule has id + reason; registry optional proven.
- **Risks:** rule-coverage inflation (capped high-value only).
- **Estimated effort:** 6–10 h. **Uncertainty:** Medium.
- **Status: COMPLETE — approved scope delivered.** Implementation location is
  `folder_analyzer/engine/kb/` (approved deviation from `folder_analyzer/kb/` to
  sit beside the other engine modules). Commits `f41d85c` (feat), `9253a5b` (test;
  surfaced fixes: registry `_catalog()` safe-empty hardening, Tier-2 browser-before-cache
  ordering). Evidence in `tests/test_knowledge_base.py` (31 tests): tier-by-tier
  correctness; dispatch first-match-wins 0→5; Known Folder resolution + registry both
  batch once per session (counting tests); bounded-read proof on a >100 MB file
  (≤512 B L2 / ≤4 KB L3); unknown stays unknown (no Assessment/recommendation surface).
  Scanner hot path untouched (`scanner.py` byte-identical; benchmark analysis/composition
  time 0.0); six-run benchmark `1.001–1.495 s` (best run at/under the Phase-3 baseline;
  spread is machine noise — see `docs/ARCHITECTURE.md §6`). Full suite **179 passed /
  2 skipped**. KB memory footprint ~tens of KB (<100 KB), documented in ARCHITECTURE;
  RSS status carries forward from Phase 3 (+18.2%, ~1.8pp headroom, watch at Phase 5
  wiring, address at Phase 8). Dispatch reachability limits (Tier-3 extension
  short-circuits Tier 4 for mapped extensions; Ollama manifest attribution is a Level 3
  content check) documented in ARCHITECTURE §2 and the `categories.py`/`content.py`
  module docstrings.

### Phase 5 — Recommendation Engine + Folder Composition + ScanResult
- **Objective:** item-level assessment implementing I1–I3/I9 positive evidence; §11 composition (short-circuit R1–R6); integrated ScanResult.
- **Why:** the heart of v3; exports v2, Web and Desktop consume it.
- **Dependencies:** Phases 2, 3, 4.
- **Files likely affected:** `folder_analyzer/recommender.py`, `folder_analyzer/composition.py`, `ScanResult`, `api/models.py`, `tests/test_recommendation_engine.py`, `test_composition.py`, `docs/SAFETY.md`.
- **Scope:** assessment function; composition with named configurable constants; positive-evidence gate; 8 canonical examples as tests; 100 GB case; NOT_RESOLVABLE → UNKNOWN aggregation; reason strings.
- **Tests:** §19 composition + safety lists; all canonical examples; prohibited chains.
- **Manual validation:** real scans of Downloads, Temp, Users — plausibility.
- **Documentation:** SAFETY.md full model; CHANGELOG.
- **Git strategy:** `feat(core): recommendation engine and folder composition (Phase 5)`.
- **Acceptance criteria:** all invariant-example tests pass; thresholds configurable; reason always present; validation against broader/randomized real-folder corpus (not only the 8 canonical examples).
- **Risks:** threshold miscalibration = **highest-uncertainty area** (mitigated: marked provisional + configurable + corpus validation).
- **Estimated effort:** 8–14 h. **Uncertainty:** High.
- **Status: COMPLETE (2026-09-13).** Assessment + composition wired into the scan
    (`engine/classifier.py`, `engine/recommender.py`); R1-R5 short-circuits with
    named config; 8 canonical examples as tests; 100 GB case; NOT_RESOLVABLE—
    UNKNOWN aggregation; I10 authority test (item SAFE/HIGH beneath folder
    REVIEW_FIRST still guard-valid); benchmark gate alloc-peak 13.97 MiB (+16.3%
    vs corrected 4′), retained 7,400, within the 20% gate. **Uninstrumented
    wall-clock: measured 0.143 → 0.782 s (+445%) and, after the reviewer-bulleted
    close optimization ("block Phase 6 until optimized"), 0.476 s (mean, n=6,
    −39%; KB pass 8.5 → 4.7 µs/file); the residual is the I10 per-item floor and
    is a Phase 8 watch item, not a Phase-6 blocker** (§15/§22/§24-7; evidence
    `docs/ARCHITECTURE.md` §6a). Suite 313 passed / 2 skipped.

### Phase 6 — Exports v2
- **Status: COMPLETE — FORMALLY APPROVED (2026-09-14).** Verification point 1
  (composition field semantics) fixed; points 2+3 confirmed and covered.
  Commits `4b4b7a9` / `85f8fa8` / `63f8cd7` + `445738a` (fix/verify). Approval
  authorized Phase 7.
- **Objective:** export schema v2 (assessment fields + `analysis_state` markers); CSV/HTML/JSON deterministic.
- **Why:** offline consumption; stable documented schema.
- **Dependencies:** Phase 5.
- **Files likely affected:** `folder_analyzer/exporters*`, `api/models.py`, tests.
- **Scope:** schema bump; `schema_version=2`; HTML assessment columns + localized keys; JSON round-trip.
- **Delivered:** v2 exporters in `folder_analyzer/exporter.py` backed **only** by
  the collected ScanResult (zero classifier/KB calls during export — guardrail
  tested); **composition is the full recursive aggregation** (`root_composition.total_bytes
  == total_size`, fold is pure data on scan-time `FolderComposition` values — no
  engine access); `assessment` unchanged (engine folder short-circuit); JSON v2
  (top-level metrics + `root_assessment`/`root_composition` + enriched tree,
  canonical ordering); CSV/HTML v2 (Rec/Conf/Impact + localized Reason +
  Analysis State/Files Analyzed/Records Retained; top-500 sorted
  size-desc-then-path-asc, root excluded); injectable `scan_date` + canonical
  sort ⇒ byte-identical exports (SHA-256 hash-compare test, all 3 formats);
  CLI `do_scan` → `(FolderInfo, ScanResult)`; API stores `last_scan_result` and
  exports v2 (400 when analysis missing); 7 new EN/ES i18n keys;
  `uncertain` (I3 demotion key) registered EN+ES; v1 `export_*` preserved (v2
  replaces v1 at CLI/API call sites — stated decision).
- **Tests:** field presence; recursive composition across levels; deterministic
  (byte-identical); round-trip; zero-reclassification guardrail (now
  instruments the `scan_result()` fold with 0 calls); reason-key localization
  through actual CSV/HTML rows (EN+ES); item-demotion and producible-key audit;
  localization; v1 preservation. **Suite 315 → 334 passed, 2 skipped.**
- **Manual validation:** export all 3 formats from real scan.
- **Documentation:** README example; CHANGELOG.
- **Git strategy:** `feat(export): schema v2 with safety assessments (Phase 6)`.
- **Benchmark:** scan-side delta = `scan_result` fold 0.494 ms = +0.11%
  (pinned P-cores [0,1], n=1); export generation total 4.3 ms
  (JSON 2.6 / CSV 0.9 / HTML 0.8); gate alloc-peak fold+export 0.26 MiB;
  retained 7,400 @ +0%.
- **Acceptance criteria:** all fields; no CLI-export regression. **Met.**
- **Risks:** low.
- **Estimated effort:** 4–7 h. **Uncertainty:** Low.

### Phase 7 — Web UI Adaptation + i18n
- **Status: COMPLETE — submitted for acceptance; all 6 verification points
  answered with evidence (commit `09e38eb`, 2026-09-14):** new HEAD benchmark
  side-by-side with Phase 6 (t_scan 0.448/0.434 s vs 0.470 s baseline, t_fold
  0.480/0.585 ms, alloc 0.26 MiB, retained 7,400, byte-identical output); I10
  `rec` proven per-row in separate render functions + `deletable` proven a pure
  per-path guard not inherited from the folder verdict
  (`test_i10_safe_file_inside_review_first_folder_is_actionable`); new
  `retained_records_for` method (no-rename) with
  `test_retained_records_for_never_reanalyzes` (0 scandir / 0 classify on
  eviction, contrast `records_for` still re-scans);
  `test_api_serves_interpolated_reason_params` proves `{params}` interpolation
  through the real scan→API→UI path (r3_unknown, "100.0%", no `{`/`}`, ES
  parity); engine `git diff 445738a..69126c2` shows only the sanctioned
  `explain.py` re-export (classifier/recommender/kb/models/enums/retention:
  empty). Suite **357 passed, 2 skipped**; benchmark confirms **no scan-side
  impact**. Awaiting formal acceptance.
- **Objective:** web assessment columns + explanations; delete gating matrix; single-source i18n migration.
- **Why:** web must represent the safety model truthfully.
- **Dependencies:** Phases 5, 6; decisions D2 (i18n) and D3 (API/Web optional) approved.
- **Files likely affected:** `api/routes.py`, `api/models.py`, `web/index.html`, `web/js/app.js`, `web/css/style.css`, `i18n.py` → `locales/{en,es}.json`, i18n tests.
- **Scope:** delete UI matrix (§13); "analyzed vs retained" stats; explanation tooltips; full i18n migration; API delete gating reasserted.
- **Tests:** UI/API contract; i18n completeness (both locales); delete-gating at API level.
- **Manual validation:** browser walkthrough EN+ES; 28/28 API checkpoint.
- **Documentation:** README; CHANGELOG.
- **Git strategy:** `feat(web): safety-aware UI and single-source i18n (Phase 7)`.
- **Acceptance criteria:** §13 matrix; both locales complete; REVIEW_FIRST never in normal delete.
- **Risks:** medium (scope creep — controlled by matrix).
- **Estimated effort:** 6–10 h. **Uncertainty:** Medium.

### Phase 8 — Performance & Scale
- **Status: COMPLETE (delivered 2026-09-14).** Suite 369 passed / 2 skipped
  (+12). Raw smoke `t_scan` 0.309–0.311 s / export 0.3549 s on the closed
  run's fixed mask (0xc00) — **−13.6% / −7.6% vs the Phase-7 code state
re-measured on the same core pair** (the archival mask 0x3 figure was a
   retracted 2.1 s reading — corrected 2026-09-14 in ARCHITECTURE §6c: 0x3
   re-measures 0.324–0.351 s at HEAD, no P-core identity drift). KB dispatch
   2.4–2.7 µs/file, classifier 2.1–2.3 µs/file
  (Phase-5 close: 4.7). Gate alloc-peak 0.26 MiB + retained 7,400 @ +0%;
  export output byte-identical (59,862 / 7,509 / 30,081 B). Cancellation
  stops within **≈8 ms** of the request (partial `ScanResult.cancelled=True`).
  Engine files touched: `scanner.py`, `classifier.py`, `models.py`,
  `kb/__init__.py` (caching only) + `api/routes.py` cancel endpoint;
  recommender/retention/safety/KB tier tables untouched.
- **Objective:** reproducible benchmark suite (extends Phase 1 fixture/smoke) + optimization; cancellation responsiveness.
- **Why:** scale targets must be measured.
- **Dependencies:** Phase 5 (stable data pipeline); Phase 1 baseline.
- **Files likely affected:** `benchmarks/` (full suite), scanner/analysis optimizations, cancellation hooks.
- **Scope:** metrics incl. analysis/composition/cancellation; environment documented; engineering targets from measurements; chunked/batched I/O.
- **Tests:** cancellation responsiveness; memory cap; no regression on full suite.
- **Manual validation:** run benchmark suite; record baseline table.
- **Documentation:** ARCHITECTURE.md performance + smoke table; CHANGELOG.
- **Git strategy:** `perf(core): benchmark suite and scale improvements (Phase 8)`.
- **Acceptance criteria:** reproducible commands; targets recorded with environment.
- **Risks:** dataset representativeness.
- **Estimated effort:** 5–9 h. **Uncertainty:** Medium.

### Phase 9 — Desktop Architecture & Prototype
- **Objective:** PySide6 scaffold; ADR; core in-process; minimal app (pick → scan → assessment table → gated delete).
- **Why:** validates desktop direction early; proves core without FastAPI.
- **Dependencies:** Phase 8 (UX responsiveness baseline); approved PySide6.
- **Files likely affected:** `desktop_app/`, `docs/ADR-001-desktop-stack.md`, `pyproject.toml` extras.
- **Scope:** short ADR (PySide6/PyQt6/Tkinter/Tauri/Electron); runnable prototype, core only; no FastAPI in desktop.
- **Tests:** headless Qt (offscreen) smoke + controller unit tests.
- **Manual validation:** run prototype on real folder.
- **Documentation:** ADR + ARCHITECTURE.md desktop section; CHANGELOG.
- **Git strategy:** `feat(desktop): PySide6 prototype (Phase 9)`.
- **Acceptance criteria:** scans + assessments + gated delete; core in-process verified.
- **Risks:** Qt offscreen quirks.
- **Estimated effort:** 6–10 h. **Uncertainty:** Medium.

### Phase 10 — Desktop Application Complete
- **Objective:** full desktop: drill-down, reasons panel, export, settings, i18n, cancellation.
- **Why:** primary product surface; feature parity with web.
- **Dependencies:** Phase 9.
- **Files likely affected:** `desktop_app/*`, packaging hooks.
- **Scope:** defined feature checklist — no unbounded polish.
- **Tests:** model/view/controller unit tests; manual UI QA checklist.
- **Manual validation:** scripted UI walkthrough EN+ES.
- **Documentation:** README screenshots; CHANGELOG.
- **Git strategy:** `feat(desktop): complete desktop application (Phase 10)`.
- **Acceptance criteria:** checklist complete; delete matrix correct.
- **Risks:** scope creep (bounded by checklist).
- **Estimated effort:** 8–14 h. **Uncertainty:** High.

### Phase 11 — Packaging & Installer
- **Objective:** PyInstaller bundle + optional installer; wheel remains; finalize v3.0.0.
- **Why:** desktop requires end-user distribution.
- **Dependencies:** Phase 10; decision D1 (versioning).
- **Files likely affected:** `packaging/`, build scripts, README install.
- **Scope:** PySide6 bundle size; locales bundled; verify scan/analysis/delete from the built exe.
- **Tests:** smoke run of artifact; full suite from wheel.
- **Manual validation:** clean-environment install + run.
- **Documentation:** install instructions; CHANGELOG.
- **Git strategy:** `build: v3.0.0 packaging (Phase 11)`.
- **Acceptance criteria:** artifact runs standalone; locales present; delete boundary intact in bundle.
- **Risks:** PyInstaller/Qt quirks.
- **Estimated effort:** 5–9 h. **Uncertainty:** High.

### Phase 12 — Final Integration, QA & Portfolio Cleanup
- **Objective:** E2E verification across CLI/Web/Desktop; docs reconciliation; threshold revalidation; scratch cleanup; release tag.
- **Why:** ship a coherent, trustworthy v3.0.0.
- **Dependencies:** all phases.
- **Files likely affected:** docs, release tag.
- **Scope:** E2E scripted checks; full suite; both locales; export round-trip; revalidate heuristics; remove unrelated Temp scratch files; `git tag v3.0.0`.
- **Tests:** full suite + E2E on throwaway trees.
- **Manual validation:** CLI/Web/Desktop parity walkthrough.
- **Documentation:** all docs reconciled; SESSION.md updated.
- **Git strategy:** `release: v3.0.0 (Phase 12)` + tag.
- **Acceptance criteria:** all suites green; parity proven; tag clean.
- **Risks:** low.
- **Estimated effort:** 6–10 h. **Uncertainty:** Medium.

## 23. Dependencies

- **Runtime:** Python 3.10+ (current), `send2trash`, Rich (CLI only), FastAPI/uvicorn (Web only), PySide6 (Desktop only), PyInstaller (Phase 11 build only). Core depends only on stdlib + `send2trash`.
- **Sequencing:** strictly sequential. No phase starts until the previous is tested, documented, committed, pushed.
- **Decision gates:** §26 items before/in Phase 1; PySide6 approved.
- **Parallelization note (flagged, not adopted):** Phase 4 has no functional dependency on Phase 3 until Phase 5 integration; ordering unchanged unless explicitly approved.

## 24. Risks and Uncertainties

1. **Threshold calibration (Phase 5)** — heuristic values may misclassify until validated. *(Highest.)*
2. **Windows FS security edge cases (Phase 1)** — symlink/junction/reparse varies by environment/privilege; mitigated by canonical guard, degrade-not-guess, honest limits docs.
3. **TOCTOU / race conditions** — mitigated + detected mostly; complete atomicity not claimed; future hardening out of scope.
4. **Retention/analysis limits** — engineering defaults, configurable.
5. **PyInstaller/Qt quirks (Phase 11)** — real risk, dedicated phase.
6. **Registry unavailability (KB T5)** — never affects correctness.
7. **Phase-5 classification cost (+233% real wall-clock on the 50k fixture after
   close optimization; +445% pre-optimization)** — the recommendation/composition
   wiring measured **0.143 s (Phase 4) → 0.782 s (Phase 5)** uninstrumented, pinned
   P-cores (**5.5×**). At the Phase-5 close ("block Phase 6 until optimized") the scan
   hot path was restructured (folder-context tier pre-resolution, name-only fast
   paths, derived file key, frozen ScanAssessment memoization): wall **0.782 → 0.476 s
   (mean, n=6, −39%)**, KB classification pass 8.5 → 4.7 µs/file, instrumented
   alloc-peak back inside the 20% gate (13.97 MiB, +16.3%). The 50k fixture is
   adversarial (a large file share has no extension/marker, exhausting every tier);
   the residual is the I10 per-item materialization floor. Carried forward as a
   **watch item only, not a Phase-6 blocker** — residual window is a Phase 8 activity.
   **Decision (Phase 6/7 guardrail): Phases 6 (Exports v2) and 7 (Web UI) must NOT add
   per-file hot-path processing** — they consume the already-collected `ScanResult`
   (exports iterate over scan-phase products; web reads the same data) and must not
   re-scan or re-classify. Real-world scan sizes are far below the 50k stress fixture,
   and the primary optimization window
   (folder-prefix classification caching, filename-only Tier-3 decisions) is a Phase 8
   activity. Re-evaluate at every phase close; do not let this regress further.
   **Outcome (Phase 7 close):** honored — Phase 7 touched no scan hot path; the
   UI reads retained records only (`Scanner.retained_records_for`, no
   re-classification) and `/api/i18n`/`/api/scan`/`/api/folder/files` consume the
   already-collected `ScanResult`; benchmark confirms `t_fold` 0.492 ms (+0.12%)
   and output byte-identical.
8. **Example 6 confidence value — REVERTED to the approved source's MEDIUM
   (2026-09-13).** The approved source specifies `Ex6 = NONE/REVIEW_FIRST/MEDIUM`
   (aggregation: `safe_pct = 0.20`, `protected_pct = 0`, `unknown_pct = 0`,
   `user_data_pct = 0.50`; reason: "Contains a mixture of user documents, application
   data, and temporary files"). An interim commit (`d6ba116`) justified retaining HIGH
   via the confidence-independence axiom ("`unknown_pct = 0` ⇒ high byte-classification
   certainty ⇒ HIGH"). That justification does not survive the source's own
   cross-example pattern: Ex4 (95% cache + 5% unknown) = MEDIUM, Ex7 (C:\Users mix,
   unknown ≈ 5%) = MEDIUM, and Ex6 itself = MEDIUM despite `unknown_pct = 0` — LESS
   unknown content than Ex4/Ex7, yet the identical confidence. Unknown-byte share is
   therefore NOT the variable driving the source's folder-level REVIEW_FIRST confidence.
   The consistent reading: folder-level derived confidence measures certainty that ONE
   aggregate verdict adequately summarizes a HETEROGENEOUS composition (the folder's mix
   of structurally distinct content categories) — lower than byte-level classification
   certainty (§2 family_photos.zip pattern, item-level) and distinct from
   single-policy-verdict confidence (Ex8 Downloads = HIGH). Ex6 spans documents +
   app config/DB + temp — three distinct categories — hence MEDIUM, the same level as
   Ex4/Ex7. The roadmap documents NO mechanical confidence-derivation rule for the
   REVIEW_FIRST paths (§11 short-circuits specify only the SAFE constraint
   `CONFIDENCE_GATE = HIGH`); source-example confidences are authored judgments, and the
   reverted value follows the source verbatim.
   **Implementation:** `derive_folder_recommendation`'s R2 (USER_VALUE) branch now stamps
   `confidence=MEDIUM` (was HIGH), so `r2_user_value` = NONE/REVIEW_FIRST/MEDIUM, consistent
   with Ex6/Ex7. The Downloads-policy floor stays HIGH (Ex8). R1 (protected-critical) and
   R5 (SAFE) remain HIGH. Item-level classification confidence is unaffected (§2).
   This reversion supersedes the interim HIGH-correction rationale in `d6ba116`.
9. **Example 7 recommendation — CORRECTED from DO_NOT_DELETE/HIGH to the source's
   REVIEW_FIRST/MEDIUM (2026-09-14).** The §11 row previously read `C:\Users → HIGH /
   DO_NOT_DELETE / HIGH — "Protected; profiles + app data"`, a composition hard block
   that (a) contradicts the approved source (`C:\Users\David`: every area REVIEW_FIRST;
   `protected_pct ≈ 0`, `unknown_pct ≈ 0.05`; Derived: REVIEW_FIRST, MEDIUM) and (b) has
   NO live code path — `kb.classify("C:\Users")` returns `unknown` (Tier-0 `_EXACT`/
   `_TREE` contain no profile root; Tier 1 matches only `C:\Users\<profile>` →
   `user_profile`, USER_VALUE bucket); folder-level derive emits REVIEW_FIRST via R2
   (`r2_user_value`) or the empty-tree branch (`r6_review_first`), both MEDIUM. No
   R1/DO_NOT_DELETE path exists. The one intentional protected Tier-1 member is
   PROGRAMDATA (`program_data` → PROTECTED_CRITICAL), pinned by test. The word
   "Protected" traces to the legacy `safety.py` `CAUTION_FOLDERS` guard color — never
   an input to `derive_folder_recommendation`. This is the SECOND source-vs-doc drift
   found (Ex6 HIGH, then Ex7 DO_NOT_DELETE); both were documentation-only, never live
   code. Row 7 + recommender docstring corrected; canonical ex7 composition test and a
   Tier-1 known-folder boundary test added; no classification code changed.

## 25. Total ETA (single authoritative figure)

| Phase | Min (h) | Max (h) |
|---|---|---|
| 1 Deletion Security | 12 | 20 |
| 2 Safety Model | 5 | 9 |
| 3 File Analysis | 8 | 14 |
| 4 Knowledge Base | 6 | 10 |
| 5 Recommendation + Composition | 8 | 14 |
| 6 Exports v2 | 4 | 7 |
| 7 Web UI + i18n | 6 | 10 |
| 8 Performance | 5 | 9 |
| 9 Desktop Prototype | 6 | 10 |
| 10 Desktop Complete | 8 | 14 |
| 11 Packaging | 5 | 9 |
| 12 Final QA | 6 | 10 |
| **TOTAL** | **79 h** | **126 h** |

- **Calendar estimate at 20 h/week:** ≈ **4–7 weeks**.
- **Single source of truth:** 79–126 h. Any other number appearing anywhere is an error.
- **Highest-uncertainty phases:** Phase 5 (recommendation/threshold calibration) and Phase 1 (Windows FS security edge cases); Phase 11 (packaging) also flagged.

## 26. Decisions Requiring Approval

**APPROVED DESIGN DIRECTIONS (no re-litigation):** three-axis safety model + REASON;
Confidence = confidence in classification; invariants I1–I10; six-condition guard;
ancestor = containment special case; `os.access` diagnostics-only; no blanket 260 limit;
long-path policy; internal vs human-readable paths; 3-state analysis; bounded retention
(no per-folder-200); 3-level content analysis; NOT_RESOLVABLE → UNKNOWN; tiered KB
(registry optional, batch-loaded); Downloads policy; delete UI matrix; short-circuit
R1–R3; core UI-independence; PySide6 in-process, no FastAPI in desktop; sequential phase
order; Phase 1 limited scope; docs strategy; testing strategy; GitHub workflow.

**PROPOSED IMPLEMENTATION DETAILS (engineering defaults, configurable, subject to
validation):** composition thresholds (0.85 / 0.10 / 0.15 / 0.0 / HIGH); retention budget
≈25k–50k records; content-analysis caps (64 KB / 64–256 KB); performance targets
(measured Phase 8); per-phase hour estimates.

**REQUIRES USER APPROVAL (genuine gates):**
- **D1.** v3.0.0 versioning (rationale §18) — or alternative baseline.
- **D2.** i18n single-source migration to `locales/{en,es}.json` in Phase 7.
- **D3.** API/Web retained as optional interface.
- **D4.** Initial heuristic thresholds as starting defaults (marked "subject to validation").
- **D5.** Authorization to begin Phase 1. **D6.** Pre-release tags option (§18) if adopted.

## 27. Explicitly Out of Scope for Now

Not implemented in this program: Phase 1 beyond the §28 scope; desktop implementation
(Phases 9–10); unrestricted file-content scanning; cloud AI; accounts/authentication;
telemetry; remote deletion; network deletion; automatic deletion without user action;
REVIEW_FIRST deletion override (future feature only); complete recognition of every
Windows application; registry-dependent classification; unnecessary third-party services.

## 28. Recommended Phase 1 Scope (executing)

Deletion containment; canonical path handling (incl. long-path policy); root/ancestor
protection; symlink/junction/reparse-point handling; protected-path validation;
deletion-time revalidation; API deletion boundary; CLI deletion boundary; **deletion
audit log**; **smoke benchmark fixture + baseline**; security regression tests; docs
foundation (`docs/ROADMAP.md`, `docs/SAFETY.md`, `docs/ARCHITECTURE.md` as scaffold).
Nothing from the assessment model, composition engine, or desktop enters Phase 1.