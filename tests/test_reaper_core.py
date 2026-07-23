import json
import os

import reaper_core


def make_rpp(path, file_refs):
    """Write a minimal fake .rpp file containing the given FILE "..." references."""
    lines = ['<REAPER_PROJECT 0.1 "6.0" 0']
    for ref in file_refs:
        lines.append(f'    FILE "{ref}"')
    lines.append('>')
    path.write_text("\n".join(lines), encoding="utf-8")


def make_audio(path, content=b"RIFF....fake-wav-data"):
    path.write_bytes(content)


# --- _extract_file_references (REAPER's quoting styles) ---

def test_extract_file_references_double_quotes():
    content = '<REAPER_PROJECT\n    FILE "kick.wav"\n>'
    assert reaper_core._extract_file_references(content) == ["kick.wav"]


def test_extract_file_references_single_quotes_for_names_with_double_quote():
    # REAPER falls back to single quotes when the value itself contains a "
    content = '<REAPER_PROJECT\n    FILE \'weird"name.wav\'\n>'
    assert reaper_core._extract_file_references(content) == ['weird"name.wav']


def test_extract_file_references_backtick_for_names_with_both_quote_types():
    content = "<REAPER_PROJECT\n    FILE `both\"and'quotes.wav`\n>"
    assert reaper_core._extract_file_references(content) == ["both\"and'quotes.wav"]


def test_extract_file_references_ignores_non_line_start_occurrences():
    # A hypothetical token ending in "FILE" must not be mistaken for the FILE key.
    content = '<REAPER_PROJECT\n    SOMEFILE "not-a-real-ref.wav"\n    FILE "real.wav"\n>'
    assert reaper_core._extract_file_references(content) == ["real.wav"]


# --- find_rpp_files ---

def test_find_rpp_files_finds_rpp_and_bak(tmp_path):
    (tmp_path / "song.rpp").write_text("dummy")
    (tmp_path / "song.rpp-bak").write_text("dummy")
    (tmp_path / "notes.txt").write_text("dummy")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "other.RPP").write_text("dummy")  # case-insensitive match

    found = reaper_core.find_rpp_files(str(tmp_path))
    names = sorted(f["name"] for f in found)

    assert names == ["other.RPP", "song.rpp", "song.rpp-bak"]
    for f in found:
        assert "size_mb" in f and "date" in f and "path" in f


def test_find_rpp_files_skips_archive_folder(tmp_path):
    archive = tmp_path / reaper_core.ARCHIVE_FOLDER_NAME
    archive.mkdir()
    (archive / "leftover.rpp").write_text("dummy")
    (tmp_path / "song.rpp").write_text("dummy")

    found = reaper_core.find_rpp_files(str(tmp_path))

    assert [f["name"] for f in found] == ["song.rpp"]


# --- parse_used_media ---

def test_parse_used_media_absolute_path(tmp_path):
    audio_dir = tmp_path / "Audio Files"
    audio_dir.mkdir()
    kick = audio_dir / "kick.wav"
    make_audio(kick)

    rpp_path = tmp_path / "song.rpp"
    make_rpp(rpp_path, [str(kick)])

    used_paths, fallback = reaper_core.parse_used_media([str(rpp_path)])

    assert os.path.normpath(str(kick)).lower() in used_paths
    assert fallback == set()


def test_parse_used_media_relative_path(tmp_path):
    audio_dir = tmp_path / "Audio Files"
    audio_dir.mkdir()
    snare = audio_dir / "snare.wav"
    make_audio(snare)

    rpp_path = tmp_path / "song.rpp"
    make_rpp(rpp_path, ["Audio Files/snare.wav"])

    used_paths, fallback = reaper_core.parse_used_media([str(rpp_path)])

    assert os.path.normpath(str(snare)).lower() in used_paths
    assert fallback == set()


def test_parse_used_media_unresolved_reference_falls_back_to_name(tmp_path):
    rpp_path = tmp_path / "song.rpp"
    make_rpp(rpp_path, ["../SomeGlobalLibrary/oneshot.wav"])

    used_paths, fallback = reaper_core.parse_used_media([str(rpp_path)])

    assert used_paths == set()
    assert "oneshot.wav" in fallback


def test_parse_used_media_resolves_absolute_path_case_insensitively(tmp_path):
    audio_dir = tmp_path / "Audio Files"
    audio_dir.mkdir()
    kick = audio_dir / "kick.wav"
    make_audio(kick)

    rpp_path = tmp_path / "song.rpp"
    # RPP stores the reference with different casing than the file on disk
    # (common after moving a project from Windows/macOS to Linux).
    make_rpp(rpp_path, [str(audio_dir / "KICK.WAV")])

    used_paths, fallback = reaper_core.parse_used_media([str(rpp_path)])

    assert os.path.normpath(str(kick)).lower() in used_paths
    assert fallback == set()


def test_parse_used_media_resolves_relative_path_case_insensitively(tmp_path):
    audio_dir = tmp_path / "Audio Files"
    audio_dir.mkdir()
    snare = audio_dir / "snare.wav"
    make_audio(snare)

    rpp_path = tmp_path / "song.rpp"
    make_rpp(rpp_path, ["audio files/SNARE.wav"])

    used_paths, fallback = reaper_core.parse_used_media([str(rpp_path)])

    assert os.path.normpath(str(snare)).lower() in used_paths
    assert fallback == set()


# --- find_unused_and_ambiguous_files ---

def test_find_unused_and_ambiguous_files_classifies_correctly(tmp_path):
    project_dir = tmp_path / "Proj1"
    project_dir.mkdir()

    used = project_dir / "used.wav"
    fallback_name = project_dir / "fallback.wav"
    truly_unused = project_dir / "truly_unused.wav"
    for f in (used, fallback_name, truly_unused):
        make_audio(f)

    rpp_path = project_dir / "Proj1.rpp"
    make_rpp(rpp_path, [str(used), "../Outside/fallback.wav"])

    used_paths, fallback = reaper_core.parse_used_media([str(rpp_path)])
    unused, ambiguous = reaper_core.find_unused_and_ambiguous_files(
        [(str(rpp_path), "Proj1.rpp")], used_paths, fallback
    )

    assert {u["name"] for u in unused} == {"truly_unused.wav"}
    assert {a["name"] for a in ambiguous} == {"fallback.wav"}
    assert unused[0]["origin"] == "Proj1.rpp"
    assert ambiguous[0]["origin"] == "Proj1.rpp"


def test_find_unused_and_ambiguous_files_ignores_non_audio_extensions(tmp_path):
    project_dir = tmp_path / "Proj1"
    project_dir.mkdir()
    (project_dir / "readme.txt").write_text("not audio")
    rpp_path = project_dir / "Proj1.rpp"
    make_rpp(rpp_path, [])

    unused, ambiguous = reaper_core.find_unused_and_ambiguous_files(
        [(str(rpp_path), "Proj1.rpp")], set(), set()
    )

    assert unused == []
    assert ambiguous == []


def test_find_unused_and_ambiguous_files_skips_archive_folder(tmp_path):
    project_dir = tmp_path / "Proj1"
    project_dir.mkdir()
    archive = project_dir / reaper_core.ARCHIVE_FOLDER_NAME / "Proj1"
    archive.mkdir(parents=True)
    make_audio(archive / "already_archived.wav")

    rpp_path = project_dir / "Proj1.rpp"
    make_rpp(rpp_path, [])

    unused, ambiguous = reaper_core.find_unused_and_ambiguous_files(
        [(str(rpp_path), "Proj1.rpp")], set(), set()
    )

    assert unused == []
    assert ambiguous == []


# --- archive_files / undo_last_archive ---

def test_archive_files_moves_file_and_writes_log(tmp_path):
    project_dir = tmp_path / "Proj1"
    project_dir.mkdir()
    audio = project_dir / "unused.wav"
    make_audio(audio)

    files_to_move = [{"path": str(audio), "name": "unused.wav", "origin": "Proj1.rpp"}]
    moved, errors, archive_root = reaper_core.archive_files(files_to_move, str(tmp_path))

    assert moved == 1
    assert errors == 0
    dest = tmp_path / reaper_core.ARCHIVE_FOLDER_NAME / "Proj1" / "unused.wav"
    assert dest.exists()
    assert not audio.exists()
    assert reaper_core.has_undoable_session(str(tmp_path)) is True

    log_path = tmp_path / reaper_core.ARCHIVE_FOLDER_NAME / reaper_core.LOG_FILE_NAME
    sessions = json.loads(log_path.read_text())
    assert len(sessions) == 1
    assert sessions[0]["entries"][0]["source"] == str(audio)
    assert sessions[0]["entries"][0]["dest"] == str(dest)


def test_archive_files_reports_errors_for_missing_source(tmp_path):
    files_to_move = [{"path": str(tmp_path / "ghost.wav"), "name": "ghost.wav", "origin": "Proj1.rpp"}]
    moved, errors, _ = reaper_core.archive_files(files_to_move, str(tmp_path))

    assert moved == 0
    assert errors == 1
    assert reaper_core.has_undoable_session(str(tmp_path)) is False


def test_undo_last_archive_restores_file(tmp_path):
    project_dir = tmp_path / "Proj1"
    project_dir.mkdir()
    audio = project_dir / "unused.wav"
    make_audio(audio)

    files_to_move = [{"path": str(audio), "name": "unused.wav", "origin": "Proj1.rpp"}]
    reaper_core.archive_files(files_to_move, str(tmp_path))
    assert not audio.exists()

    restored, errors = reaper_core.undo_last_archive(str(tmp_path))

    assert restored == 1
    assert errors == 0
    assert audio.exists()
    assert reaper_core.has_undoable_session(str(tmp_path)) is False


def test_undo_last_archive_with_no_sessions_is_noop(tmp_path):
    restored, errors = reaper_core.undo_last_archive(str(tmp_path))
    assert (restored, errors) == (0, 0)


def test_undo_last_archive_keeps_retryable_entry_on_partial_failure(tmp_path):
    project_dir = tmp_path / "Proj1"
    project_dir.mkdir()
    audio = project_dir / "unused.wav"
    make_audio(audio)

    files_to_move = [{"path": str(audio), "name": "unused.wav", "origin": "Proj1.rpp"}]
    reaper_core.archive_files(files_to_move, str(tmp_path))

    # Simulate the archived file being deleted/moved externally before undo.
    dest = tmp_path / reaper_core.ARCHIVE_FOLDER_NAME / "Proj1" / "unused.wav"
    dest.unlink()

    restored, errors = reaper_core.undo_last_archive(str(tmp_path))

    assert restored == 0
    assert errors == 1
    # The session must still be present so the user can be informed / can retry.
    assert reaper_core.has_undoable_session(str(tmp_path)) is True
