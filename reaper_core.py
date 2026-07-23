"""Core logic for Reaper Project Cleaner: scanning, detection, archiving and undo.

Kept free of any GUI dependency (no tkinter/customtkinter) so it can be
unit tested directly.
"""

import os
import re
import shutil
import json
import sys
import datetime

AUDIO_EXTENSIONS = ('.wav', '.aif', '.aiff', '.mp3', '.ogg', '.flac', '.mid')
ARCHIVE_FOLDER_NAME = "_Reaper_Cleanup_Archive"
LOG_FILE_NAME = "archive_log.json"
SETTINGS_FILE_NAME = "settings.json"


class ScanCancelled(Exception):
    """Raised by the scanning functions when `cancel_check` reports a
    user-requested cancellation. Callers (typically a GUI worker thread)
    catch this to stop early without treating it as an error."""

DEFAULT_SETTINGS = {
    "audio_extensions": list(AUDIO_EXTENSIONS),
    # User-declared media search folders, equivalent to REAPER's own
    # "media search path" (Preferences > Media): additional locations to
    # look in when a FILE reference can't be resolved relative to the
    # project or as an absolute path.
    "extra_search_folders": [],
    "language": "en",
}


def _config_dir():
    """Per-OS user config directory, so settings survive PyInstaller onefile
    runs (whose own install location is a temp folder wiped after exit)."""
    if os.name == 'nt':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Application Support')
    else:
        base = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    return os.path.join(base, 'ReaperProjectCleaner')


def _settings_path():
    return os.path.join(_config_dir(), SETTINGS_FILE_NAME)


def load_settings(path=None):
    """Load user settings, falling back to defaults for anything missing/invalid."""
    path = path or _settings_path()
    settings = dict(DEFAULT_SETTINGS)
    if not os.path.exists(path):
        return settings
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return settings
    for key in DEFAULT_SETTINGS:
        if key in data:
            settings[key] = data[key]
    return settings


def save_settings(settings, path=None):
    path = path or _settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

# REAPER's chunk serializer quotes a string with double quotes by default,
# falls back to single quotes if the value itself contains a double quote,
# and to backticks if it contains both. A FILE token is always the first
# thing on its line (possibly indented). Anchoring on line start (with a
# word boundary after FILE) avoids accidentally matching the token inside
# unrelated chunk data.
_FILE_REF_PATTERN = re.compile(
    r'^[ \t]*FILE\b\s*(?:"([^"]*)"|\'([^\']*)\'|`([^`]*)`)',
    re.MULTILINE,
)


def _extract_file_references(content):
    """Return the raw path strings referenced via FILE tokens in an .rpp file."""
    refs = []
    for match in _FILE_REF_PATTERN.finditer(content):
        value = next((g for g in match.groups() if g is not None), '')
        if value:
            refs.append(value)
    return refs


def _resolve_on_disk(path):
    """Resolve `path` to its real on-disk path, tolerating case differences.

    REAPER projects are frequently moved between Windows/macOS (case-insensitive
    filesystems) and Linux (case-sensitive), so a stored reference can differ
    in case from the actual file/folder names anywhere along the path, not
    just in the final filename. Each path segment is resolved individually.
    Returns None if no match exists at all.
    """
    if os.path.exists(path):
        return path

    normalized = os.path.normpath(path)
    drive, tail = os.path.splitdrive(normalized)
    is_absolute = tail.startswith(os.sep)
    parts = [p for p in tail.split(os.sep) if p]

    current = drive + (os.sep if is_absolute else '')
    if not current:
        # Relative path with no anchor to resolve against.
        return None

    for part in parts:
        candidate = os.path.join(current, part)
        if os.path.exists(candidate):
            current = candidate
            continue
        try:
            entries = os.listdir(current)
        except OSError:
            return None
        match = next((e for e in entries if e.lower() == part.lower()), None)
        if match is None:
            return None
        current = os.path.join(current, match)

    return current if os.path.exists(current) else None


def _search_in_folders(filename, folders):
    """Look for `filename` (case-insensitive) anywhere under any of `folders`.

    Mirrors REAPER's own media search path behaviour: if a project references
    a file only by name in a location this tool doesn't know about, the user
    can declare that location as an extra search folder instead of the file
    being flagged merely "ambiguous". Returns the first match found, or None.
    """
    target = filename.lower()
    for folder in folders:
        if not folder or not os.path.isdir(folder):
            continue
        for root, dirs, files in os.walk(folder):
            for f in files:
                if f.lower() == target:
                    return os.path.join(root, f)
    return None


def find_rpp_files(root_folder, cancel_check=None):
    """Recursively find .rpp/.rpp-bak files under root_folder.

    cancel_check: optional zero-arg callable; if it returns True, raises
      ScanCancelled instead of continuing (checked once per directory,
      so a large folder tree can be interrupted from another thread).

    Returns a list of dicts: path, name, size_mb, date.
    """
    results = []
    for root, dirs, files in os.walk(root_folder):
        if cancel_check and cancel_check():
            raise ScanCancelled()
        dirs[:] = [d for d in dirs if d != ARCHIVE_FOLDER_NAME]
        for file in files:
            if file.lower().endswith(('.rpp', '.rpp-bak')):
                full_path = os.path.join(root, file)
                results.append({
                    "path": full_path,
                    "name": file,
                    "size_mb": os.path.getsize(full_path) / (1024 * 1024),
                    "date": datetime.datetime.fromtimestamp(
                        os.path.getmtime(full_path)
                    ).strftime('%Y-%m-%d'),
                })
    return results


def parse_used_media(rpp_paths, extra_search_folders=None, cancel_check=None):
    """Extract media references from a list of .rpp/.rpp-bak file paths.

    extra_search_folders: optional list of user-declared folders (equivalent
      to REAPER's own media search path) to also check by filename when a
      reference can't be resolved relative to the project or as an absolute
      path. Resolving via these folders turns what would otherwise be an
      "ambiguous" file into a confirmed used one.
    cancel_check: optional zero-arg callable; if it returns True, raises
      ScanCancelled (checked once per project file).

    Returns (specific_used_paths, fallback_safe_names):
      - specific_used_paths: set of normalized, lowercased absolute paths
        that were resolved to a real file on disk.
      - fallback_safe_names: set of lowercased filenames whose referenced
        path could not be resolved (safety net, see README/cahier des charges).
    """
    specific_used_paths = set()
    fallback_safe_names = set()
    extra_search_folders = extra_search_folders or []

    for rpp_path in rpp_paths:
        if cancel_check and cancel_check():
            raise ScanCancelled()
        project_folder = os.path.dirname(rpp_path)
        try:
            with open(rpp_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except OSError:
            continue

        for m in _extract_file_references(content):
            m_clean = m.replace('\\', '/')
            filename = m_clean.split('/')[-1].lower()
            found_absolute = False

            if os.path.isabs(m_clean):
                resolved = _resolve_on_disk(m_clean)
            else:
                resolved = _resolve_on_disk(os.path.join(project_folder, m_clean))

            if not resolved and extra_search_folders:
                resolved = _search_in_folders(filename, extra_search_folders)

            if resolved:
                specific_used_paths.add(os.path.normpath(resolved).lower())
                found_absolute = True

            if not found_absolute:
                fallback_safe_names.add(filename)

    return specific_used_paths, fallback_safe_names


def find_unused_and_ambiguous_files(project_entries, specific_used_paths, fallback_safe_names,
                                     audio_extensions=AUDIO_EXTENSIONS, cancel_check=None):
    """Classify audio files found in the given projects' folders.

    project_entries: iterable of (rpp_path, origin_name) for projects whose
      containing folder should be scanned for audio files.
    audio_extensions: iterable of extensions (any casing, with leading dot,
      list or tuple) to treat as media - user-configurable via settings.
    cancel_check: optional zero-arg callable; if it returns True, raises
      ScanCancelled (checked once per unique folder and once per directory walked).

    Returns (unused, ambiguous), each a deduplicated list of dicts
    (path, name, size_mb, origin):
      - unused: no reference to this file was found at all (safe to archive).
      - ambiguous: excluded from `unused` only because its filename matches an
        unresolved FILE reference somewhere (the "safety net" heuristic) -
        it may or may not actually be in use. Reported separately so the
        user can review it instead of it silently vanishing from both lists.
    """
    audio_extensions = tuple(ext.lower() for ext in audio_extensions)
    unused = {}
    ambiguous = {}

    # Multiple checked projects frequently share the same folder - REAPER
    # keeps every auto-backup as a separate .rpp-bak in the project's own
    # folder (or a Backups/ subfolder), so a single real project can produce
    # dozens or hundreds of project_entries pointing at the same directory.
    # Walk each unique folder once instead of once per entry, otherwise
    # checking N backups from the same folder re-walks that folder N times.
    project_dirs = {}
    for rpp_path, origin_name in project_entries:
        project_dirs.setdefault(os.path.dirname(rpp_path), origin_name)

    for project_dir, origin_name in project_dirs.items():
        if cancel_check and cancel_check():
            raise ScanCancelled()
        for root, dirs, files in os.walk(project_dir):
            if cancel_check and cancel_check():
                raise ScanCancelled()
            dirs[:] = [d for d in dirs if d != ARCHIVE_FOLDER_NAME]
            for file in files:
                if not file.lower().endswith(audio_extensions):
                    continue
                full_path = os.path.join(root, file)
                norm_path = os.path.normpath(full_path).lower()

                if norm_path in specific_used_paths:
                    continue

                entry = {
                    "path": full_path,
                    "name": file,
                    "size_mb": os.path.getsize(full_path) / (1024 * 1024),
                    "origin": origin_name,
                }

                if file.lower() in fallback_safe_names:
                    ambiguous[full_path] = entry
                else:
                    unused[full_path] = entry

    return list(unused.values()), list(ambiguous.values())


def _log_path(root_folder):
    return os.path.join(root_folder, ARCHIVE_FOLDER_NAME, LOG_FILE_NAME)


def _load_log(root_folder):
    log_path = _log_path(root_folder)
    if not os.path.exists(log_path):
        return []
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def _save_log(root_folder, sessions):
    archive_root = os.path.join(root_folder, ARCHIVE_FOLDER_NAME)
    os.makedirs(archive_root, exist_ok=True)
    with open(_log_path(root_folder), 'w', encoding='utf-8') as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)


def has_undoable_session(root_folder):
    """Whether at least one archive session can be undone for this root folder."""
    return len(_load_log(root_folder)) > 0


def get_last_archive_session(root_folder):
    """Return the most recent archive session (timestamp + entries) without
    consuming it, so the UI can show what an undo would restore before the
    user confirms. Returns None if there is nothing to undo."""
    sessions = _load_log(root_folder)
    return sessions[-1] if sessions else None


def archive_files(files_to_move, root_folder):
    """Move given files into _Reaper_Cleanup_Archive/<project>/ and log the move.

    files_to_move: list of dicts with path, name, origin.

    Returns (moved_count, error_count, archive_root).
    """
    archive_root = os.path.join(root_folder, ARCHIVE_FOLDER_NAME)
    os.makedirs(archive_root, exist_ok=True)

    moved_count = 0
    error_count = 0
    session_entries = []

    for item in files_to_move:
        try:
            proj_folder_name = os.path.splitext(item['origin'])[0]
            target_dir = os.path.join(archive_root, proj_folder_name)
            os.makedirs(target_dir, exist_ok=True)

            dest_path = os.path.join(target_dir, item['name'])
            shutil.move(item['path'], dest_path)

            session_entries.append({
                "source": item['path'],
                "dest": dest_path,
                "name": item['name'],
                "origin": item['origin'],
            })
            moved_count += 1
        except OSError:
            error_count += 1

    if session_entries:
        sessions = _load_log(root_folder)
        sessions.append({
            "timestamp": datetime.datetime.now().isoformat(timespec='seconds'),
            "entries": session_entries,
        })
        _save_log(root_folder, sessions)

    return moved_count, error_count, archive_root


def undo_last_archive(root_folder):
    """Restore files moved during the most recent archive session.

    Entries that cannot be restored (destination missing, source path now
    occupied by a different file) are kept in the log for a later retry
    instead of being silently dropped.

    Returns (restored_count, error_count).
    """
    sessions = _load_log(root_folder)
    if not sessions:
        return 0, 0

    last_session = sessions[-1]
    remaining_entries = []
    restored_count = 0
    error_count = 0

    for entry in last_session['entries']:
        source = entry['source']
        dest = entry['dest']
        restored = False

        if os.path.exists(dest) and not os.path.exists(source):
            try:
                os.makedirs(os.path.dirname(source), exist_ok=True)
                shutil.move(dest, source)
                restored_count += 1
                restored = True
            except OSError:
                pass

        if not restored:
            error_count += 1
            remaining_entries.append(entry)

    if remaining_entries:
        last_session['entries'] = remaining_entries
        sessions[-1] = last_session
    else:
        sessions.pop()

    _save_log(root_folder, sessions)
    return restored_count, error_count
