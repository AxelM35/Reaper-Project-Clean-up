import datetime

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

        # --- UI LAYOUT ---

        # 1. HEADER (Top)
        self.header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(20, 10))

        self.path_entry = ctk.CTkEntry(self.header_frame, placeholder_text=self._t("path_placeholder"), width=600)
        self.path_entry.pack(side="left", padx=(0, 10))

        self.scan_btn = ctk.CTkButton(self.header_frame, text=self._t("scan_folder"), command=self.scan_folder, font=("Arial", 12, "bold"))
        self.scan_btn.pack(side="left")

        self.settings_btn = ctk.CTkButton(self.header_frame, text=self._t("settings_button"), width=110,
                                          fg_color="#444", hover_color="#555", command=self.open_settings)
        self.settings_btn.pack(side="right")

        # 2. COLUMN HEADERS (Sorting)
        self.left_header = ctk.CTkFrame(self, fg_color="transparent")
        self.left_header.grid(row=1, column=0, sticky="ew", padx=20)
        ctk.CTkLabel(self.left_header, text=self._t("projects_found"), font=("Arial", 14, "bold")).pack(side="left")
        ctk.CTkButton(self.left_header, text=self._t("sort_name"), width=80, height=20, fg_color="#444", command=lambda: self.sort_projects("name")).pack(side="right", padx=2)
        ctk.CTkButton(self.left_header, text=self._t("sort_size"), width=80, height=20, fg_color="#444", command=lambda: self.sort_projects("size")).pack(side="right", padx=2)

        self.right_header = ctk.CTkFrame(self, fg_color="transparent")
        self.right_header.grid(row=1, column=1, sticky="ew", padx=20)
        ctk.CTkLabel(self.right_header, text=self._t("unused_files"), font=("Arial", 14, "bold"), text_color="#FF5555").pack(side="left")
        ctk.CTkButton(self.right_header, text=self._t("sort_size"), width=80, height=20, fg_color="#444", command=lambda: self.sort_unused("size")).pack(side="right", padx=2)
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

    # --- 1ST FUNCTION: SCANNING THE FOLDER FOR RPP FILES ---
    def scan_folder(self):
        path = filedialog.askdirectory()
        if not path: return

        self.root_folder = path
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, path)

        # Find RPP Files
        found = reaper_core.find_rpp_files(path)
        self.all_projects_data = [
            {**proj, "selected_var": ctk.IntVar(value=1)} for proj in found
        ]
        self.ambiguous_files_data = []
        self.ambiguous_btn.configure(text=self._t("ambiguous_button_na"))
        self._update_ambiguous_banner()

        # A fresh scan invalidates any previous "unused files" results until
        # "Find Unused" is re-run - otherwise the right panel would keep
        # showing stale results from a different folder.
        self.unused_files_data = []
        self.render_unused()
        self.btn_archive.configure(state="disabled")

        self.render_projects()
        self.btn_search.configure(state="normal")
        self._refresh_undo_state()
        self.status_label.configure(text=self._t("status_found_projects", n=len(self.all_projects_data)))

    def render_projects(self):
        # Clear UI
        for widget in self.project_scroll.winfo_children(): widget.destroy()

        # Re-draw UI
        for proj in self.all_projects_data:
            row = ctk.CTkFrame(self.project_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)

            cb = ctk.CTkCheckBox(row, text=proj['name'], variable=proj['selected_var'], width=300)
            cb.pack(side="left")

            lbl = ctk.CTkLabel(row, text=f"{proj['size_mb']:.2f} MB", text_color="gray", width=80, anchor="e")
            lbl.pack(side="right")


    # --- 2ND FUNCTION: FINDING UNUSED AUDIO FILES ---
    def find_unused_logic(self):
        self.status_label.configure(text=self._t("status_analyzing"))
        self.update()

        all_rpp_paths = [p['path'] for p in self.all_projects_data]
        extra_folders = self.settings.get("extra_search_folders", [])
        specific_used_paths, fallback_safe_names = reaper_core.parse_used_media(all_rpp_paths, extra_folders)

        checked_projects = [
            (p['path'], p['name']) for p in self.all_projects_data if p['selected_var'].get() == 1
        ]
        audio_extensions = self.settings.get("audio_extensions") or reaper_core.AUDIO_EXTENSIONS
        unused, ambiguous = reaper_core.find_unused_and_ambiguous_files(
            checked_projects, specific_used_paths, fallback_safe_names, audio_extensions
        )

        self.unused_files_data = [
            {**item, "selected_var": ctk.IntVar(value=1)} for item in unused
        ]
        self.ambiguous_files_data = ambiguous
        self.ambiguous_btn.configure(text=self._t("ambiguous_button", n=len(ambiguous)))
        self._update_ambiguous_banner()

        self.render_unused()
        self.btn_archive.configure(state="normal")

        self.status_label.configure(text=self._t("status_analysis_complete", n=len(self.unused_files_data)))

    def render_unused(self):
        for widget in self.files_scroll.winfo_children(): widget.destroy()

        for file in self.unused_files_data:
            row = ctk.CTkFrame(self.files_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)

            cb = ctk.CTkCheckBox(row, text=file['name'], variable=file['selected_var'], text_color="#FF9999")
            cb.pack(side="left")
            file['selected_var'].trace_add("write", lambda *_: self._update_selection_summary())

            # Show Origin Project
            meta = ctk.CTkLabel(row, text=f"[{file['origin']}]  {file['size_mb']:.1f}MB", text_color="gray", width=150, anchor="e")
            meta.pack(side="right")

        self._update_selection_summary()

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

        for file in self.ambiguous_files_data:
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=file['name'], anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=f"[{file['origin']}]  {file['size_mb']:.1f}MB", text_color="gray", width=150, anchor="e").pack(side="right")

    # --- LOGIC 3: ARCHIVER ---
    def archive_files_logic(self):
        # Filter only checked files
        files_to_move = [f for f in self.unused_files_data if f['selected_var'].get() == 1]

        if not files_to_move:
            return

        confirm = messagebox.askyesno(self._t("confirm_archive_title"), self._t("confirm_archive_msg", n=len(files_to_move)))
        if not confirm: return

        count, errors, archive_root = reaper_core.archive_files(files_to_move, self.root_folder)

        # Cleanup UI
        self.find_unused_logic() # Re-scan to update list
        self._refresh_undo_state()
        messagebox.showinfo(self._t("archive_success_title"), self._t("archive_success_msg", count=count, errors=errors, location=archive_root))

    # --- LOGIC 4: UNDO LAST ARCHIVE ---
    def undo_last_archive_logic(self):
        if not self.root_folder:
            return
        session = reaper_core.get_last_archive_session(self.root_folder)
        if not session:
            return

        entries = session["entries"]
        names = [e.get("name") or e["dest"].rsplit("/", 1)[-1] for e in entries]
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

        self.find_unused_logic() # Re-scan to update list
        self._refresh_undo_state()
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
        if key == "size":
            self.unused_files_data.sort(key=lambda x: x['size_mb'], reverse=True)
        self.render_unused()

if __name__ == "__main__":
    app = App()
    app.mainloop()
