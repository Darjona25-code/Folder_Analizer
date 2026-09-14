"""Bilingual support (EN/ES) for Folder Analyzer."""

STRINGS = {
    "en": {
        "app_title": "Folder Analyzer",
        "language_prompt": "Select language:",
        "lang_en": "[1] English",
        "lang_es": "[2] Espanol",
        "tagline": "Scan any drive or folder, view sizes, and safely free disk space.",
        "scan_path_prompt": "Enter path to scan (default: C:\\): ",
        "scanning": "Scanning {path}",
        "scan_complete": "Scan complete!",
        "scan_error": "Error scanning {path}: {error}",
        "permission_denied": "Access denied: {path}",
        "files_scanned": "{count} files scanned",
        "folders_scanned": "{count} folders scanned",

        "top_folders": "Top {n} Largest Folders",
        "col_rank": "#",
        "col_folder": "Folder",
        "col_size": "Size",
        "col_risk": "Risk",
        "col_files": "Files",

        "risk_critical": "CRITICAL",
        "risk_caution": "CAUTION",
        "risk_safe": "SAFE",

        "treemap_title": "Disk Usage Treemap",
        "treemap_total": "Total: {size}",

        "menu_title": "What would you like to do?",
        "menu_details": "View details of a folder",
        "menu_delete": "Mark folders for deletion",
        "menu_export": "Export report",
        "menu_quit": "Quit",

        "select_folder_num": "Enter folder number (or 0 to go back): ",
        "folder_details": "Details for: {path}",
        "subfolders": "Subfolders:",
        "total_size": "Total size: {size}",
        "total_files": "Total files: {count}",
        "parent_folder": "[..] Back to parent",

        "delete_title": "Folders marked for deletion:",
        "delete_prompt_hint": "Enter folder numbers to mark for deletion (comma-separated, e.g. 1,3,5)",
        "delete_confirm": "Are you sure you want to send these to Recycle Bin? (yes/no): ",
        "delete_blocked": "BLOCKED: Cannot delete critical system folder: {path}",
        "delete_root_blocked": "BLOCKED: Cannot delete the scanned root folder: {path}",
        "delete_blocked_containment": "BLOCKED: Cannot delete outside the scanned folder: {path}",
        "delete_unresolvable": "Cannot safely validate path (not deleted): {path} - {reason}",
        "delete_missing": "Path not found: {path}",
        "delete_success": "Sent to Recycle Bin: {path} ({size})",
        "delete_failed": "Failed to delete: {path} - {error}",
        "delete_cancelled": "Deletion cancelled.",
        "delete_no_folders": "No folders marked for deletion.",
        "delete_warning_program": "Warning: This is a program/system folder.",
        "deleted_count": "Deleted {count} folder(s).",

        "export_title": "Export format:",
        "export_json": "[1] JSON",
        "export_csv": "[2] CSV",
        "export_html": "[3] HTML",
        "export_prompt": "Select format: ",
        "export_filename": "Filename (without extension): ",
        "export_success": "Report exported to: {path}",
        "export_failed": "Export failed: {error}",
        "col_subfolders": "Subfolders",
        "col_distribution": "Distribution",
        "files_count": "{count} files",
        "folders_count": "{count} folders",
        "export_csv_size_bytes": "Size (bytes)",
        "export_csv_size_human": "Size (human)",
        "col_recommendation": "Recommendation",
        "col_confidence": "Confidence",
        "col_impact": "Impact",
        "col_reason": "Reason",
        "col_analysis_state": "Analysis State",
        "col_files_analyzed": "Files Analyzed",
        "col_records_retained": "Records Retained",

        "enter_number": "Please enter a valid number.",
        "goodbye": "Goodbye!",
    },
    "es": {
        "app_title": "Analizador de Carpetas",
        "language_prompt": "Seleccione idioma:",
        "lang_en": "[1] English",
        "lang_es": "[2] Espanol",
        "tagline": "Analiza cualquier unidad o carpeta, consulta tamanos y libera espacio de forma segura.",
        "scan_path_prompt": "Ingrese la ruta a analizar (default: C:\\): ",
        "scanning": "Analizando {path}",
        "scan_complete": "Analisis completado!",
        "scan_error": "Error al analizar {path}: {error}",
        "permission_denied": "Acceso denegado: {path}",
        "files_scanned": "{count} archivos analizados",
        "folders_scanned": "{count} carpetas analizadas",

        "top_folders": "Top {n} Carpetas Mas Grandes",
        "col_rank": "#",
        "col_folder": "Carpeta",
        "col_size": "Tamano",
        "col_risk": "Riesgo",
        "col_files": "Archivos",

        "risk_critical": "CRITICO",
        "risk_caution": "PRECAUCION",
        "risk_safe": "SEGURO",

        "treemap_title": "Mapa de Uso de Disco",
        "treemap_total": "Total: {size}",

        "menu_title": "Que desea hacer?",
        "menu_details": "Ver detalles de una carpeta",
        "menu_delete": "Marcar carpetas para eliminar",
        "menu_export": "Exportar reporte",
        "menu_quit": "Salir",

        "select_folder_num": "Ingrese numero de carpeta (o 0 para volver): ",
        "folder_details": "Detalles de: {path}",
        "subfolders": "Subcarpetas:",
        "total_size": "Tamano total: {size}",
        "total_files": "Total de archivos: {count}",
        "parent_folder": "[..] Volver a carpeta padre",

        "delete_title": "Carpetas marcadas para eliminar:",
        "delete_prompt_hint": "Ingrese los numeros de las carpetas a eliminar (separados por coma, ej. 1,3,5)",
        "delete_confirm": "Esta seguro de enviar esto a la Papelera de Reciclaje? (si/no): ",
        "delete_blocked": "BLOQUEADO: No se puede eliminar carpeta critica del sistema: {path}",
        "delete_root_blocked": "BLOQUEADO: No se puede eliminar la carpeta raiz analizada: {path}",
        "delete_blocked_containment": "BLOQUEADO: No se puede eliminar fuera de la carpeta analizada: {path}",
        "delete_unresolvable": "No se puede validar la ruta de forma segura (no eliminada): {path} - {reason}",
        "delete_missing": "Ruta no encontrada: {path}",
        "delete_success": "Enviado a Papelera de Reciclaje: {path} ({size})",
        "delete_failed": "Error al eliminar: {path} - {error}",
        "delete_cancelled": "Eliminacion cancelada.",
        "delete_no_folders": "No hay carpetas marcadas para eliminar.",
        "delete_warning_program": "Advertencia: Esta es una carpeta de programa/sistema.",
        "deleted_count": "Eliminadas {count} carpeta(s).",

        "export_title": "Formato de exportacion:",
        "export_json": "[1] JSON",
        "export_csv": "[2] CSV",
        "export_html": "[3] HTML",
        "export_prompt": "Seleccione formato: ",
        "export_filename": "Nombre de archivo (sin extension): ",
        "export_success": "Reporte exportado a: {path}",
        "export_failed": "Error en exportacion: {error}",
        "col_subfolders": "Subcarpetas",
        "col_distribution": "Distribucion",
        "files_count": "{count} archivos",
        "folders_count": "{count} carpetas",
        "export_csv_size_bytes": "Tamano (bytes)",
        "export_csv_size_human": "Tamano (legible)",
        "col_recommendation": "Recomendacion",
        "col_confidence": "Confianza",
        "col_impact": "Impacto",
        "col_reason": "Motivo",
        "col_analysis_state": "Estado de analisis",
        "col_files_analyzed": "Archivos analizados",
        "col_records_retained": "Registros conservados",

        "enter_number": "Por favor ingrese un numero valido.",
        "goodbye": "Hasta luego!",
    },
}


class I18n:
    def __init__(self, lang: str = "en"):
        if lang not in STRINGS:
            lang = "en"
        self.lang = lang

    def t(self, key: str, **kwargs) -> str:
        text = STRINGS.get(self.lang, STRINGS["en"]).get(key, key)
        if kwargs:
            return text.format(**kwargs)
        return text

    def set_lang(self, lang: str):
        if lang in STRINGS:
            self.lang = lang
