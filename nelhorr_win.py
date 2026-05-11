import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import datetime
import os
import subprocess

# Note: The app uses 'rclone' for syncing which relies on your 'Sys' remote configuration.
# Ensure rclone.exe is in your Windows PATH and 'Sys' remote is configured.

def sync_to_cloud():
    try:
        # Use rclone to sync the local log.txt to the 'Sys' remote
        # subprocess.run handles the list of arguments correctly on Windows if rclone is in PATH
        subprocess.run(["rclone", "copy", "log.txt", "Sys:nelhorr_app/"], check=True, shell=True)
    except Exception as e:
        print(f"Cloud sync failed: {e}")

def log_data(event=None):
    user_input = entry.get().strip()
    if user_input:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp} - {user_input}\n"
        
        try:
            with open("log.txt", "a") as f:
                f.write(log_entry)
            
            log_display.config(state=tk.NORMAL)
            log_display.insert(tk.END, log_entry)
            log_display.see(tk.END)  # Auto-scroll to the bottom
            log_display.config(state=tk.DISABLED)
            entry.delete(0, tk.END)
            
            # Sync to cloud after logging
            sync_to_cloud()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to write to log.txt: {e}")

def clear_log():
    if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all logs? This action cannot be undone."):
        try:
            with open("log.txt", "w") as f:
                f.write("")
            log_display.config(state=tk.NORMAL)
            log_display.delete(1.0, tk.END)
            log_display.config(state=tk.DISABLED)
            
            # Sync to cloud after clearing
            sync_to_cloud()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear log file: {e}")

def delete_last_entry():
    if not os.path.exists("log.txt"):
        return
    
    try:
        with open("log.txt", "r") as f:
            lines = f.readlines()
        
        if lines:
            lines.pop()  # Remove last line
            with open("log.txt", "w") as f:
                f.writelines(lines)
            
            # Refresh display
            log_display.config(state=tk.NORMAL)
            log_display.delete(1.0, tk.END)
            log_display.insert(tk.END, "".join(lines))
            log_display.see(tk.END)
            log_display.config(state=tk.DISABLED)
            
            # Sync to cloud after deleting
            sync_to_cloud()
        else:
            messagebox.showinfo("Info", "Log is already empty.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to delete last entry: {e}")

def main():
    global entry, log_display, root
    
    # --- GUI Setup ---
    root = tk.Tk()
    root.title("nelhorr Windows - UPDATED")
    root.geometry("600x500") 
    root.minsize(400, 350)

    # Apply Windows theme
    style = ttk.Style(root)
    available_themes = style.theme_names()
    if 'vista' in available_themes:
        style.theme_use('vista')
    elif 'xpnative' in available_themes:
        style.theme_use('xpnative')

    # Main Container
    main_frame = ttk.Frame(root, padding="15")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Header
    header_label = ttk.Label(main_frame, text="nelhorr", font=("Segoe UI", 24, "bold"))
    header_label.pack(pady=(0, 15))

    # Input Section
    input_frame = ttk.Frame(main_frame)
    input_frame.pack(fill=tk.X, pady=(0, 10))

    entry = ttk.Entry(input_frame, font=("Segoe UI", 14))
    entry.pack(fill=tk.X, expand=True)
    entry.focus_set()

    # Controls Row
    controls_frame = ttk.Frame(main_frame)
    controls_frame.pack(fill=tk.X, pady=10)

    log_btn = ttk.Button(controls_frame, text="Log Entry", command=log_data)
    log_btn.pack(side=tk.LEFT, padx=(0, 5))

    delete_btn = ttk.Button(controls_frame, text="Delete Last", command=delete_last_entry)
    delete_btn.pack(side=tk.LEFT, padx=5)

    clear_btn = ttk.Button(controls_frame, text="Delete All Logs", command=clear_log)
    clear_btn.pack(side=tk.LEFT, padx=5)

    quit_btn = ttk.Button(controls_frame, text="Quit", command=root.quit)
    quit_btn.pack(side=tk.RIGHT)

    # Bind Enter key to logging
    root.bind('<Return>', log_data)

    # Log Display Section
    display_label = ttk.Label(main_frame, text="Activity Log:", font=("Segoe UI", 10, "italic"))
    display_label.pack(anchor=tk.W, pady=(10, 2))

    # Consolas is the standard Windows mono font
    log_display = scrolledtext.ScrolledText(main_frame, state=tk.DISABLED, 
                                           font=("Consolas", 12), 
                                           bg="white", fg="black",
                                           insertbackground="black",
                                           padx=10, pady=10)
    log_display.pack(fill=tk.BOTH, expand=True)

    # Load existing log data
    if os.path.exists("log.txt"):
        try:
            with open("log.txt", "r") as f:
                existing_log = f.read()
                log_display.config(state=tk.NORMAL)
                log_display.insert(tk.END, existing_log)
                log_display.see(tk.END)
                log_display.config(state=tk.DISABLED)
        except Exception as e:
            print(f"Error loading log: {e}")

    root.mainloop()

if __name__ == "__main__":
    main()
