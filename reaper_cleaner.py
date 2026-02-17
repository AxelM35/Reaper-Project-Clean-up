import os
import shutil
import re
import datetime
import customtkinter as ctk
from tkinter import filedialog, messagebox

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- AUDIO FORMATS TO SCAN ---
AUDIO_EXTENSIONS = ('.wav', '.aif', '.aiff', '.mp3', '.ogg', '.flac', '.mid')

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

        self.btn_archive = ctk.CTkButton(self.action_frame, text="3. ARCHIVE SELECTED", font=("Arial", 12, "bold"), text_color="white",
                                         fg_color="#7CA37C", hover_color="#922B21",
                                         state="disabled", width=200, command=self.archive_files_logic)
        self.btn_archive.pack(side="right", padx=20, pady=20)

        self.btn_search = ctk.CTkButton(self.action_frame, text="2. FIND UNUSED", font=("Arial", 12, "bold"), text_color="white",
                                        state="disabled", width=200, command=self.find_unused_logic)
        self.btn_search.pack(side="right", padx=10, pady=20)


    # --- 1ST FUNCTION: SCANNING THE FOLDER FOR RPP FILES ---
    def scan_folder(self):
        path = filedialog.askdirectory()
        if not path: return
        
        self.root_folder = path
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, path)
        self.all_projects_data = []

        # Find RPP Files
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.lower().endswith(('.rpp', '.rpp-bak')):
                    full_path = os.path.join(root, file)
                    size = os.path.getsize(full_path) / (1024*1024)
                    
                    self.all_projects_data.append({
                        "path": full_path,
                        "name": file,
                        "size_mb": size,
                        "date": datetime.datetime.fromtimestamp(os.path.getmtime(full_path)).strftime('%Y-%m-%d'),
                        "selected_var": ctk.IntVar(value=1) # Default Checked
                    })
        
        self.render_projects()
        self.btn_search.configure(state="normal")
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
        
        # We need two safety nets:
        # 1. specific_used_paths: Stores full absolute paths (e.g., "C:\Proj\Audio\kick.wav")
        # 2. fallback_safe_names: Stores just filenames (e.g., "kick.wav") if we couldn't find the file
        specific_used_paths = set()
        fallback_safe_names = set()
        
        all_rpp_paths = [p['path'] for p in self.all_projects_data]
        
        print(f"--- STARTING SCAN ---")

        for rpp_path in all_rpp_paths:
            project_folder = os.path.dirname(rpp_path)
            try:
                with open(rpp_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    matches = re.findall(r'FILE "(.*?)"', content)
                    
                    for m in matches:
                        # Normalize slashes
                        m_clean = m.replace('\\', '/')
                        filename = m_clean.split('/')[-1].lower()
                        
                        # LOGIC: Try to find the actual file on disk
                        found_absolute = False
                        
                        # Case A: RPP stored an absolute path (e.g., "C:/Sound/kick.wav")
                        if os.path.isabs(m_clean):
                            if os.path.exists(m_clean):
                                specific_used_paths.add(os.path.normpath(m_clean).lower())
                                found_absolute = True
                        
                        # Case B: RPP stored a relative path (e.g., "Audio/kick.wav")
                        else:
                            # Construct likely path relative to project file
                            likely_path = os.path.join(project_folder, m_clean)
                            if os.path.exists(likely_path):
                                specific_used_paths.add(os.path.normpath(likely_path).lower())
                                found_absolute = True
                        
                        # FAILSAFE: If we couldn't find the specific file (maybe it's in a global search path?)
                        # We must add the filename to the fallback list to be safe.
                        if not found_absolute:
                            fallback_safe_names.add(filename)

            except Exception as e:
                print(f"Error reading {rpp_path}: {e}")

        print(f"Smart Scan: Found {len(specific_used_paths)} specific paths and {len(fallback_safe_names)} fallback names.")
        
        # --- DISK COMPARISON ---
        self.unused_files_data = []
        checked_projects = [p for p in self.all_projects_data if p['selected_var'].get() == 1]

        for proj in checked_projects:
            project_dir = os.path.dirname(proj['path'])
            
            for root, dirs, files in os.walk(project_dir):
                for file in files:
                    if file.lower().endswith(AUDIO_EXTENSIONS):
                        full_path = os.path.join(root, file)
                        norm_path = os.path.normpath(full_path).lower()
                        
                        # 1. Is this EXACT path known to be used?
                        if norm_path in specific_used_paths:
                            continue # It's safe, skip it.

                        # 2. Is the filename in the "Ambiguous/Fallback" list?
                        if file.lower() in fallback_safe_names:
                            continue # It might be used by a project we couldn't resolve. Skip it.

                        # If we get here, it's truly unused
                        size = os.path.getsize(full_path) / (1024*1024)
                        self.unused_files_data.append({
                            "path": full_path,
                            "name": file,
                            "size_mb": size,
                            "origin": proj['name'],
                            "selected_var": ctk.IntVar(value=1)
                        })

        # Final Cleanup
        unique_unused = {item['path']: item for item in self.unused_files_data}.values()
        self.unused_files_data = list(unique_unused)
        self.render_unused()
        self.btn_archive.configure(state="normal")
        
        result_msg = f"Analysis Complete. Found {len(self.unused_files_data)} unused files."
        print(result_msg)
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

    # --- LOGIC 3: ARCHIVER ---
    def archive_files_logic(self):
        # Filter only checked files
        files_to_move = [f for f in self.unused_files_data if f['selected_var'].get() == 1]
        
        if not files_to_move:
            return

        confirm = messagebox.askyesno("Confirm Archive", f"Are you sure you want to move {len(files_to_move)} files to the Archive folder?")
        if not confirm: return

        # Create Master Archive Folder
        archive_root = os.path.join(self.root_folder, "_Reaper_Cleanup_Archive")
        if not os.path.exists(archive_root):
            os.makedirs(archive_root)

        count = 0
        errors = 0

        for item in files_to_move:
            try:
                # Create Subfolder based on Project Name
                # We strip the .rpp extension for the folder name
                proj_folder_name = os.path.splitext(item['origin'])[0]
                target_dir = os.path.join(archive_root, proj_folder_name)
                
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)

                # Move the file
                shutil.move(item['path'], os.path.join(target_dir, item['name']))
                count += 1
            except Exception as e:
                print(f"Error moving {item['name']}: {e}")
                errors += 1

        # Cleanup UI
        self.find_unused_logic() # Re-scan to update list
        messagebox.showinfo("Success", f"Archived {count} files.\nErrors: {errors}\n\nLocation: {archive_root}")

    # --- SORTING HELPERS ---
    def sort_projects(self, key):
        reverse = False
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