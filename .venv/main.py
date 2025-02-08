import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys
import time
from pathlib import Path
import platform
import psutil  # More reliable than taskkill


class ServiceManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DevTool")
        self.root.geometry("600x400")

        # Add icon (handle PyInstaller and script execution)
        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, "favicon.ico")
            else:
                icon_path = "favicon.ico"
            self.root.iconbitmap(icon_path)
        except tk.TclError:
            print("Error: Could not find icon file.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")


        self.service_status_labels = {}
        self.running_services = set()
        self.lock = threading.Lock()  # For thread-safe access to running_services

        self.commands = {
            "MongoDB": {
                "start": ["mongodb\\bin\\mongod.exe", "--quiet", "--dbpath=mongodb\\local", "--logpath=mongodb\\mongo.log", "--logappend"],
                "stop": ["taskkill", "/F", "/IM", "mongod.exe"],  # Keep for fallback and MongoDB
                "log_path": "mongodb\\mongo.log"
            },
            "Nginx": {
                "start": ["nginx\\nginx.exe", "-c", "nginx\\conf\\nginx.conf", "-e", "./nginx/logs/error.log"],
                "stop": ["nginx\\nginx.exe", "-s", "stop"],  # Attempt graceful stop FIRST
                "log_path": "nginx\\logs\\error.log"
            }
        }

        if not platform.system().lower().startswith('win'):
            self.show_warning()
            return  # Exit if not on Windows

        self.setup_ui()

    def setup_ui(self):
        main_container = ttk.Frame(self.root)
        main_container.pack(expand=True, fill='both', padx=5, pady=5)

        self.status_frame = ttk.LabelFrame(main_container, text="Status Messages")
        self.status_frame.pack(fill='x', padx=5, pady=5)

        self.status_text = tk.Text(self.status_frame, height=4, wrap=tk.WORD, state='disabled')
        self.status_text.pack(fill='x', padx=5, pady=5)

        services_panel = ttk.Frame(main_container)
        services_panel.pack(expand=True, fill='both', padx=5, pady=5)

        for service_name in self.commands:
            self.create_service_panel(services_panel, service_name)

        action_panel = ttk.Frame(main_container)
        action_panel.pack(fill='x', padx=5, pady=5)
        self.create_action_buttons(action_panel)

        self.root.protocol("WM_DELETE_WINDOW", self.cleanup)


    def add_status_message(self, message):
        self.status_text.config(state='normal')
        self.status_text.insert('end', f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.status_text.see('end')
        self.status_text.config(state='disabled')
        self.root.update_idletasks()

    def create_service_panel(self, parent, service_name):
        frame = ttk.LabelFrame(parent, text=service_name)
        frame.pack(fill='x', padx=5, pady=5)

        self.service_status_labels[service_name] = ttk.Label(frame, text="●", foreground="red")
        self.service_status_labels[service_name].pack(side='left', padx=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='right', padx=5)

        buttons = {
            "Start": lambda s=service_name: self.start_service(s),
            "Stop": lambda s=service_name: self.stop_service(s),
            "Restart": lambda s=service_name: self.restart_service(s),
            "Files": lambda s=service_name: self.open_explorer(s),
            "Logs": lambda s=service_name: self.show_logs(s)
        }

        for text, command in buttons.items():
            ttk.Button(btn_frame, text=text, command=command).pack(side='left', padx=2)

    def create_action_buttons(self, parent):
        buttons = {
            "Start All": self.start_all,
            "Stop All": self.stop_all,
            "Restart All": self.restart_all
        }

        for text, command in buttons.items():
            ttk.Button(parent, text=text, command=command).pack(side='left', padx=5)

    def update_status(self, service_name, color, message=""):
        self.service_status_labels[service_name].configure(foreground=color)
        if message:
            self.add_status_message(f"{service_name}: {message}")

    def verify_mongodb_startup(self, service_name):
        """Verify MongoDB startup and update status."""
        max_attempts = 30
        attempts = 0
        log_path = self.commands[service_name]["log_path"]

        while attempts < max_attempts:
            try:
                mongod_running = any(proc.info['name'] == 'mongod.exe' for proc in psutil.process_iter(['name']))
                if not mongod_running:
                    attempts += 1
                    time.sleep(1)
                    continue

                if os.path.exists(log_path):
                    with open(log_path, 'r') as f:
                        if "Waiting for connections" in f.read():
                            self.service_started(service_name)  # Use the callback
                            return

                attempts += 1
                time.sleep(1)
            except Exception as e:
                self.add_status_message(f"Error verifying {service_name} startup: {e}")
                return

        self.add_status_message(f"{service_name} failed to start within timeout.")
        self.update_status(service_name, "red", "Service failed to start")



    def verify_nginx_startup(self, service_name):
        """Verify Nginx startup."""
        max_attempts = 10
        for attempt in range(max_attempts):
            time.sleep(1)
            try:
                for proc in psutil.process_iter(['name']):
                    if proc.info['name'] == 'nginx.exe':
                        self.service_started(service_name)
                        return
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass  # These exceptions are expected
            except Exception as e:
                self.add_status_message(f"Error verifying {service_name}: {e}")
                self.update_status(service_name, "red", "Startup verification error")
                return
        self.update_status(service_name, "red", "Failed to start")


    def execute_command(self, service_name, command_type):
        command = self.commands[service_name][command_type]

        def run_command():
            try:
                creationflags = subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
                subprocess.Popen(command, creationflags=creationflags) # No need to wait here.

                if command_type == 'start':
                    if service_name == "MongoDB":
                        self.verify_mongodb_startup(service_name)  # Verify MongoDB
                    elif service_name == "Nginx":
                         self.verify_nginx_startup(service_name)

                elif command_type == 'stop':
                    # ALWAYS call verify_stop, even for Nginx.  This is the core change.
                    time.sleep(0.5)  # Short delay for nginx -s stop to attempt
                    self.verify_stop(service_name)


            except Exception as e:
                self.add_status_message(f"Error executing {command_type} for {service_name}: {e}")
                self.update_status(service_name, "red", "Command execution error")

        threading.Thread(target=run_command, daemon=True).start()

    def start_service(self, service_name):
        self.update_status(service_name, "orange", "Starting...")
        self.execute_command(service_name, "start")

    def service_started(self, service_name):
        with self.lock:
            self.running_services.add(service_name)
        self.update_status(service_name, "green", "Running")

    def stop_service(self, service_name):
        self.update_status(service_name, "orange", "Stopping...")
        self.execute_command(service_name, "stop") # Execute "nginx -s stop"

    def verify_stop(self, service_name):
        """Verifies if a service has stopped (handles Nginx and others)."""
        process_name = "mongod.exe" if service_name == "MongoDB" else "nginx.exe"
        max_attempts = 10  # Limit attempts

        for _ in range(max_attempts):
            try:
                processes = [proc for proc in psutil.process_iter(['name']) if proc.info['name'] == process_name]
                if not processes:
                    self.service_stopped(service_name)
                    return

                # Kill ALL matching processes (this is the key for Nginx on Windows)
                for proc in processes:
                    try:
                        proc.kill()  # Use psutil's kill() for reliable termination
                    except psutil.NoSuchProcess:
                        pass  # Process already terminated
                    except psutil.AccessDenied:
                        self.add_status_message(f"Access denied while stopping {service_name}")
                        self.update_status(service_name,"red", "Access Denied")
                        return
                    except Exception as e:
                        self.add_status_message(f"Error killing {service_name} process: {e}")
                        self.update_status(service_name, "red", "Kill error")
                        return


            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass  # Handle expected exceptions
            except Exception as e:
                self.add_status_message(f"Error verifying stop for {service_name}: {e}")
                self.update_status(service_name, "red", "Stop verification error")
                return
            time.sleep(0.5)

        self.update_status(service_name, "orange", f"{service_name} failed to stop completely")


    def service_stopped(self, service_name):
        with self.lock:
            self.running_services.discard(service_name)  # Use discard for safety
        self.update_status(service_name, "red", "Stopped")

    def restart_service(self, service_name):
        self.add_status_message(f"Restarting {service_name}...")
        self.stop_service(service_name)
        self.root.after(1000, lambda: self.start_service(service_name)) # Use a lambda

    def start_all(self):
        self.add_status_message("Starting all services...")
        for service_name in self.commands:
            self.start_service(service_name)

    def stop_all(self):
        self.add_status_message("Stopping all services...")
        for service_name in list(self.running_services):  # Iterate over a copy
            self.stop_service(service_name)

    def restart_all(self):
        self.add_status_message("Restarting all services...")
        self.stop_all()
        self.root.after(2000, self.start_all)

    def open_explorer(self, service_name):
        log_path = self.commands[service_name]["log_path"]
        try:
            path = os.path.dirname(os.path.abspath(log_path))
            os.startfile(path)
            self.add_status_message(f"Opened explorer for {service_name}")
        except Exception as e:
            self.add_status_message(f"Failed to open explorer: {e}")

    def show_logs(self, service_name):
        log_path = self.commands[service_name]["log_path"]
        log_window = tk.Toplevel(self.root)
        log_window.title(f"{service_name} Logs")
        log_window.geometry("800x600")

        text_area = tk.Text(log_window, wrap=tk.NONE)
        text_area.pack(expand=True, fill='both')

        y_scrollbar = ttk.Scrollbar(log_window, orient='vertical', command=text_area.yview)
        x_scrollbar = ttk.Scrollbar(log_window, orient='horizontal', command=text_area.xview)
        y_scrollbar.pack(side='right', fill='y')
        x_scrollbar.pack(side='bottom', fill='x')
        text_area.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        def refresh_logs():
            try:
                with open(log_path, 'r') as f:
                    text_area.delete(1.0, tk.END)
                    text_area.insert(tk.END, f.read())
                    text_area.see(tk.END)
                self.add_status_message(f"Refreshed {service_name} logs")
            except Exception as e:
                error_msg = f"Error reading log file: {e}"
                text_area.delete(1.0, tk.END)
                text_area.insert(tk.END, error_msg)
                self.add_status_message(error_msg)

        ttk.Button(log_window, text="Refresh", command=refresh_logs).pack(pady=5)
        refresh_logs()

    def show_warning(self):
        messagebox.showerror("Error", "This application only runs on Windows!")

    def cleanup(self):
        self.add_status_message("Cleaning up and shutting down...")
        self.stop_all()
        self.root.after(2000, self.root.destroy)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = ServiceManager()
    app.run()