import customtkinter as ctk
from tkinter import filedialog, messagebox

import reaper_core

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("Reaper Project Cleaner - Clean and Archive Unused Audio Files")
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

        self.path_entry = ctk.CTkEntry(self.header_frame, placeholder_text="Select Project Root Folder...", width=600)
        self.path_entry.pack(side="left", padx=(0, 10))

        self.scan_btn = ctk.CTkButton(self.header_frame, text="1. SCAN FOLDER", command=self.scan_folder, font=("Arial", 12, "bold"))
        self.scan_btn.pack(side="left")

        # 2. COLUMN HEADERS (Sorting)
        self.left_header = ctk.CTkFrame(self, fg_color="transparent")
        self.left_header.grid(row=1, column=0, sticky="ew", padx=20)
        ctk.CTkLabel(self.left_header, text="PROJECTS FOUND", font=("Arial", 14, "bold")).pack(side="left")
        ctk.CTkButton(self.left_header, text="Sort Name", width=80, height=20, fg_color="#444", command=lambda: self.sort_projects("name")).pack(side="right", padx=2)
        ctk.CTkButton(self.left_header, text="Sort Size", width=80, height=20, fg_color="#444", command=lambda: self.sort_projects("size")).pack(side="right", padx=2)

        self.right_header = ctk.CTkFrame(self, fg_color="transparent")
        self.right_header.grid(row=1, column=1, sticky="ew", padx=20)
        ctk.CTkLabel(self.right_header, text="UNUSED FILES", font=("Arial", 14, "bold"), text_color="#FF5555").pack(side="left")
        ctk.CTkButton(self.right_header, text="Sort Size", width=80, height=20, fg_color="#444", command=lambda: self.sort_unused("size")).pack(side="right", padx=2)

        # 3. SCROLLABLE AREAS
        self.project_scroll = ctk.CTkScrollableFrame(self, label_text="Select .rpp to analyze")
        self.project_scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=5)

        self.files_scroll = ctk.CTkScrollableFrame(self, label_text="Select files to archive")
        self.files_scroll.grid(row=2, column=1, sticky="nsew", padx=20, pady=5)

        # 4. FOOTER ACTIONS
        self.action_frame = ctk.CTkFrame(self, height=80, fg_color="#2B2B2B")
        self.action_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=0, pady=0)

        self.status_label = ctk.CTkLabel(self.action_frame, text="Ready", text_color="gray")
        self.status_label.pack(side="left", padx=20)

        self.ambiguous_btn = ctk.CTkButton(self.action_frame, text="⚠ Ambiguous files: n/a",
                                           font=("Arial", 11), fg_color="transparent",
                                           text_color="#E5B450", hover_color="#3A3A3A",
                                           width=220, anchor="w", command=self.show_ambiguous_files)
        self.ambiguous_btn.pack(side="left", padx=10)

        self.btn_archive = ctk.CTkButton(self.action_frame, text="3. ARCHIVE SELECTED", font=("Arial", 12, "bold"), text_color="white",
                                         fg_color="#7CA37C", hover_color="#922B21",
                                         state="disabled", width=200, command=self.archive_files_logic)
        self.btn_archive.pack(side="right", padx=20, pady=20)

        self.btn_search = ctk.CTkButton(self.action_frame, text="2. FIND UNUSED", font=("Arial", 12, "bold"), text_color="white",
                                        state="disabled", width=200, command=self.find_unused_logic)
        self.btn_search.pack(side="right", padx=10, pady=20)

        self.btn_undo = ctk.CTkButton(self.action_frame, text="↩ UNDO LAST ARCHIVE", font=("Arial", 12, "bold"), text_color="white",
                                      fg_color="#555", hover_color="#775555",
                                      state="disabled", width=200, command=self.undo_last_archive_logic)
        self.btn_undo.pack(side="right", padx=10, pady=20)


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
        self.ambiguous_btn.configure(text="⚠ Ambiguous files: n/a")

        self.render_projects()
        self.btn_search.configure(state="normal")
        self._refresh_undo_state()
        self.status_label.configure(text=f"Found {len(self.all_projects_data)} project files.")

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
        self.status_label.configure(text="Analyzing for unused audio files...")
        self.update()

        all_rpp_paths = [p['path'] for p in self.all_projects_data]
        specific_used_paths, fallback_safe_names = reaper_core.parse_used_media(all_rpp_paths)

        checked_projects = [
            (p['path'], p['name']) for p in self.all_projects_data if p['selected_var'].get() == 1
        ]
        unused, ambiguous = reaper_core.find_unused_and_ambiguous_files(
            checked_projects, specific_used_paths, fallback_safe_names
        )

        self.unused_files_data = [
            {**item, "selected_var": ctk.IntVar(value=1)} for item in unused
        ]
        self.ambiguous_files_data = ambiguous
        self.ambiguous_btn.configure(text=f"⚠ Ambiguous files: {len(ambiguous)}")

        self.render_unused()
        self.btn_archive.configure(state="normal")

        result_msg = f"Analysis Complete. Found {len(self.unused_files_data)} unused files."
        self.status_label.configure(text=result_msg)

    def render_unused(self):
        for widget in self.files_scroll.winfo_children(): widget.destroy()

        for file in self.unused_files_data:
            row = ctk.CTkFrame(self.files_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)

            cb = ctk.CTkCheckBox(row, text=file['name'], variable=file['selected_var'], text_color="#FF9999")
            cb.pack(side="left")

            # Show Origin Project
            meta = ctk.CTkLabel(row, text=f"[{file['origin']}]  {file['size_mb']:.1f}MB", text_color="gray", width=150, anchor="e")
            meta.pack(side="right")

    # --- TRANSPARENCY: SHOW FILES EXCLUDED BY THE SAFETY NET ---
    def show_ambiguous_files(self):
        if not self.ambiguous_files_data:
            messagebox.showinfo(
                "Ambiguous Files",
                "No ambiguous files. Every audio file found is either a confirmed "
                "reference or a confirmed unused file."
            )
            return

        win = ctk.CTkToplevel(self)
        win.title("Ambiguous Files - Excluded by the Safety Net")
        win.geometry("700x450")

        ctk.CTkLabel(
            win,
            text=(
                "These audio files were NOT proposed for archiving because their filename\n"
                "matches an unresolved FILE reference in a scanned project (safety net).\n"
                "They might genuinely be in use via a path this tool could not verify\n"
                "(e.g. a REAPER media search path), or they might truly be unused.\n"
                "Review them manually before deleting or moving them yourself."
            ),
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

        confirm = messagebox.askyesno("Confirm Archive", f"Are you sure you want to move {len(files_to_move)} files to the Archive folder?")
        if not confirm: return

        count, errors, archive_root = reaper_core.archive_files(files_to_move, self.root_folder)

        # Cleanup UI
        self.find_unused_logic() # Re-scan to update list
        self._refresh_undo_state()
        messagebox.showinfo("Success", f"Archived {count} files.\nErrors: {errors}\n\nLocation: {archive_root}")

    # --- LOGIC 4: UNDO LAST ARCHIVE ---
    def undo_last_archive_logic(self):
        if not self.root_folder or not reaper_core.has_undoable_session(self.root_folder):
            return

        confirm = messagebox.askyesno("Confirm Undo", "Restore the files from the last archive operation to their original location?")
        if not confirm: return

        restored, errors = reaper_core.undo_last_archive(self.root_folder)

        self.find_unused_logic() # Re-scan to update list
        self._refresh_undo_state()
        messagebox.showinfo("Undo Complete", f"Restored {restored} files.\nErrors: {errors}")

    def _refresh_undo_state(self):
        can_undo = bool(self.root_folder) and reaper_core.has_undoable_session(self.root_folder)
        self.btn_undo.configure(state="normal" if can_undo else "disabled")

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
