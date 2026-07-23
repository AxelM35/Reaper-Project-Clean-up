import datetime
import os
import threading
import tkinter as tk

import customtkinter as ctk
from tkinter import filedialog, messagebox

import reaper_core
from i18n import t, SUPPORTED_LANGUAGES

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

_LANGUAGE_LABELS = {"en": "English", "fr": "Français"}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- SETTINGS & LANGUAGE ---
        self.settings = reaper_core.load_settings()
        self.lang = self.settings.get("language", "en")
        if self.lang not in SUPPORTED_LANGUAGES:
            self.lang = "en"

        # Window Setup
        self.title(self._t("window_title"))
        self.geometry("1200x800")

        # Grid Configuration
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1) # Scrollable area expands

        # --- DATA STATE ---
        self.root_folder = ""
        self.all_projects_data = []  # List of dicts
        self.unused_files_data = []  # List of dicts
        self.ambiguous_files_data = []  # List of dicts (excluded by the safety net)
        self._cancel_event = threading.Event()
        # Bumped on every render_projects()/render_unused() call so a stale,
        # still-scheduled chunk from a previous render (e.g. superseded by a
        # fast filter keystroke) can recognize it's obsolete and stop.
        self._project_render_token = 0
        self._unused_render_token = 0

        # --- UI LAYOUT ---

        # 1. HEADER (Top)
        self.header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(20, 10))

        self.path_entry = ctk.CTkEntry(self.header_frame, placeholder_text=self._t("path_placeholder"), width=600)
        self.path_entry.pack(side="left", padx=(0, 10))
        self.path_entry.bind("<Return>", self.scan_folder_from_entry)

        self.scan_btn = ctk.CTkButton(self.header_frame, text=self._t("scan_folder"), command=self.scan_folder, font=("Arial", 12, "bold"))
        self.scan_btn.pack(side="left")

        # Progress bar + cancel button for long scans - created but not packed
        # until an operation actually starts (see _start_progress/_stop_progress).
        self.progress_bar = ctk.CTkProgressBar(self.header_frame, mode="indeterminate", width=160)
        self.cancel_btn = ctk.CTkButton(self.header_frame, text=self._t("cancel_button"), width=90,
                                        fg_color="#7A3B3B", hover_color="#8A4B4B", command=self._cancel_current_operation)

        self.settings_btn = ctk.CTkButton(self.header_frame, text=self._t("settings_button"), width=110,
                                          fg_color="#444", hover_color="#555", command=self.open_settings)
        self.settings_btn.pack(side="right")

        # 2. COLUMN HEADERS (Sorting, filtering, bulk selection)
        self.left_header = ctk.CTkFrame(self, fg_color="transparent")
        self.left_header.grid(row=1, column=0, sticky="ew", padx=20)
        ctk.CTkLabel(self.left_header, text=self._t("projects_found"), font=("Arial", 14, "bold")).pack(side="left")
        self.project_filter_var = ctk.StringVar()
        self.project_filter_var.trace_add("write", lambda *_: self.render_projects())
        ctk.CTkEntry(self.left_header, textvariable=self.project_filter_var,
                    placeholder_text=self._t("filter_placeholder"), width=140).pack(side="left", padx=(15, 0))
        ctk.CTkButton(self.left_header, text=self._t("sort_name"), width=80, height=20, fg_color="#444", command=lambda: self.sort_projects("name")).pack(side="right", padx=2)
        ctk.CTkButton(self.left_header, text=self._t("sort_size"), width=80, height=20, fg_color="#444", command=lambda: self.sort_projects("size")).pack(side="right", padx=2)
        ctk.CTkButton(self.left_header, text=self._t("select_none"), width=50, height=20, fg_color="#444", command=lambda: self.set_all_projects_selected(False)).pack(side="right", padx=2)
        ctk.CTkButton(self.left_header, text=self._t("select_all"), width=50, height=20, fg_color="#444", command=lambda: self.set_all_projects_selected(True)).pack(side="right", padx=2)

        self.right_header = ctk.CTkFrame(self, fg_color="transparent")
        self.right_header.grid(row=1, column=1, sticky="ew", padx=20)
        ctk.CTkLabel(self.right_header, text=self._t("unused_files"), font=("Arial", 14, "bold"), text_color="#FF5555").pack(side="left")
        self.unused_filter_var = ctk.StringVar()
        self.unused_filter_var.trace_add("write", lambda *_: self.render_unused())
        ctk.CTkEntry(self.right_header, textvariable=self.unused_filter_var,
                    placeholder_text=self._t("filter_placeholder"), width=140).pack(side="left", padx=(15, 0))
        ctk.CTkButton(self.right_header, text=self._t("sort_size"), width=80, height=20, fg_color="#444", command=lambda: self.sort_unused("size")).pack(side="right", padx=2)
        ctk.CTkButton(self.right_header, text=self._t("sort_name"), width=80, height=20, fg_color="#444", command=lambda: self.sort_unused("name")).pack(side="right", padx=2)
        ctk.CTkButton(self.right_header, text=self._t("select_none"), width=50, height=20, fg_color="#444", command=lambda: self.set_all_unused_selected(False)).pack(side="right", padx=2)
        ctk.CTkButton(self.right_header, text=self._t("select_all"), width=50, height=20, fg_color="#444", command=lambda: self.set_all_unused_selected(True)).pack(side="right", padx=2)
        self.selection_label = ctk.CTkLabel(self.right_header, text="", text_color="#9FCF9F", font=("Arial", 12))
        self.selection_label.pack(side="right", padx=10)

        # 3. SCROLLABLE AREAS
        self.project_scroll = ctk.CTkScrollableFrame(self, label_text=self._t("select_rpp_placeholder"))
        self.project_scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=5)

        self.files_scroll = ctk.CTkScrollableFrame(self, label_text=self._t("select_files_placeholder"))
        self.files_scroll.grid(row=2, column=1, sticky="nsew", padx=20, pady=5)

        # 3.5 AMBIGUOUS FILES ALERT BANNER (hidden unless there is something to review)
        self.alert_banner = ctk.CTkFrame(self, fg_color="#4A3B1E", corner_radius=6)
        self.alert_banner.grid(row=3, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 10))
        self.alert_banner_label = ctk.CTkLabel(self.alert_banner, text="", text_color="#F5C767", font=("Arial", 12, "bold"))
        self.alert_banner_label.pack(side="left", padx=15, pady=10)
        ctk.CTkButton(self.alert_banner, text=self._t("ambiguous_review_button"), width=100,
                     fg_color="#F5C767", text_color="#2B2B2B", hover_color="#E0B050",
                     command=self.show_ambiguous_files).pack(side="right", padx=15, pady=10)
        self.alert_banner.grid_remove()

        # 4. FOOTER ACTIONS
        self.action_frame = ctk.CTkFrame(self, height=80, fg_color="#2B2B2B")
        self.action_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=0, pady=0)

        self.status_label = ctk.CTkLabel(self.action_frame, text=self._t("status_ready"), text_color="gray")
        self.status_label.pack(side="left", padx=20)

        self.ambiguous_btn = ctk.CTkButton(self.action_frame, text=self._t("ambiguous_button_na"),
                                           font=("Arial", 11), fg_color="transparent",
                                           text_color="#E5B450", hover_color="#3A3A3A",
                                           width=220, anchor="w", command=self.show_ambiguous_files)
        self.ambiguous_btn.pack(side="left", padx=10)

        self.btn_archive = ctk.CTkButton(self.action_frame, text=self._t("archive_selected"), font=("Arial", 12, "bold"), text_color="white",
                                         fg_color="#7CA37C", hover_color="#922B21",
                                         state="disabled", width=200, command=self.archive_files_logic)
        self.btn_archive.pack(side="right", padx=20, pady=20)

        self.btn_search = ctk.CTkButton(self.action_frame, text=self._t("find_unused"), font=("Arial", 12, "bold"), text_color="white",
                                        state="disabled", width=200, command=self.find_unused_logic)
        self.btn_search.pack(side="right", padx=10, pady=20)

        self.btn_undo = ctk.CTkButton(self.action_frame, text=self._t("undo_last_archive"), font=("Arial", 12, "bold"), text_color="white",
                                      fg_color="#555", hover_color="#775555",
                                      state="disabled", width=200, command=self.undo_last_archive_logic)
        self.btn_undo.pack(side="right", padx=10, pady=20)

    def _t(self, key, **kwargs):
        return t(key, self.lang, **kwargs)

    # --- BACKGROUND TASK HELPER ---
    def _run_in_background(self, task, on_success, on_cancelled=None):
        """Run `task()` in a worker thread and dispatch its result back on the
        main thread. Tk widgets must only be touched from the main thread, so
        `task` must be a pure function (no widget access) - callers gather
        whatever state they need from the UI *before* calling this."""
        result_box = {}

        def worker():
            try:
                result_box['value'] = task()
            except reaper_core.ScanCancelled:
                result_box['cancelled'] = True
            except Exception as exc:  # pragma: no cover - defensive, surfaced to the user
                result_box['error'] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        def poll():
            if thread.is_alive():
                self.after(80, poll)
                return
            if result_box.get('cancelled'):
                if on_cancelled:
                    on_cancelled()
            elif 'error' in result_box:
                self._stop_progress()
                messagebox.showerror(self._t("settings_window_title"), str(result_box['error']))
            else:
                on_success(result_box.get('value'))

        poll()

    def _start_progress(self, status_text):
        self._cancel_event.clear()
        self.alert_banner.grid_remove()
        self.status_label.configure(text=status_text)
        self.progress_bar.pack(side="left", padx=10)
        self.progress_bar.start()
        self.cancel_btn.pack(side="left", padx=(0, 10))
        self.scan_btn.configure(state="disabled")
        self.settings_btn.configure(state="disabled")
        self.btn_search.configure(state="disabled")
        self.btn_archive.configure(state="disabled")
        self.btn_undo.configure(state="disabled")

    def _stop_progress(self):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.cancel_btn.pack_forget()
        self.scan_btn.configure(state="normal")
        self.settings_btn.configure(state="normal")

    def _cancel_current_operation(self):
        self._cancel_event.set()

    # --- 1ST FUNCTION: SCANNING THE FOLDER FOR RPP FILES ---
    def scan_folder(self):
        path = filedialog.askdirectory()
        if not path: return
        self._begin_scan(path)

    def scan_folder_from_entry(self, event=None):
        path = self.path_entry.get().strip()
        if not path:
            return
        if not os.path.isdir(path):
            messagebox.showerror(self._t("invalid_path_title"), self._t("invalid_path_msg", path=path))
            return
        self._begin_scan(path)

    def _begin_scan(self, path):
        self.root_folder = path
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, path)

        self._start_progress(self._t("status_scanning"))

        def task():
            return reaper_core.find_rpp_files(path, cancel_check=self._cancel_event.is_set)

        def on_success(found):
            self._stop_progress()
            self.all_projects_data = [
                {**proj, "selected_var": ctk.IntVar(value=1)} for proj in found
            ]
            self.ambiguous_files_data = []
            self.ambiguous_btn.configure(text=self._t("ambiguous_button_na"))
            self._update_ambiguous_banner()

            # A fresh scan invalidates any previous "unused files" results
            # until "Find Unused" is re-run - otherwise the right panel
            # would keep showing stale results from a different folder.
            self.unused_files_data = []
            self.render_unused()
            self.btn_archive.configure(state="disabled")

            self.render_projects()
            self.btn_search.configure(state="normal")
            self._refresh_undo_state()
            self.status_label.configure(text=self._t("status_found_projects", n=len(self.all_projects_data)))

        def on_cancelled():
            self._stop_progress()
            self.btn_search.configure(state="normal" if self.all_projects_data else "disabled")
            self._refresh_undo_state()
            self.status_label.configure(text=self._t("status_cancelled"))

        self._run_in_background(task, on_success, on_cancelled)

    def _row_bg(self, scrollable_frame):
        """Background color matching a CTkScrollableFrame's own fill, so
        plain-tkinter list rows (see _render_project_batch/_render_unused_batch)
        blend in instead of showing a mismatched default gray."""
        color = scrollable_frame.cget("fg_color")
        if isinstance(color, (list, tuple)):
            return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
        return color

    # Zebra striping / group-header shades, layered on top of the base
    # _row_bg() so alternating rows and group headers stay readable at a
    # glance without needing a real spreadsheet-style grid widget.
    _ROW_ALT_BG = "gray20"
    _GROUP_HEADER_BG = "gray24"

    def render_projects(self):
        # Clear UI
        for widget in self.project_scroll.winfo_children(): widget.destroy()

        query = self.project_filter_var.get().strip().lower()
        items = [p for p in self.all_projects_data if not query or query in p['name'].lower()]

        self.project_scroll.grid_columnconfigure(0, weight=1)
        self.project_scroll.grid_columnconfigure(1, weight=0)

        self._project_render_token += 1
        self._render_project_batch(items, 0, self._project_render_token)

    def _render_project_batch(self, items, index, token, batch_size=60):
        # A newer render_projects() call has since cleared the panel and
        # started its own sequence - creating widgets from this stale batch
        # would silently re-populate a list the user already moved on from.
        # Rendering in small batches (instead of all ~1000+ rows in one
        # synchronous pass) keeps the UI responsive on large project folders.
        # Rows use plain tkinter widgets rather than customtkinter's (each
        # customtkinter widget is a canvas-based construct ~10x more
        # expensive to build - at 1000 rows that alone is a multi-second
        # stall, which is what most of a reported "freeze" turned out to be).
        if token != self._project_render_token:
            return

        row_bg = self._row_bg(self.project_scroll)
        end = min(index + batch_size, len(items))
        for row_index in range(index, end):
            proj = items[row_index]
            # Widgets are gridded directly into the scrollable frame (two
            # fixed columns) rather than packed inside a per-row Frame, so
            # the size column lines up at the same x position on every row
            # regardless of filename length - an actual table, not an
            # approximation of one.
            bg = self._ROW_ALT_BG if row_index % 2 else row_bg
            cb = tk.Checkbutton(self.project_scroll, text=proj['name'], variable=proj['selected_var'],
                                bg=bg, fg="white", selectcolor="#333333",
                                activebackground=bg, activeforeground="white",
                                highlightthickness=0, bd=0, anchor="w", font=("Arial", 12))
            cb.grid(row=row_index, column=0, sticky="ew", padx=(4, 10), pady=1)

            lbl = tk.Label(self.project_scroll, text=f"{proj['size_mb']:.2f} MB", fg="gray", bg=bg,
                          anchor="e", font=("Arial", 11))
            lbl.grid(row=row_index, column=1, sticky="e", padx=(0, 10), pady=1)

        if end < len(items):
            self.after(1, lambda: self._render_project_batch(items, end, token, batch_size))

    def set_all_projects_selected(self, selected):
        query = self.project_filter_var.get().strip().lower()
        for proj in self.all_projects_data:
            if query and query not in proj['name'].lower():
                continue
            proj['selected_var'].set(1 if selected else 0)


    # --- 2ND FUNCTION: FINDING UNUSED AUDIO FILES ---
    def find_unused_logic(self):
        all_rpp_paths = [p['path'] for p in self.all_projects_data]
        checked_projects = [
            (p['path'], p['name']) for p in self.all_projects_data if p['selected_var'].get() == 1
        ]
        extra_folders = self.settings.get("extra_search_folders", [])
        audio_extensions = self.settings.get("audio_extensions") or reaper_core.AUDIO_EXTENSIONS

        self._start_progress(self._t("status_analyzing"))

        def task():
            specific_used_paths, fallback_safe_names = reaper_core.parse_used_media(
                all_rpp_paths, extra_folders, cancel_check=self._cancel_event.is_set
            )
            return reaper_core.find_unused_and_ambiguous_files(
                checked_projects, specific_used_paths, fallback_safe_names, audio_extensions,
                cancel_check=self._cancel_event.is_set,
            )

        def on_success(result):
            unused, ambiguous = result
            self._stop_progress()
            self.unused_files_data = [self._make_unused_entry(item) for item in unused]
            self.ambiguous_files_data = ambiguous
            self.ambiguous_btn.configure(text=self._t("ambiguous_button", n=len(ambiguous)))
            self._update_ambiguous_banner()

            self.render_unused()
            self.btn_archive.configure(state="normal")
            self.btn_search.configure(state="normal")
            self._refresh_undo_state()

            self.status_label.configure(text=self._t("status_analysis_complete", n=len(self.unused_files_data)))

        def on_cancelled():
            self._stop_progress()
            self.btn_search.configure(state="normal")
            self._refresh_undo_state()
            self.status_label.configure(text=self._t("status_cancelled"))

        self._run_in_background(task, on_success, on_cancelled)

    def _make_unused_entry(self, item):
        # The trace is attached once here, not in render_unused()'s per-row
        # loop - render_unused() re-runs on every filter keystroke while the
        # underlying IntVar objects persist, so attaching it there would
        # silently stack a new duplicate callback on every keystroke.
        var = ctk.IntVar(value=1)
        var.trace_add("write", lambda *_: self._update_selection_summary())
        return {**item, "selected_var": var}

    def render_unused(self):
        for widget in self.files_scroll.winfo_children(): widget.destroy()

        query = self.unused_filter_var.get().strip().lower()
        items = [
            f for f in self.unused_files_data
            if not query or query in f['name'].lower() or query in f['origin'].lower()
        ]

        # The summary reflects the full underlying selection, not just what's
        # rendered so far, so it's correct immediately even while rows stream in.
        self._update_selection_summary()

        # Group by origin project so it's immediately obvious which project
        # each unused file came from (a section header), instead of a small
        # gray suffix on every single row that's easy to miss. Groups are
        # ordered alphabetically for a predictable "table of contents";
        # within a group, files keep whatever Name/Size sort order is active.
        groups = {}
        for item in items:
            groups.setdefault(item['origin'], []).append(item)

        row_plan = []
        for origin in sorted(groups.keys(), key=str.lower):
            group_items = groups[origin]
            total_mb = sum(f['size_mb'] for f in group_items)
            row_plan.append(("header", origin, len(group_items), total_mb))
            for item in group_items:
                row_plan.append(("item", item))

        self.files_scroll.grid_columnconfigure(0, weight=1)
        self.files_scroll.grid_columnconfigure(1, weight=0)

        self._unused_render_token += 1
        self._render_unused_batch(row_plan, 0, self._unused_render_token, data_row_count=0)

    def _render_unused_batch(self, row_plan, index, token, data_row_count, batch_size=60):
        if token != self._unused_render_token:
            return  # superseded by a newer render_unused() call

        row_bg = self._row_bg(self.files_scroll)
        end = min(index + batch_size, len(row_plan))
        for grid_row in range(index, end):
            entry = row_plan[grid_row]
            if entry[0] == "header":
                _, origin, count, total_mb = entry
                header = tk.Label(
                    self.files_scroll, bg=self._GROUP_HEADER_BG, fg="white", anchor="w",
                    font=("Arial", 12, "bold"),
                    text=f"{origin}   ({count} · {total_mb:.1f} MB)",
                )
                header.grid(row=grid_row, column=0, columnspan=2, sticky="ew",
                           padx=2, pady=(8 if grid_row > 0 else 0, 2))
            else:
                file = entry[1]
                bg = self._ROW_ALT_BG if data_row_count % 2 else row_bg
                data_row_count += 1

                cb = tk.Checkbutton(self.files_scroll, text=file['name'], variable=file['selected_var'],
                                    bg=bg, fg="#FF9999", selectcolor="#333333",
                                    activebackground=bg, activeforeground="#FF9999",
                                    highlightthickness=0, bd=0, anchor="w", font=("Arial", 12))
                cb.grid(row=grid_row, column=0, sticky="ew", padx=(20, 10), pady=1)

                lbl = tk.Label(self.files_scroll, text=f"{file['size_mb']:.1f} MB", fg="gray", bg=bg,
                              anchor="e", font=("Arial", 11))
                lbl.grid(row=grid_row, column=1, sticky="e", padx=(0, 10), pady=1)

        if end < len(row_plan):
            self.after(1, lambda: self._render_unused_batch(row_plan, end, token, data_row_count, batch_size))

    def set_all_unused_selected(self, selected):
        query = self.unused_filter_var.get().strip().lower()
        for file in self.unused_files_data:
            if query and query not in file['name'].lower() and query not in file['origin'].lower():
                continue
            file['selected_var'].set(1 if selected else 0)

    def _update_selection_summary(self):
        selected = [f for f in self.unused_files_data if f['selected_var'].get() == 1]
        total_mb = sum(f['size_mb'] for f in selected)
        self.selection_label.configure(text=self._t("selection_summary", count=len(selected), size=total_mb))

    def _update_ambiguous_banner(self):
        count = len(self.ambiguous_files_data)
        if count > 0:
            self.alert_banner_label.configure(text=self._t("ambiguous_banner_msg", n=count))
            self.alert_banner.grid()
        else:
            self.alert_banner.grid_remove()

    # --- TRANSPARENCY: SHOW FILES EXCLUDED BY THE SAFETY NET ---
    def show_ambiguous_files(self):
        if not self.ambiguous_files_data:
            messagebox.showinfo(self._t("ambiguous_none_title"), self._t("ambiguous_none_msg"))
            return

        win = ctk.CTkToplevel(self)
        win.title(self._t("ambiguous_window_title"))
        win.geometry("700x450")

        ctk.CTkLabel(
            win,
            text=self._t("ambiguous_window_explanation"),
            justify="left", text_color="#E5B450",
        ).pack(padx=15, pady=(15, 10), anchor="w")

        scroll = ctk.CTkScrollableFrame(win)
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        row_bg = self._row_bg(scroll)
        for file in self.ambiguous_files_data:
            row = tk.Frame(scroll, bg=row_bg)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=file['name'], fg="white", bg=row_bg, anchor="w", font=("Arial", 12)).pack(side="left")
            tk.Label(row, text=f"[{file['origin']}]  {file['size_mb']:.1f}MB", fg="gray", bg=row_bg,
                    anchor="e", font=("Arial", 11)).pack(side="right", padx=(0, 10))

    # --- LOGIC 3: ARCHIVER ---
    def archive_files_logic(self):
        # Filter only checked files
        files_to_move = [f for f in self.unused_files_data if f['selected_var'].get() == 1]

        if not files_to_move:
            messagebox.showinfo(self._t("confirm_archive_title"), self._t("no_files_selected_msg"))
            return

        confirm = messagebox.askyesno(self._t("confirm_archive_title"), self._t("confirm_archive_msg", n=len(files_to_move)))
        if not confirm: return

        count, errors, archive_root = reaper_core.archive_files(files_to_move, self.root_folder)

        # Cleanup UI
        self._refresh_undo_state()
        self.find_unused_logic() # Re-scan to update list (async)
        messagebox.showinfo(self._t("archive_success_title"), self._t("archive_success_msg", count=count, errors=errors, location=archive_root))

    # --- LOGIC 4: UNDO LAST ARCHIVE ---
    def undo_last_archive_logic(self):
        if not self.root_folder:
            return
        session = reaper_core.get_last_archive_session(self.root_folder)
        if not session:
            return

        entries = session["entries"]
        names = [e.get("name") or os.path.basename(e["dest"]) for e in entries]
        preview = "\n".join(f"  • {name}" for name in names[:10])
        if len(names) > 10:
            preview += "\n  " + self._t("and_n_more", n=len(names) - 10)

        try:
            timestamp = datetime.datetime.fromisoformat(session["timestamp"]).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            timestamp = session["timestamp"]

        confirm = messagebox.askyesno(
            self._t("confirm_undo_title"),
            self._t("confirm_undo_msg_detailed", n=len(entries), timestamp=timestamp, files=preview),
        )
        if not confirm: return

        restored, errors = reaper_core.undo_last_archive(self.root_folder)

        self._refresh_undo_state()
        self.find_unused_logic() # Re-scan to update list (async)
        messagebox.showinfo(self._t("undo_complete_title"), self._t("undo_complete_msg", restored=restored, errors=errors))

    def _refresh_undo_state(self):
        can_undo = bool(self.root_folder) and reaper_core.has_undoable_session(self.root_folder)
        self.btn_undo.configure(state="normal" if can_undo else "disabled")

    # --- SETTINGS ---
    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title(self._t("settings_window_title"))
        win.geometry("650x550")

        # Language
        ctk.CTkLabel(win, text=self._t("settings_language_label"), anchor="w").pack(fill="x", padx=15, pady=(15, 2))
        lang_var = ctk.StringVar(value=_LANGUAGE_LABELS.get(self.lang, "English"))
        lang_menu = ctk.CTkOptionMenu(win, values=[_LANGUAGE_LABELS[code] for code in SUPPORTED_LANGUAGES], variable=lang_var)
        lang_menu.pack(fill="x", padx=15, pady=(0, 15))

        # Audio extensions
        ctk.CTkLabel(win, text=self._t("settings_extensions_label"), anchor="w").pack(fill="x", padx=15, pady=(0, 2))
        ext_entry = ctk.CTkEntry(win)
        ext_entry.insert(0, ", ".join(self.settings.get("audio_extensions", list(reaper_core.AUDIO_EXTENSIONS))))
        ext_entry.pack(fill="x", padx=15, pady=(0, 15))

        # Extra search folders
        ctk.CTkLabel(win, text=self._t("settings_folders_label"), anchor="w").pack(fill="x", padx=15, pady=(0, 2))
        folders_scroll = ctk.CTkScrollableFrame(win, height=200)
        folders_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        folders = list(self.settings.get("extra_search_folders", []))

        def render_folders():
            for widget in folders_scroll.winfo_children(): widget.destroy()
            for folder in folders:
                row = ctk.CTkFrame(folders_scroll, fg_color="transparent")
                row.pack(fill="x", pady=2)
                ctk.CTkLabel(row, text=folder, anchor="w").pack(side="left", fill="x", expand=True)
                ctk.CTkButton(row, text=self._t("settings_remove"), width=70, fg_color="#7A3B3B",
                             command=lambda f=folder: (folders.remove(f), render_folders())).pack(side="right")

        def add_folder():
            chosen = filedialog.askdirectory()
            if chosen and chosen not in folders:
                folders.append(chosen)
                render_folders()

        render_folders()
        ctk.CTkButton(win, text=self._t("settings_add_folder"), command=add_folder).pack(padx=15, pady=(0, 15), anchor="w")

        def save_and_close():
            selected_label = lang_var.get()
            new_lang = next((code for code, label in _LANGUAGE_LABELS.items() if label == selected_label), self.lang)

            extensions = [
                e.strip().lower() if e.strip().startswith(".") else f".{e.strip().lower()}"
                for e in ext_entry.get().split(",") if e.strip()
            ]
            if not extensions:
                extensions = list(reaper_core.AUDIO_EXTENSIONS)

            self.settings = {
                "audio_extensions": extensions,
                "extra_search_folders": folders,
                "language": new_lang,
            }
            reaper_core.save_settings(self.settings)
            win.destroy()
            messagebox.showinfo(self._t("settings_saved_title"), self._t("settings_saved_msg"))

        ctk.CTkButton(win, text=self._t("settings_save"), font=("Arial", 12, "bold"), command=save_and_close).pack(padx=15, pady=(0, 15), anchor="e")

    # --- SORTING HELPERS ---
    def sort_projects(self, key):
        if key == "size":
            self.all_projects_data.sort(key=lambda x: x['size_mb'], reverse=True)
        else:
            self.all_projects_data.sort(key=lambda x: x['name'].lower())
        self.render_projects()

    def sort_unused(self, key):
        # Groups (see render_unused) are always ordered alphabetically by
        # origin project, so this only controls the order of files *within*
        # each group - not which project's section appears first.
        if key == "size":
            self.unused_files_data.sort(key=lambda x: x['size_mb'], reverse=True)
        else:
            self.unused_files_data.sort(key=lambda x: x['name'].lower())
        self.render_unused()

if __name__ == "__main__":
    app = App()
    app.mainloop()
