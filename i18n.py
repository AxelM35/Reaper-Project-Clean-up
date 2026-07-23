"""Minimal internationalization for Reaper Project Cleaner.

A small dict-based lookup rather than a full gettext/babel setup, sized to
match the app: two supported languages (English, French), no plural rules,
no runtime locale detection. Changing the language takes effect on next
launch (see the "settings_restart_notice" string) rather than re-labelling
every already-built widget live.
"""

SUPPORTED_LANGUAGES = ("en", "fr")

STRINGS = {
    "window_title": {
        "en": "Reaper Project Cleaner - Clean and Archive Unused Audio Files",
        "fr": "Reaper Project Cleaner - Nettoyer et archiver les fichiers audio inutilisés",
    },
    "path_placeholder": {
        "en": "Select Project Root Folder...",
        "fr": "Choisir le dossier racine du projet...",
    },
    "scan_folder": {"en": "1. SCAN FOLDER", "fr": "1. SCANNER LE DOSSIER"},
    "find_unused": {"en": "2. FIND UNUSED", "fr": "2. TROUVER LES INUTILISÉS"},
    "archive_selected": {"en": "3. ARCHIVE SELECTED", "fr": "3. ARCHIVER LA SÉLECTION"},
    "undo_last_archive": {"en": "↩ UNDO LAST ARCHIVE", "fr": "↩ ANNULER LE DERNIER ARCHIVAGE"},
    "settings_button": {"en": "⚙ Settings", "fr": "⚙ Paramètres"},

    "projects_found": {"en": "PROJECTS FOUND", "fr": "PROJETS TROUVÉS"},
    "unused_files": {"en": "UNUSED FILES", "fr": "FICHIERS INUTILISÉS"},
    "sort_name": {"en": "Sort Name", "fr": "Trier Nom"},
    "sort_size": {"en": "Sort Size", "fr": "Trier Taille"},
    "select_rpp_placeholder": {"en": "Select .rpp to analyze", "fr": "Sélectionner les .rpp à analyser"},
    "select_files_placeholder": {"en": "Select files to archive", "fr": "Sélectionner les fichiers à archiver"},

    "status_ready": {"en": "Ready", "fr": "Prêt"},
    "status_found_projects": {"en": "Found {n} project files.", "fr": "{n} fichiers projet trouvés."},
    "status_analyzing": {"en": "Analyzing for unused audio files...", "fr": "Analyse des fichiers audio inutilisés..."},
    "status_analysis_complete": {
        "en": "Analysis Complete. Found {n} unused files.",
        "fr": "Analyse terminée. {n} fichiers inutilisés trouvés.",
    },
    "ambiguous_button": {"en": "⚠ Ambiguous files: {n}", "fr": "⚠ Fichiers ambigus : {n}"},
    "ambiguous_button_na": {"en": "⚠ Ambiguous files: n/a", "fr": "⚠ Fichiers ambigus : n/a"},
    "ambiguous_banner_msg": {
        "en": "⚠ {n} ambiguous file(s) found - excluded from archiving until reviewed.",
        "fr": "⚠ {n} fichier(s) ambigu(s) détecté(s) - exclus de l'archivage tant qu'ils ne sont pas vérifiés.",
    },
    "ambiguous_review_button": {"en": "Review", "fr": "Vérifier"},

    "selection_summary": {"en": "{count} selected · {size:.1f} MB", "fr": "{count} sélectionné(s) · {size:.1f} Mo"},

    "confirm_archive_title": {"en": "Confirm Archive", "fr": "Confirmer l'archivage"},
    "confirm_archive_msg": {
        "en": "Are you sure you want to move {n} files to the Archive folder?",
        "fr": "Confirmer le déplacement de {n} fichiers vers le dossier d'archive ?",
    },
    "archive_success_title": {"en": "Success", "fr": "Succès"},
    "archive_success_msg": {
        "en": "Archived {count} files.\nErrors: {errors}\n\nLocation: {location}",
        "fr": "{count} fichiers archivés.\nErreurs : {errors}\n\nEmplacement : {location}",
    },

    "confirm_undo_title": {"en": "Confirm Undo", "fr": "Confirmer l'annulation"},
    "confirm_undo_msg": {
        "en": "Restore the files from the last archive operation to their original location?",
        "fr": "Restaurer à leur emplacement d'origine les fichiers du dernier archivage ?",
    },
    "confirm_undo_msg_detailed": {
        "en": "Restore {n} file(s) from the archive performed on {timestamp}?\n\n{files}",
        "fr": "Restaurer {n} fichier(s) de l'archivage effectué le {timestamp} ?\n\n{files}",
    },
    "and_n_more": {"en": "… and {n} more", "fr": "… et {n} de plus"},
    "undo_complete_title": {"en": "Undo Complete", "fr": "Annulation terminée"},
    "undo_complete_msg": {
        "en": "Restored {restored} files.\nErrors: {errors}",
        "fr": "{restored} fichiers restaurés.\nErreurs : {errors}",
    },

    "ambiguous_window_title": {
        "en": "Ambiguous Files - Excluded by the Safety Net",
        "fr": "Fichiers ambigus - Exclus par le filet de sécurité",
    },
    "ambiguous_window_explanation": {
        "en": (
            "These audio files were NOT proposed for archiving because their filename\n"
            "matches an unresolved FILE reference in a scanned project (safety net).\n"
            "They might genuinely be in use via a path this tool could not verify\n"
            "(e.g. a REAPER media search path), or they might truly be unused.\n"
            "Review them manually before deleting or moving them yourself."
        ),
        "fr": (
            "Ces fichiers audio n'ont PAS été proposés à l'archivage car leur nom\n"
            "correspond à une référence FILE non résolue d'un projet scanné (filet de\n"
            "sécurité). Ils sont peut-être réellement utilisés via un chemin que cet\n"
            "outil n'a pas pu vérifier (ex. un chemin de recherche média REAPER), ou\n"
            "peut-être réellement inutilisés. À vérifier manuellement avant de les\n"
            "déplacer ou de les supprimer vous-même."
        ),
    },
    "ambiguous_none_title": {"en": "Ambiguous Files", "fr": "Fichiers ambigus"},
    "ambiguous_none_msg": {
        "en": "No ambiguous files. Every audio file found is either a confirmed reference or a confirmed unused file.",
        "fr": "Aucun fichier ambigu. Chaque fichier audio trouvé est soit confirmé utilisé, soit confirmé inutilisé.",
    },

    "settings_window_title": {"en": "Settings", "fr": "Paramètres"},
    "settings_language_label": {"en": "Language (restart required)", "fr": "Langue (redémarrage requis)"},
    "settings_extensions_label": {
        "en": "Audio extensions to scan (comma-separated)",
        "fr": "Extensions audio à scanner (séparées par des virgules)",
    },
    "settings_folders_label": {
        "en": "Extra media search folders (like REAPER's own media search path)",
        "fr": "Dossiers de recherche média supplémentaires (équivalent du media search path de REAPER)",
    },
    "settings_add_folder": {"en": "Add Folder...", "fr": "Ajouter un dossier..."},
    "settings_remove": {"en": "Remove", "fr": "Retirer"},
    "settings_save": {"en": "Save", "fr": "Enregistrer"},
    "settings_saved_title": {"en": "Settings Saved", "fr": "Paramètres enregistrés"},
    "settings_saved_msg": {
        "en": "Settings saved. Restart the app for a language change to take effect.",
        "fr": "Paramètres enregistrés. Redémarrez l'application pour appliquer un changement de langue.",
    },
}


def t(key, lang="en", **kwargs):
    """Translate `key` into `lang`, falling back to English then the key itself."""
    entry = STRINGS.get(key, {})
    text = entry.get(lang) or entry.get("en") or key
    return text.format(**kwargs) if kwargs else text
