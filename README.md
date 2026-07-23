# Reaper Project Cleaner

A small desktop utility that finds and archives audio files your REAPER projects no longer reference — so your `Audio Files` folders stop growing forever with old takes, discarded overdubs, and one-shots you tried once and forgot about.

A massive THANK YOU to **GriffinSauce**, who started this as a JS tool. This is a full Python rewrite (customtkinter GUI) with a lot of v2 additions on top: safety nets, undo, configurability, and a big pass on reliability and usability.

> Originally shipped as a rough prototype ("do not use on real projects"). As of **v2**, it's had a proper pass on safety (nothing is ever deleted, everything is logged and undoable), correctness (regex parsing hardened, cross-platform path handling), and usability. Still: **always keep backups of anything you care about** — see [Safety](#safety) below.

## What it does

A simple 3-step workflow:

1. **Scan Folder** — recursively finds every `.rpp` / `.rpp-bak` project file under a root folder.
2. **Find Unused** — parses the media references (`FILE "..."`) inside the checked projects, then compares them against the actual audio files sitting in each project's folder.
3. **Archive Selected** — moves (never deletes) the files you confirm into a `_Reaper_Cleanup_Archive/<project>/` subfolder, so you can review or restore them later.

## What's new in v2

- **Nothing is ever silently lost.** Every archive operation is logged (source, destination, timestamp) and can be undone from the UI — including partial recovery if a file was moved again in the meantime.
- **Ambiguous files are surfaced, not hidden.** If a file's status can't be fully confirmed (e.g. it's referenced via a path the tool couldn't resolve), it's shown separately with an explanation instead of quietly disappearing from both lists.
- **More robust `.rpp` parsing.** Handles all three quoting styles REAPER's project format actually uses, and resolves paths case-insensitively — useful if a project has ever moved between Windows/macOS and Linux.
- **Configurable.** Audio extensions to scan, plus extra "media search folders" (the same idea as REAPER's own media search path) for references that live outside the project folder.
- **Handles big project libraries.** Scanning and analysis run in the background with a progress bar and a cancel button — tested against ~1000 accumulated `.rpp-bak` backups without locking up.
- **Easier to read results.** Unused files are grouped by the project they belong to, with a per-project checkbox to select/deselect everything in that group at once, plus text filtering and sorting.
- **English / French UI.**

## Installation

### Run from source (recommended for now)

```bash
git clone https://github.com/AxelM35/Reaper-Project-Clean-up.git
cd Reaper-Project-Clean-up
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python reaper_cleaner.py
```

Requires Python 3.10+ and [customtkinter](https://github.com/TomSchimansky/CustomTkinter) (the only dependency).

### Prebuilt binaries

Every push to `main` builds standalone Windows/Linux/macOS executables via GitHub Actions (see `.github/workflows/build.yml`). They're currently only available as **build artifacts** on the [Actions tab](https://github.com/AxelM35/Reaper-Project-Clean-up/actions) (requires a GitHub account, retained ~90 days) — proper tagged Releases with permanent download links aren't set up yet.

## How to use it

1. Click **1. SCAN FOLDER** and pick the root folder containing your REAPER project(s).
2. Click **2. FIND UNUSED**. Uncheck any project you don't want included in the comparison first if needed.
3. Review the **UNUSED FILES** list, grouped by project. If the **⚠ Ambiguous files** banner shows up, check it too — those are files the tool wasn't fully sure about.
4. Select what you want archived (there's a live "N selected · X MB" total) and click **3. ARCHIVE SELECTED**.
5. Made a mistake? **↩ UNDO LAST ARCHIVE** restores the files from the most recent archive session.

Settings (⚙) let you change the scanned audio extensions, add extra media search folders, and switch language.

## Safety

- Files are **moved**, never deleted, into `_Reaper_Cleanup_Archive/` inside the folder you scanned.
- Every archive operation is logged and can be undone from the app.
- That said: this tool inspects your `.rpp` files with a hardened but still heuristic parser, not REAPER's own project-loading code. **Back up anything irreplaceable before running it on a real project**, especially the first time.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest -v
```

- `reaper_core.py` — all scanning/parsing/archiving logic, with no GUI dependency (fully unit-testable).
- `reaper_cleaner.py` — the customtkinter GUI, built on top of `reaper_core`.
- `i18n.py` — the English/French string tables.
- `tests/` — unit tests for `reaper_core.py`.
- `CAHIER_DES_CHARGES.md` — a reverse-engineered functional spec of the tool (French).

Bug reports, test coverage on real-world project libraries, and pull requests are all very welcome — this started as a first-coding-project prototype and the goal is to keep making it more trustworthy.

## Credits

- Original concept and JS version: **GriffinSauce**.
- Python rewrite, v2 hardening (safety/undo, robustness, configurability, i18n, performance, UI) and this documentation: **AxelM35**, developed with the assistance of **[Claude Code](https://claude.ai/code)** (Anthropic).

## License

MIT — see [LICENSE](LICENSE). Free to use, share, and modify — just keep the copyright/credit notice above and in [LICENSE](LICENSE) intact.
