"""Core logic for Reaper Project Cleaner: scanning, detection, archiving and undo.

Kept free of any GUI dependency (no tkinter/customtkinter) so it can be
unit tested directly.
"""

import os
import re
import shutil
import json
import datetime

AUDIO_EXTENSIONS = ('.wav', '.aif', '.aiff', '.mp3', '.ogg', '.flac', '.mid')
ARCHIVE_FOLDER_NAME = "_Reaper_Cleanup_Archive"
LOG_FILE_NAME = "archive_log.json"


def find_rpp_files(root_folder):
    """Recursively find .rpp/.rpp-bak files under root_folder.

    Returns a list of dicts: path, name, size_mb, date.
    """
    results = []
    for root, dirs, files in os.walk(root_folder):
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


def parse_used_media(rpp_paths):
    """Extract media references from a list of .rpp/.rpp-bak file paths.

    Returns (specific_used_paths, fallback_safe_names):
      - specific_used_paths: set of normalized, lowercased absolute paths
        that were resolved to a real file on disk.
      - fallback_safe_names: set of lowercased filenames whose referenced
        path could not be resolved (safety net, see README/cahier des charges).
    """
    specific_used_paths = set()
    fallback_safe_names = set()

    for rpp_path in rpp_paths:
        project_folder = os.path.dirname(rpp_path)
        try:
            with open(rpp_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except OSError:
            continue

        for m in re.findall(r'FILE "(.*?)"', content):
            m_clean = m.replace('\\', '/')
            filename = m_clean.split('/')[-1].lower()
            found_absolute = False

            if os.path.isabs(m_clean):
                if os.path.exists(m_clean):
                    specific_used_paths.add(os.path.normpath(m_clean).lower())
                    found_absolute = True
            else:
                likely_path = os.path.join(project_folder, m_clean)
                if os.path.exists(likely_path):
                    specific_used_paths.add(os.path.normpath(likely_path).lower())
                    found_absolute = True

            if not found_absolute:
                fallback_safe_names.add(filename)

    return specific_used_paths, fallback_safe_names


def find_unused_files(project_entries, specific_used_paths, fallback_safe_names,
                       audio_extensions=AUDIO_EXTENSIONS):
    """Find audio files on disk that are not referenced by the given projects.

    project_entries: iterable of (rpp_path, origin_name) for projects whose
      containing folder should be scanned for audio files.

    Returns a deduplicated list of dicts: path, name, size_mb, origin.
    """
    unused = {}
    for rpp_path, origin_name in project_entries:
        project_dir = os.path.dirname(rpp_path)
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d != ARCHIVE_FOLDER_NAME]
            for file in files:
                if not file.lower().endswith(audio_extensions):
                    continue
                full_path = os.path.join(root, file)
                norm_path = os.path.normpath(full_path).lower()

                if norm_path in specific_used_paths:
                    continue
                if file.lower() in fallback_safe_names:
                    continue

                unused[full_path] = {
                    "path": full_path,
                    "name": file,
                    "size_mb": os.path.getsize(full_path) / (1024 * 1024),
                    "origin": origin_name,
                }
    return list(unused.values())


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
