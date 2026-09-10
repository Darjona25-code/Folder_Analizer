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