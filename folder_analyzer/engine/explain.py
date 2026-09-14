"""Explainability foundation — localized resolution of ``reason_key`` strings (Phase 2).

This resolves only the reason keys introduced in Phase 2 (the safety-model
enum/assessment space). It follows the same pattern as ``folder_analyzer/i18n.py``
(a per-language dict + ``{param}`` interpolation) but is deliberately scoped and
does NOT migrate the existing i18n system — that full single-source migration is
Phase 7 work.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional

REASONS: Dict[str, Dict[str, str]] = {
    "en": {
        "unknown_impact": (
            "No reliable information about this item's impact was available "
            "during classification."
        ),
        "confidence_gate_promoted": (
            "Promoted to review: high confidence is required to recommend "
            "deletion; confidence was {confidence}."
        ),
        "confidence_low": (
            "Classification confidence is low; verification is required."
        ),
        "user_data": "Contains personal or user-generated data.",
        "uncertain": (
            "Impact could not be resolved with high confidence; safe deletion "
            "cannot be justified, so this item is kept for review."
        ),
        "temporary_data": "Recognized transient/temporary data.",
        "clean_system_data": (
            "Low system/user impact with no protected or user-value content "
            "detected; positive high-confidence evidence available."
        ),
        "review_before_delete": (
            "High-impact or protected content requires manual review "
            "before deletion."
        ),
        "keep": "No reliable disposability evidence; item is not disposable.",
        "do_not_delete": "Deletion of this item is not authorized.",
        # --- Phase 5 item-level classification reasons (classifier.py) ---
        "protected_critical": (
            "Protected or system-critical path; deletion is not authorized."
        ),
        "disposable_positive_evidence": (
            "Known disposable content with positive, high-confidence "
            "evidence of disposable purpose."
        ),
        "user_value": (
            "Personal/user-value content, or content the user may reasonably "
            "want; user consent is required before deletion."
        ),
        "known_non_disposable": (
            "Understood and classified, but not positively disposable."
        ),
        "not_resolvable": (
            "Cannot be safely resolved in the current runtime; treated as "
            "unknown and never deleted without review."
        ),
        # --- Phase 5 folder-level composition reasons (recommender.py) ---
        "r1_protected_critical": (
            "Protected/system-critical descendant bytes present: deletion "
            "not authorized."
        ),
        "r2_user_value": (
            "User-value descendant bytes present: manual review required."
        ),
        "downloads_policy": (
            "Known user Downloads location: folder-level deletion requires "
            "review (per-file assessments may vary; item authority I10 "
            "applies)."
        ),
        "r3_unknown": (
            "UNKNOWN descendant bytes present ({unknown_share:.1%}): any "
            "UNKNOWN blocks safe deletion (UNKNOWN_BLOCK = 0.0)."
        ),
        "r4_known_non_disposable_share": (
            "Understood-but-not-disposable share ({known_share:.1%}) exceeds "
            "REVIEW_SHARE ({review_share:.0%}); manual review required."
        ),
        "r5_safe_to_delete": (
            "Disposable share ({disposable_share:.1%}) meets SAFE_MIN_SHARE "
            "({safe_min_share:.0%}), known-non-disposable within ceiling "
            "({known_non_disposable_ceiling:.0%}), positive direct disposable "
            "evidence, high confidence."
        ),
        "r6_review_first": (
            "Composition does not meet the safe-deletion criteria; manual "
            "review required."
        ),
    },
    "es": {
        "unknown_impact": (
            "No se dispone de informacion fiable sobre el impacto de este "
            "elemento durante la clasificacion."
        ),
        "confidence_gate_promoted": (
            "Promovido a revision: se requiere confianza alta para recomendar "
            "la eliminacion; la confianza fue {confidence}."
        ),
        "confidence_low": (
            "La confianza de la clasificacion es baja; se requiere verificacion."
        ),
        "user_data": "Contiene datos personales o generados por el usuario.",
        "uncertain": (
            "No se pudo resolver el impacto con confianza alta; no se puede "
            "justificar una eliminacion segura, por lo que este elemento se "
            "conserva para revision."
        ),
        "temporary_data": "Datos transitorios/temporales reconocidos.",
        "clean_system_data": (
            "Impacto bajo de sistema/usuario sin contenido protegido ni valioso "
            "detectado; evidencia positiva de alta confianza disponible."
        ),
        "review_before_delete": (
            "Contenido de alto impacto o protegido requiere revision manual "
            "antes de eliminar."
        ),
        "keep": "Sin evidencia fiable de descarte; el elemento no es desechable.",
        "do_not_delete": "No se autoriza la eliminacion de este elemento.",
        # --- Phase 5 item-level classification reasons (Validador CF102) ---
        "protected_critical": (
            "Ruta protegida o critica para el sistema; no se autoriza la "
            "eliminacion."
        ),
        "disposable_positive_evidence": (
            "Contenido desechable conocido con evidencia positiva de alta "
            "confianza sobre su proposito desechable."
        ),
        "user_value": (
            "Contenido personal/de valor para el usuario, o que el usuario "
            "puede querer razonablemente; se requiere consentimiento antes "
            "de eliminar."
        ),
        "known_non_disposable": (
            "Comprendido y clasificado, pero no positivamente desechable."
        ),
        "not_resolvable": (
            "No se puede resolver de forma segura en el entorno actual; se "
            "trata como desconocido y nunca se elimina sin revision."
        ),
        # --- Phase 5 folder-level composition reasons (recommender.py) ---
        "r1_protected_critical": (
            "Hay bytes descendientes protegidos/criticos para el sistema: no "
            "se autoriza la eliminacion."
        ),
        "r2_user_value": (
            "Hay bytes descendientes de valor para el usuario: se requiere "
            "revision manual."
        ),
        "downloads_policy": (
            "Ubicacion conocida de descargas del usuario: la eliminacion a "
            "nivel de carpeta requiere revision (las evaluaciones por archivo "
            "pueden variar; se aplica la autoridad por elemento I10)."
        ),
        "r3_unknown": (
            "Hay bytes descendientes desconocidos ({unknown_share:.1%}): "
            "cualquier UNKNOWN bloquea la eliminacion segura "
            "(UNKNOWN_BLOCK = 0.0)."
        ),
        "r4_known_non_disposable_share": (
            "La proporcion comprendida-pero-no-desechable ({known_share:.1%}) "
            "supera REVIEW_SHARE ({review_share:.0%}); se requiere revision "
            "manual."
        ),
        "r5_safe_to_delete": (
            "La proporcion desechable ({disposable_share:.1%}) cumple "
            "SAFE_MIN_SHARE ({safe_min_share:.0%}), lo no desechable se "
            "mantiene dentro del tope ({known_non_disposable_ceiling:.0%}), "
            "hay evidencia positiva directa desechable y alta confianza."
        ),
        "r6_review_first": (
            "La composicion no cumple los criterios de eliminacion segura; se "
            "requiere revision manual."
        ),
    },
}


def resolve_reason(
    reason_key: str,
    lang: str = "en",
    params: Optional[Mapping[str, object]] = None,
) -> str:
    """Resolve a Phase 2 reason_key into localized, interpolated text.

    Unknown keys return the key itself (same fallback behavior as i18n.py).
    """
    text = REASONS.get(lang, REASONS["en"]).get(reason_key, reason_key)
    if params:
        return text.format(**params)
    return text