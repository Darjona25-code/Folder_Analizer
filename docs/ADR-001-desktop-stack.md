# ADR-001 — Desktop UI stack: PySide6

- Status: **Accepted** (2026-09-15)
- Supersedes: nothing — first ADR for the desktop direction
- Source of truth: `docs/ROADMAP.md` §14 (decision **APPROVED: PySide6 (Qt6)**) and §22 (Phase 9 charter). This ADR is the Phase 9 **record** of that already-approved choice, not a re-litigation.

## Context

Folder Analyzer ships one UI-independent core (`folder_analyzer/`) consumed by
CLI (Rich), Web (FastAPI + browser JS/CSS), and a native Desktop app. The
desktop app must:

- consume the core **directly in-process** — no `Desktop → localhost FastAPI →
  Core` path, no embedded browser hosting the existing web UI;
- keep the core free of any desktop dependency (architecture rule: core depends
  only on stdlib + `send2trash`);
- share the single-source locale files `locales/{en,es}.json` (ui + reasons);
- run natively on Windows with a modern widget feel, reasonable resource usage,
  and a Python-native implementation path (no separate build toolchain).

## Decision

Use **PySide6 (Qt6)** for the desktop UI (`desktop_app/` package introduced in
Phase 9). Decision was locked in ROADMAP §14; this ADR records it and the
rationale.

## Alternatives considered

| Option | Compared outcome |
| --- | --- |
| **PySide6 (Qt6) — SELECTED** | Modern widgets, LGPL (permissive for this MIT project), official Qt for Python, active maintenance, strong Windows native desktop experience, pure-Python glue with no extra JS/build toolchain. Keeps core UI-independent by living outside `folder_analyzer/`. |
| PyQt6 | Equivalent Qt6 functionality but GPL/commercial dual licensing conflicts with the project's MIT posture; no functional advantage over PySide6 for this app. |
| Tkinter | Stdlib-only (no extra dependency) but dated widget set and limited styling/UX; weaker fit for the "modern rich experience" goal (ROADMAP §12/§13). |
| Tauri/Electron | Web shell — contradicts the "no browser in desktop" constraint (ROADMAP §13), heavier memory footprint, adds a Node/Rust toolchain outside the Python ecosystem. |

## Compliance constraints (binding)

1. `desktop_app/` consumes `folder_analyzer/` **in-process only**. It never
   starts a FastAPI/localhost server and never embeds a webview hosting the
   existing web UI.
2. The core keeps zero desktop dependencies: `PySide6` is a **Desktop-only**
   dependency (ROADMAP §24 runtime), declared as an **optional extra**, never a
   core `dependencies` entry. `folder_analyzer/` code must not `import` any Qt
   module.
3. Desktop i18n loads the **same** `locales/{en,es}.json` files; EN/ES parity
   stays test-enforced.
4. Deletion, item-level authority (I10), and the six-condition guard
   (`security_guard.validate_delete_target` + `revalidate` + `send2trash`) are
   the same everywhere — the desktop adds presentation only.

## Consequences

- PySide6 becomes an optional-dependency extra (`desktop`), not a core requirement.
- Headless tests run under `QT_QPA_PLATFORM=offscreen`; controller logic is
  kept Qt-free for cheap unit tests.
- The desktop entry point (`python -m desktop_app`) launches the native window;
  tests drive it offscreen.