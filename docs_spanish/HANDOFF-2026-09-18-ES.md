# Handoff — Continuar la mejora de UX (Folder Analyzer)

**Fecha:** 2026-09-18 · **Proyecto:** Folder Analyzer v3.0.0
**Repo:** https://github.com/Darjona25-code/Folder_Analizer (branch `master`, PÚBLICO)
**Ruta local:** `C:\OPENCODE\Folder_Analyzer`
**Estado del repo:** v3.0.0 completado (12 fases), 400 tests passing / 2 skipped,
tag `v3.0.0` aplicado (2026-09-18), working tree clean.

---

## 1. Contexto de esta sesión

El usuario dice que la app "todavía le falta mucho" para usarse como herramienta real.
En esta sesión se preparó un **prompt para Claude (claude.ai)** con el objetivo de mejorar
la UX. La conversación no llegó a implementar nada: solo análisis + prompt. Siguiente
paso: debatir el plan con el usuario y ejecutar las mejoras.

## 2. Respuestas del usuario (preguntas hechas en esta sesión)

- **Uso objetivo:** Limpieza personal de su PC (Windows).
- **Superficie clave seleccionada:** Motor/CLI — pero sus quejas concretas corresponden a
  la app grafica; el prompt resultante enfoca **Desktop + Web** (ver hallazgos abajo).
  El CLI ya tiene barra de progreso Rich y muestra rutas completas.
- **Brechas percibidas (verbatim):** "UI/UX pobre, cuando hace el scan de un folder
  seleccionado no te da una barra de tiempo o de carga de lo que esta haciendo, solo te da
  el nombre del folder pero no se ve el path de donde esta guardado ese folder, todo esta
  en desorden, no se puede hacer un filtro o sort por nombre o por ninguna columna".
- **Destino del prompt:** Claude web (claude.ai).

## 3. Hallazgos verificados en el código (para el prompt)

| Problema | Dónde está en el código |
|---|---|
| Desktop sin barra de progreso (solo status bar texto; `ScanWorker` no emite señales de progreso) | `desktop_app/worker.py` (solo `finished_ok`/`failed`) + `main_window.py:253-271` |
| Web solo spinner estático; NO usa `POST /api/scan/cancel` (endpoint existe) | `web/js/app.js:186-218` |
| Desktop muestra solo NOMBRE de carpeta; path solo en tooltip | `main_window.py:338-343`, `controller.rows()` |
| Desktop ordena SIEMPRE por tamaño (`sort_folders_by_size`), sin headers clicables, sin filtros | `desktop_app/controller.py:80-86` |
| Web SÍ ordena por columnas pero sin indicador de dirección y sin filtros | `web/js/app.js:117-128, 345-369` |

## 4. Entregable de esta sesión: prompt para Claude

Prompt completo redactado en castellano (abajo, §6). Agrupa:

- **P0:** barra de progreso real (Desktop y Web) + Cancelar funcional; mostrar ruta
  completa + breadcrumb + "abrir en Explorador"; columnas ordenables en Desktop (todas,
  asc/desc); filtros por nombre/ruta, Recomendación, tamaño mínimo y riesgo (Desktop y Web).
- **P1:** botón "Borrar todo lo seguro" (SAFE_TO_DELETE + HIGH, uno a uno por el guard);
  organizar por categorías (clasificación del motor, sin re-clasificar); persistir path/
  idioma/filtros (extender `AppSettings` que hoy solo guarda idioma); estados de error/
  permisos claros.
- **P2:** polish (columnas redimensionables, avisos "hay X carpetas más", re-scan con un clic).
- **Restricciones:** guard de 6 condiciones, I1–I10, protección raíz/ancestros/CRITICAL,
  Papelera siempre, motor congelado por defecto (no tocar `engine/`, `scanner.py`,
  `safety.py`, `security_guard.py`, `deleter.py`), cero re-clasificación
  (`retained_records_for`), i18n EN+ES con paridad (hoy 127 UI + 22 reasons por idioma),
  desktop in-process (ADR-001), `pytest tests/` debe quedar ≥ 400 passing, commits
  pequeños y convencionales, docs actualizadas (README/CHANGELOG/SESSION), repo en inglés,
  NO tocar `packaging/`.

## 5. Cómo continuar en otra PC

```bash
cd /d C:\OPENCODE\Folder_Analyzer   # o el clon en la otra PC
git pull origin master
python -m pytest --tb=short          # sanidad: 400 passed / 2 skipped
```

Con la otra herramienta (Claude Code en este repo, o claude.ai adjuntando archivos):
pegar el prompt de la sección §6 y pedir el plan P0 → P1 → P2.

## 6. Prompt para Claude (copia y pega)

```
# Roles y contexto

Actúas como ingeniero sénior de software para mejorar "Folder Analyzer", un analizador de
espacio en disco para Windows cuyo propósito es ayudar a un usuario a liberar espacio de
forma SEGURA (todo borrado va a la Papelera de Reciclaje, recuperable). Es la v3.0.0, con
12 fases de desarrollo completadas, 400 tests pasando (2 omitidos) y un motor de clasificación
con reglas de seguridad estrictas. El usuario la usa para la limpieza personal de su PC.

## Arquitectura actual

- `folder_analyzer/` — Motor core 100% independiente de UI: escáner multi-hilo
  (`scanner.py`), modelo de seguridad (`engine/enums.py`, `engine/models.py`), clasificador
  (`engine/classifier.py`), base de conocimiento por niveles (`engine/kb/`), recomendador
  (`engine/recommender.py`), guard de borrado de 6 condiciones (`security_guard.py`),
  exportadores v2 (`exporter.py`), i18n single-source (`folder_analyzer/locales/{en,es}.json`).
- `desktop_app/` — App nativa PySide6: `main_window.py` (vista), `controller.py` (lógica Qt-free),
  `worker.py` (QThread de escaneo), + diálogos de detalles/export/ajustes.
- `api/` + `web/` — UI web FastAPI + frontend estático (vanilla JS, `web/js/app.js`).
- `folder_analyzer/__main__.py` + `reporter.py` — CLI con Rich.

## Problemas a resolver (UX, prioridad alta)

El usuario ya tiene instalada la app y le falta muchísimo para que sirva de herramienta real
de limpieza. Quejas concretas y verificadas en el código:

1. **Sin feedback de progreso durante el escaneo.**
   - Desktop: `worker.py` solo emite `finished_ok`/`failed`; no hay señal de progreso.
     Durante el scan solo aparece un mensaje estático en la status bar
     (`main_window.py:253-271`). No se ve ni %, ni cantidad de archivos/carpetas, ni
     tiempo transcurrido.
   - Web: `app.js:186-218` muestra un overlay spinner estático ("Escaneando..."), sin
     progreso y SIN usar el endpoint de cancelación que YA existe (`POST /api/scan/cancel`).
   → Objetivo: barra de progreso real en ambas superficies (archivos/carpetas procesados,
   %, tamaño acumulado, tiempo, botón Cancelar visible y funcional). En Desktop, emitir
   señales de progreso desde `ScanWorker` (el core `Scanner` ya cuenta archivos; exponer un
   callback/signals sin romper la API actual).

2. **Las carpetas solo muestran su NOMBRE, no su ruta.**
   - Desktop: la columna principal muestra `row["name"]`; el path completo solo está en un
     tooltip (`main_window.py:338-343`). El usuario no sabe de dónde viene cada carpeta.
   - Web: `app.js:395` igual (nombre + tooltip).
   → Objetivo: mostrar la ruta completa de la carpeta escaneada, de cada fila y breadcrumb
   en el drill-down; permitir copiar la ruta con un clic y "abrir en el Explorador".

3. **Todo está desordenado; sin ordenar ni filtrar por columnas.**
   - Desktop: `controller.rows()` ordena SIEMPRE por tamaño (`sort_folders_by_size`); el
     `QTableWidget` no tiene cabeceras clicables ni dirección asc/desc, y NO hay ningún
     filtro/búsqueda.
   - Web: hay orden por columnas (`app.js:117-128, 345-369`) pero sin indicador de
     dirección, y tampoco hay filtros.
   → Objetivo: en Desktop, cabeceras de columna clicables y ordenables (asc/desc) sobre
   TODAS las columnas (Carpeta, Tamaño, Archivos, Recomendación, Confianza, Impacto).
   En ambas: campo de búsqueda/filtro por nombre o ruta, y filtros por Recomendación
   (Seguro / Revisar / Conservar), por tamaño mínimo (ej: ocultar < 10 MB) y por riesgo.
   Ordenar y filtrar de forma estable y determinista, funcionando también en el drill-down
   de archivos.

## Objetivo de producto (para que sirva de verdad en la limpieza diaria)

Además de lo anterior, prioriza estas mejoras de valor para el caso de uso personal:

- **Acción "Borrar todo lo seguro"**: un botón/resumen agregado que liste las carpetas
  (y archivos) marcados `SAFE_TO_DELETE` con confianza HIGH, muestre cuánto espacio
  liberaría en total y, tras confirmación explícita, los elimine UNO A UNO pasando por el
  mismo guard de seguridad (nunca ahorrar validaciones). Con deshacer/revisión previa.
- **Organización por categorías**: agrupar la vista por tipo (cachés del navegador,
  temporales, instaladores, etc.) usando la clasificación que YA produce el motor
  (`assessment.reason_key` / `detected_category` / `composition`) — sin re-clasificar nada.
- **Persistencia de sesión**: recordar el último path escaneado, idioma y filtros usados
  (en Desktop ya hay `AppSettings` para el idioma; extiéndelo con cuidado).
- **Estados claros**: avisos de carpetas sin permisos, "hay X carpetas más", vuelta a
  escanear con un click, y que el PANEL de detalles muestre también la ruta completa.

## Restricciones INVIOLABLES (no las rompas nunca)

- **Seguridad de borrado**: todo borrado pasa por `validar → confirmar → revalidar →
  Papelera`. Nunca elimines o debilites: guard de 6 condiciones (`security_guard.py`),
  invariantes I1–I10, la regla I10 (un archivo SAFE_TO_DELETE dentro de una carpeta
  REVIEW_FIRST sigue siendo accionable individualmente), protección de raíz de escaneo,
  ancestros y rutas CRITICAL. Nada se borra de forma permanente.
- **Motor congelado por defecto**: no modifiques `folder_analyzer/engine/`, `scanner.py`,
  `safety.py`, `security_guard.py`, `deleter.py` salvo necesidad JUSTIFICADA y propuesta
  previa por escrito. Prefiere soluciones de UI/controller.
- **Cero re-clasificación en UI**: el drill-down consume SOLO `Scanner.retained_records_for`
  (nunca re-escanees ni re-clasifiques desde la vista).
- **i18n single-source**: CUALQUIER texto nuevo en la UI debe agregarse a
  `locales/en.json` Y `locales/es.json` con paridad exacta de claves (tests de
  `tests/test_locales.py` lo verifican; hoy 127 claves de UI y 22 de reasons por idioma).
- **Desktop consume el core in-process (ADR-001)**: no montar FastAPI dentro del desktop.
- **Calidad**: la suite `pytest tests/` debe seguir en 400 passed / 2 skipped (ó 400+pasa
  con los NUEVOS tests que agregues para cada mejora). No hagas commits rotos. Las
  regresiones de rendimiento de escaneo >20% son bloqueantes.

## Flujo de trabajo esperado

1. Lee los archivos clave ANTES de proponer nada: `README.md`, `SESSION.md`,
   `desktop_app/main_window.py`, `desktop_app/controller.py`, `desktop_app/worker.py`,
   `web/js/app.js`, `web/index.html`, `api/routes.py`, `api/models.py`,
   `folder_analyzer/locales/en.json`, `es.json`, y la estructura de `tests/`.
   (Si no se te adjuntaron, pídelos explícitamente, file por file.)
2. Investiga cómo funciona hoy el escáner, la señal de cancelación (`ScanCancellation`),
   las filas (`controller.rows`/`file_rows`) y los tests existentes de desktop/web
   (`tests/test_desktop_*.py`, `tests/test_web_assets.py`, `tests/test_api.py`) para
   imitar las convenciones y no romper el contrato.
3. Propone un PLAN concreto, priorizado y por pasos PEQUEÑOS y verificables
   (P0 = progreso/ruta/orden/filtros; P1 = "borrar todo lo seguro" + categorías;
   P2 = polish). Hazme preguntas si algo no está claro o hay tradeoffs.
4. Implementa paso a paso: cambios mínimos, test tras cada cambio (agrega tests que cubran
   la nueva función), y al final corre la suite completa y reporta el conteo exacto.
5. No toques `packaging/` ni el instalador salvo que se pida explícitamente.

## Entregable final

Describe el estado ANTES vs DESPUÉS de cada mejora, los archivos modificados/creados, los
tests nuevos, el resultado de `pytest tests/`, y qué queda pendiente.
```

---

## 7. Pendiente / próximos pasos

1. Debatir el plan con el usuario (¿prioriza Desktop o Web? ¿qué features añadir al P1/P2?).
2. Ejecutar las mejoras: P0 primero (progreso + ruta + orden/filtros Desktop y Web).
3. Recordatorio: guardar este handoff en el repo solo si el usuario lo decide (docs_spanish
   es material informativo en español, fuera del contenido inglés del repo; si se sube,
   es bajo `docs_spanish/` como los anteriores).