import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys
import time
from pathlib import Path
import platform
import re
import psutil


class ServiceManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DevTool")
        self.root.geometry("600x400")

        # Add icon
        try:
            # Check if running as a bundled executable (e.g., using PyInstaller)
            if getattr(sys, 'frozen', False):
                # If bundled, use the resource path
                icon_path = os.path.join(sys._MEIPASS, "favicon.ico")
            else:
                # If running as a script, use the script's directory
                icon_path = "favicon.ico"

            self.root.iconbitmap(icon_path)
        except tk.TclError:
            print("Error: Could not find icon file.  Make sure it's in the correct location.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        # Store service status labels
        self.service_status_labels = {}

        # Keep track of which services are running
        self.running_services = set()

        # Use a lock to synchronize access to shared resources (running_services)
        self.lock = threading.Lock()

        # Service commands
        self.commands = {
            "MongoDB": {
                "start": ["mongodb\\bin\\mongod.exe", "--quiet", "--dbpath=mongodb\\local", "--logpath=mongodb\\mongo.log",
                          "--logappend"],
                "stop": ["taskkill", "/F", "/IM", "mongod.exe"],
                "log_path": "mongodb\\mongo.log"
            },
            "Apache": {
                "start": ["apache\\bin\\httpd.exe", "-d", "apache\\"],
                "stop": ["taskkill", "/F", "/IM", "httpd.exe"],
                "log_path": "apache\\logs\\error.log"
            }
        }

        # Check if running on Windows
        if not platform.system().lower().startswith('win'):
            self.show_warning()
            return

        self.setup_ui()

    def setup_ui(self):
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(expand=True, fill='both', padx=5, pady=5)

        # Status message area
        self.status_frame = ttk.LabelFrame(main_container, text="Status Messages")
        self.status_frame.pack(fill='x', padx=5, pady=5)

        self.status_text = tk.Text(self.status_frame, height=4, wrap=tk.WORD)
        self.status_text.pack(fill='x', padx=5, pady=5)
        self.status_text.config(state='disabled')

        # Services panel
        services_panel = ttk.Frame(main_container)
        services_panel.pack(expand=True, fill='both', padx=5, pady=5)

        # Create service panels
        for service_name in self.commands:
            self.create_service_panel(services_panel, service_name)

        # Action buttons panel
        action_panel = ttk.Frame(main_container)
        action_panel.pack(fill='x', padx=5, pady=5)

        # Create action buttons
        self.create_action_buttons(action_panel)

        # Bind cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self.cleanup)

    def add_status_message(self, message):
        timestamp = time.strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
        self.status_text.config(state='normal')
        self.status_text.insert('end', full_message)
        self.status_text.see('end')
        self.status_text.config(state='disabled')
        self.root.update_idletasks()

    def create_service_panel(self, parent, service_name):
        frame = ttk.LabelFrame(parent, text=service_name)
        frame.pack(fill='x', padx=5, pady=5)

        status_label = ttk.Label(frame, text="●", foreground="red")
        status_label.pack(side='left', padx=5)
        self.service_status_labels[service_name] = status_label

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='right', padx=5)

        buttons = {
            "Start": lambda s=service_name: self.start_service(s),  # Use default argument
            "Stop": lambda s=service_name: self.stop_service(s),
            "Restart": lambda s=service_name: self.restart_service(s),
            "Files": lambda s=service_name: self.open_explorer(s),
            "Logs": lambda s=service_name: self.show_logs(s)
        }

        for text, command in buttons.items():
            btn = ttk.Button(btn_frame, text=text, command=command)
            btn.pack(side='left', padx=2)

    def create_action_buttons(self, parent):
        buttons = {
            "Start All": self.start_all,
            "Stop All": self.stop_all,
            "Restart All": self.restart_all
        }

        for text, command in buttons.items():
            btn = ttk.Button(parent, text=text, command=command)
            btn.pack(side='left', padx=5)

    def update_status(self, service_name, color, message=""):
        label = self.service_status_labels[service_name]
        label.configure(foreground=color)
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


    def verify_apache_startup(self, service_name):
        """Verify Apache startup and update status."""
        max_attempts = 30
        attempts = 0

        while attempts < max_attempts:
            time.sleep(1)  # Check every second
            try:
                # More robust process check using psutil.process_iter()
                for process in psutil.process_iter(['pid', 'name']):
                    try:
                        if process.info['name'] == 'httpd.exe':
                            # Apache is running!
                            self.service_started(service_name)
                            return  # Exit the verification loop

                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        # Handle exceptions that might occur while iterating processes
                        pass

            except Exception as e:
                self.add_status_message(f"Error verifying {service_name} startup: {str(e)}")
                return  # Exit on error

            attempts += 1

        # If we reach here, Apache didn't start within the timeout
        self.add_status_message(f"{service_name} failed to start within timeout period")
        self.update_status(service_name, "red", "Service failed to start")


    def execute_command(self, service_name, command_type):
        """Executes a command and handles output/errors."""
        command = self.commands[service_name][command_type]

        def run_command():
            try:
                creation_flags = subprocess.CREATE_NO_WINDOW if platform.system().lower().startswith('win') else 0
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           universal_newlines=True, creationflags=creation_flags)

                # Special handling for start commands
                if command_type == "start":
                    if service_name == "MongoDB":
                        self.verify_mongodb_startup(service_name)
                    elif service_name == "Apache":
                        self.verify_apache_startup(service_name)
                elif command_type == "stop":
                    stdout, stderr = process.communicate()  # Wait for stop command
                    time.sleep(1) # short wait
                    self.verify_stop(service_name)

            except Exception as e:
                error_msg = f"Error executing {command_type} for {service_name}: {e}"
                self.add_status_message(error_msg)
                self.root.after(0, lambda: messagebox.showerror("Error", error_msg))

        threading.Thread(target=run_command, daemon=True).start()


    def start_service(self, service_name):
        """Starts a single service."""
        self.update_status(service_name, "orange", "Starting service...")
        self.execute_command(service_name, "start")

    def service_started(self, service_name):
        """Handles successful service start."""
        with self.lock:  # Acquire lock
            self.running_services.add(service_name)
        self.update_status(service_name, "green", "Service started successfully")


    def stop_service(self, service_name):
        """Stops a single service."""
        self.update_status(service_name, "orange", "Stopping service...")
        self.execute_command(service_name, "stop") # No callback needed here now


    def verify_stop(self, service_name):
        """Verifies if a service has stopped and updates the UI."""
        process_name = "mongod.exe" if service_name == "MongoDB" else "httpd.exe"
        service_stopped = all(proc.info['name'] != process_name for proc in psutil.process_iter(['name']))

        if service_stopped:
            self.service_stopped(service_name)  # Use consistent callback
        else:
            self.update_status(service_name, "orange", "Service failed to stop completely")

    def service_stopped(self, service_name):
        """Handles successful service stop."""
        with self.lock:  # Acquire lock
            if service_name in self.running_services:
                self.running_services.remove(service_name)
        self.update_status(service_name, "red", "Service stopped successfully")

    def restart_service(self, service_name):
        """Restarts a single service."""
        self.add_status_message(f"Restarting {service_name}...")
        self.stop_service(service_name)
        # Delay start to ensure the previous instance is fully stopped.
        self.root.after(2000, lambda s=service_name: self.start_service(s))

    def start_all(self):
        """Starts all services."""
        self.add_status_message("Starting all services...")
        for service_name in self.commands:
            self.start_service(service_name)

    def stop_all(self):
        """Stops all running services."""
        self.add_status_message("Stopping all services...")
        with self.lock:
            services_to_stop = list(self.running_services) # Create a list

        for service_name in services_to_stop:
            self.stop_service(service_name)


    def restart_all(self):
        """Restarts all services."""
        self.add_status_message("Restarting all services...")
        self.stop_all()
        self.root.after(3000, self.start_all)  # Increased delay for all services


    def open_explorer(self, service_name):
        log_path = self.commands[service_name]["log_path"]
        try:
            path = os.path.dirname(os.path.abspath(log_path))
            os.startfile(path)
            self.add_status_message(f"Opened file explorer for {service_name}")
        except Exception as e:
            error_msg = f"Failed to open explorer: {str(e)}"
            self.add_status_message(error_msg)
            messagebox.showerror("Error", error_msg)

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
                self.add_status_message(f"Refreshed logs for {service_name}")
            except Exception as e:
                error_msg = f"Error reading log file: {str(e)}"
                text_area.delete(1.0, tk.END)
                text_area.insert(tk.END, error_msg)
                self.add_status_message(error_msg)

        refresh_btn = ttk.Button(log_window, text="Refresh", command=refresh_logs)
        refresh_btn.pack(pady=5)

        refresh_logs()

    def show_warning(self):
        warning_window = tk.Tk()
        warning_window.withdraw()
        messagebox.showerror("Error", "This application only runs on Windows!")
        warning_window.after(5000, warning_window.destroy)

    def cleanup(self):
        self.add_status_message("Cleaning up and shutting down...")
        self.stop_all()
        self.root.after(3000, self.root.destroy)  # Increased delay for all services

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ServiceManager()
    app.run()