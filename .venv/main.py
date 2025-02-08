import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys
import time
from pathlib import Path
import platform
import psutil
from tkinter.font import Font
import json

class ServiceManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DevTools Manager")
        self.root.geometry("1000x700")

        # --- Set Icon ---
        # Use a .ico file for best compatibility (Windows)
        icon_path = "favicon.ico"  # Replace with your icon file's path

        if os.path.exists(icon_path):  # Check if the icon file exists
            if platform.system() == 'Windows':
                self.root.iconbitmap(icon_path) # For taskbar and title bar
            else:
                # For other platforms (e.g., Linux, macOS)
                try:
                    img = tk.PhotoImage(file=icon_path)
                    self.root.iconphoto(True, img)  # Title Bar
                except tk.TclError:
                    print("Warning: Could not load icon on this platform.")
                    # You could fall back to a default icon here if necessary

        else:
            print(f"Warning: Icon file not found at {icon_path}")
        # --- End Set Icon ---

        # Modern dark theme colors
        self.colors = {
            'bg': '#1a1b1e',
            'card': '#25262b',
            'hover': '#2c2e33',
            'primary': '#3b82f6',
            'primary_hover': '#2563eb',
            'success': '#22c55e',
            'warning': '#eab308',
            'error': '#ef4444',
            'text': '#ffffff',
            'text_secondary': '#9ca3af',
            'pending': '#eab308',
            'running': '#22c55e',
            'stopped': '#ef4444',
            'stop_btn': '#ef4444',
            'restart_btn' : '#eab308',
            'files_btn' : '#3b82f6',
            'logs_btn' : '#22c55e'
        }

        # Initialize variables
        self.service_status_labels = {}
        self.running_services = set()
        self.lock = threading.Lock()

        self.commands = {
            "MongoDB": {
                "start": ["mongodb\\bin\\mongod.exe", "--quiet", "--dbpath=mongodb\\local",
                          "--logpath=mongodb\\mongo.log", "--logappend"],
                "stop": ["taskkill", "/F", "/IM", "mongod.exe"],
                "log_path": "mongodb\\mongo.log",
                "service_path": "mongodb",
                "icon": "🍃"
            },
            "Nginx": {
                "start": ["nginx\\nginx.exe", "-c", "nginx\\conf\\nginx.conf",
                          "-e", "./nginx/logs/error.log"],
                "stop": ["nginx\\nginx.exe", "-s", "stop"],
                "log_path": "nginx\\logs\\error.log",
                "service_path": "nginx",
                "icon": "🌐"
            }
        }
        # Configure modern styles
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.setup_styles()

        self.setup_ui()

    def setup_ui(self):
        # Main container
        main_container = ttk.Frame(self.root, style='Dark.TFrame')
        main_container.pack(expand=True, fill='both', padx=20, pady=20)

        # Header
        header = ttk.Frame(main_container, style='Dark.TFrame')
        header.pack(fill='x', pady=(0, 20))

        title = tk.Label(
            header,
            text="DevTools Manager",
            font=('Segoe UI', 24, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        title.pack(side='left')

        # Global actions
        actions = ttk.Frame(header, style='Dark.TFrame')
        actions.pack(side='right')

        for action in [("Start All", self.start_all),
                       ("Stop All", self.stop_all),
                       ("Restart All", self.restart_all)]:
            btn = ttk.Button(
                actions,
                text=action[0],
                style='Modern.TButton',
                command=action[1]
            )
            btn.pack(side='left', padx=5)

        # Services grid
        services_container = ttk.Frame(main_container, style='Dark.TFrame')
        services_container.pack(fill='both', expand=True)

        for idx, service_name in enumerate(self.commands):
            self.create_service_card(services_container, service_name, row=idx)

        # Status panel
        self.setup_status_panel(main_container)

    def setup_styles(self):
        # Main window style
        self.root.configure(bg=self.colors['bg'])

        # Custom button style
        self.style.configure(
            'Modern.TButton',
            background=self.colors['primary'],
            foreground=self.colors['text'],
            padding=(15, 8),
            font=('Segoe UI', 9),
            borderwidth=0
        )
        self.style.map(
            'Modern.TButton',
            background=[('active', self.colors['primary_hover'])]
        )

        # Secondary button style
        self.style.configure(
            'Secondary.TButton',
            background=self.colors['card'],
            foreground=self.colors['text'],
            padding=(12, 6),
            font=('Segoe UI', 9),
            borderwidth=0
        )
        self.style.map(
            'Secondary.TButton',
            background=[('active', self.colors['hover'])]
        )

        # ---  Colored Button Styles ---
        self.style.configure(
            'Stop.TButton',
            background=self.colors['stop_btn'],
            foreground=self.colors['text'],
            padding=(12, 6),
            font=('Segoe UI', 9),
            borderwidth=0
        )
        self.style.map('Stop.TButton', background=[('active', self.colors['error'])])


        self.style.configure(
            'Restart.TButton',
            background=self.colors['restart_btn'],
            foreground=self.colors['text'],
            padding=(12, 6),
            font=('Segoe UI', 9),
            borderwidth=0
        )
        self.style.map('Restart.TButton', background=[('active', self.colors['warning'])])

        self.style.configure(
            'Files.TButton',
            background=self.colors['files_btn'],
            foreground=self.colors['text'],
            padding=(12, 6),
            font=('Segoe UI', 9),
            borderwidth=0
        )
        self.style.map('Files.TButton', background=[('active', self.colors['primary'])])

        self.style.configure(
            'Logs.TButton',
            background=self.colors['logs_btn'],
            foreground=self.colors['text'],
            padding=(12, 6),
            font=('Segoe UI', 9),
            borderwidth=0
        )
        self.style.map('Logs.TButton', background=[('active', self.colors['success'])])

        # Frame styles
        self.style.configure(
            'Dark.TFrame',
            background=self.colors['bg']
        )
        self.style.configure(
            'Card.TFrame',
            background=self.colors['card']
        )

        # Label styles
        self.style.configure(
            'Dark.TLabel',
            background=self.colors['bg'],
            foreground=self.colors['text'],
            font=('Segoe UI', 10)
        )

    def setup_status_panel(self, parent):
        status_frame = ttk.Frame(parent, style='Card.TFrame')
        status_frame.pack(fill='x', pady=(20, 0))

        status_header = ttk.Frame(status_frame, style='Card.TFrame')
        status_header.pack(fill='x', padx=15, pady=10)

        status_label = tk.Label(
            status_header,
            text="Status Log",
            font=('Segoe UI', 12, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text']
        )
        status_label.pack(side='left')

        self.status_text = tk.Text(
            status_frame,
            height=6,
            wrap=tk.WORD,
            font=('Consolas', 9),
            bg=self.colors['bg'],
            fg=self.colors['text_secondary'],
            borderwidth=0,
            padx=15,
            pady=10
        )
        self.status_text.pack(fill='x', padx=15, pady=(0, 15))

    def create_service_card(self, parent, service_name, row):
        card = ttk.Frame(parent, style='Card.TFrame')
        card.pack(fill='x', pady=(0, 10), padx=2)

        # Service header
        header = ttk.Frame(card, style='Card.TFrame')
        header.pack(fill='x', padx=15, pady=15)

        icon_label = tk.Label(
            header,
            text=self.commands[service_name]['icon'],
            font=('Segoe UI', 20),
            bg=self.colors['card'],
            fg=self.colors['text']
        )
        icon_label.pack(side='left')

        name_label = tk.Label(
            header,
            text=service_name,
            font=('Segoe UI', 14, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text']
        )
        name_label.pack(side='left', padx=10)

        self.service_status_labels[service_name] = tk.Label(
            header,
            text="●",
            font=('Segoe UI', 14),
            bg=self.colors['card'],
            fg=self.colors['error']
        )
        self.service_status_labels[service_name].pack(side='right')

        # Action buttons
        actions = ttk.Frame(card, style='Card.TFrame')
        actions.pack(fill='x', padx=15, pady=(0, 15))

        buttons = {
            "Start": (lambda s=service_name: self.start_service(s), 'Modern.TButton'),
            "Stop": (lambda s=service_name: self.stop_service(s), 'Stop.TButton'),
            "Restart": (lambda s=service_name: self.restart_service(s), 'Restart.TButton'),
            "Files": (lambda s=service_name: self.open_explorer(s), 'Files.TButton'),
            "Logs": (lambda s=service_name: self.show_logs(s), 'Logs.TButton')
        }

        for text, (command, style) in buttons.items():
            btn = ttk.Button(
                actions,
                text=text,
                style=style,
                command=command
            )
            btn.pack(side='left', padx=(0, 5))

    def add_status_message(self, message):
        self.status_text.configure(state='normal')
        timestamp = time.strftime('%H:%M:%S')
        self.status_text.insert('end', f"[{timestamp}] {message}\n")
        self.status_text.see('end')
        self.status_text.configure(state='disabled')
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

    def update_status(self, service_name, status, message=""):
        status_colors = {
            'running': 'running',
            'stopped': 'stopped',
            'starting': 'pending',
            'stopping': 'pending',
            'pending': 'pending',
            'error': 'stopped'
        }

        color = status_colors.get(status, 'stopped')
        self.service_status_labels[service_name].configure(fg=self.colors[color])

        if message:
            self.add_status_message(f"{service_name}: {message}")

    def verify_mongodb_startup(self, service_name):
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
                            self.service_started(service_name)
                            return

                attempts += 1
                time.sleep(1)
            except Exception as e:
                self.add_status_message(f"Error verifying {service_name} startup: {e}")
                return

        self.add_status_message(f"{service_name} failed to start within timeout.")
        self.update_status(service_name, "red", "Service failed to start")

    def verify_nginx_startup(self, service_name):
        max_attempts = 10
        for attempt in range(max_attempts):
            time.sleep(1)
            try:
                for proc in psutil.process_iter(['name']):
                    if proc.info['name'] == 'nginx.exe':
                        self.service_started(service_name)
                        return
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
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
                subprocess.Popen(command, creationflags=creationflags)

                if command_type == 'start':
                    if service_name == "MongoDB":
                        self.verify_mongodb_startup(service_name)
                    elif service_name == "Nginx":
                         self.verify_nginx_startup(service_name)

                elif command_type == 'stop':
                    time.sleep(0.5)
                    self.verify_stop(service_name)

            except Exception as e:
                self.add_status_message(f"Error executing {command_type} for {service_name}: {e}")
                self.update_status(service_name, "red", "Command execution error")

        threading.Thread(target=run_command, daemon=True).start()

    def start_service(self, service_name):
        self.update_status(service_name, "starting", "Starting...")
        self.execute_command(service_name, "start")

    def service_started(self, service_name):
        with self.lock:
            self.running_services.add(service_name)
        self.update_status(service_name, "running", "Running")

    def stop_service(self, service_name):
        self.update_status(service_name, "stopping", "Stopping...")
        self.execute_command(service_name, "stop")

    def verify_stop(self, service_name):
        process_name = "mongod.exe" if service_name == "MongoDB" else "nginx.exe"
        max_attempts = 10

        for _ in range(max_attempts):
            try:
                processes = [proc for proc in psutil.process_iter(['name']) if proc.info['name'] == process_name]
                if not processes:
                    self.service_stopped(service_name)
                    return

                for proc in processes:
                    try:
                        proc.kill()
                    except psutil.NoSuchProcess:
                        pass
                    except psutil.AccessDenied:
                        self.add_status_message(f"Access denied while stopping {service_name}")
                        self.update_status(service_name,"red", "Access Denied")
                        return
                    except Exception as e:
                        self.add_status_message(f"Error killing {service_name} process: {e}")
                        self.update_status(service_name, "red", "Kill error")
                        return

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
            except Exception as e:
                self.add_status_message(f"Error verifying stop for {service_name}: {e}")
                self.update_status(service_name, "red", "Stop verification error")
                return
            time.sleep(0.5)

        self.update_status(service_name, "orange", f"{service_name} failed to stop completely")

    def service_stopped(self, service_name):
        with self.lock:
            self.running_services.discard(service_name)
        self.update_status(service_name, "stopped", "Stopped")

    def restart_service(self, service_name):
        self.add_status_message(f"Restarting {service_name}...")
        self.stop_service(service_name)
        self.root.after(1000, lambda: self.start_service(service_name))

    def start_all(self):
        self.add_status_message("Starting all services...")
        for service_name in self.commands:
            self.start_service(service_name)

    def stop_all(self):
        self.add_status_message("Stopping all services...")
        for service_name in list(self.running_services):
            self.stop_service(service_name)

    def restart_all(self):
        self.add_status_message("Restarting all services...")
        self.stop_all()
        self.root.after(2000, self.start_all)

    def open_explorer(self, service_name):
        service_path = self.commands[service_name]["service_path"]
        try:
            path = os.path.abspath(service_path)
            os.startfile(path)
            self.add_status_message(f"Opened explorer for {service_name} at {path}")
        except Exception as e:
            self.add_status_message(f"Failed to open explorer: {e}")

    def show_logs(self, service_name):
        log_window = tk.Toplevel(self.root)
        log_window.title(f"{service_name} Logs")
        log_window.geometry("900x600")
        log_window.configure(bg=self.colors['bg'])

        log_frame = ttk.Frame(log_window, style='Card.TFrame')
        log_frame.pack(expand=True, fill='both', padx=20, pady=20)

        header = ttk.Frame(log_frame, style='Card.TFrame')
        header.pack(fill='x', padx=15, pady=15)

        title = tk.Label(
            header,
            text=f"{self.commands[service_name]['icon']} {service_name} Logs",
            font=('Segoe UI', 16, 'bold'),
            bg=self.colors['card'],
            fg=self.colors['text']
        )
        title.pack(side='left')

        refresh_btn = ttk.Button(
            header,
            text="Refresh",
            style='Modern.TButton',
            command=lambda: self.refresh_logs(text_area, service_name)
        )
        refresh_btn.pack(side='right')

        text_area = tk.Text(
            log_frame,
            wrap=tk.NONE,
            font=('Consolas', 10),
            bg=self.colors['bg'],
            fg=self.colors['text'],
            padx=15,
            pady=15
        )
        text_area.pack(expand=True, fill='both', padx=15, pady=(0, 15))
        y_scrollbar = ttk.Scrollbar(text_area, orient='vertical', command=text_area.yview)
        y_scrollbar.pack(side=tk.RIGHT, fill= tk.Y)
        x_scrollbar = ttk.Scrollbar(text_area, orient='horizontal', command=text_area.xview)
        x_scrollbar.pack(side=tk.BOTTOM, fill= tk.X)
        text_area.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        self.refresh_logs(text_area, service_name)

    def refresh_logs(self, text_widget, service_name):
        log_path = self.commands[service_name]["log_path"]
        try:
            with open(log_path, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            content = "Log file not found."
        except Exception as e:
            content = f"Error reading log file: {e}"

        text_widget.config(state=tk.NORMAL)
        text_widget.delete('1.0', tk.END)
        text_widget.insert('1.0', content)
        text_widget.config(state=tk.DISABLED)

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