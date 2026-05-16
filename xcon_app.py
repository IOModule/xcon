import sys
import os
import subprocess
import json
import socket
import threading
import time
import csv
from datetime import datetime
from pathlib import Path
import requests
import psutil

import ctypes
from ctypes import c_void_p
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QPoint
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                             QSystemTrayIcon, QMenu, QGraphicsDropShadowEffect)
from PyQt6.QtGui import QColor, QFont, QAction, QIcon, QPixmap, QPainter

# Native macOS imports for vibrancy
try:
    from AppKit import (NSVisualEffectView, NSVisualEffectMaterialDark, 
                        NSVisualEffectBlendingModeBehindWindow, NSViewHeightSizable, 
                        NSViewWidthSizable, NSApplication, NSApplicationActivationPolicyAccessory)
    import objc
except ImportError:
    NSVisualEffectView = None

# --- Configuration ---
CHECK_INTERVAL = 2.0  # Seconds between connection checks
DISPLAY_TIME = 10000  # 10 seconds in milliseconds
MAX_HISTORY = 10
NEON_CYAN = "#00f2ff"
NEON_GREEN = "#39ff14"
NEON_MAGENTA = "#ff00ff"

# --- Helper Functions ---

def get_company_info(pid):
    """Get the developer/company info using codesign"""
    try:
        # Get process executable path
        proc = psutil.Process(pid)
        path = proc.exe()
        
        if not path:
            return "Unknown Company"
            
        # Run codesign
        result = subprocess.run(
            ['codesign', '-dvvv', path],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        # Parse output for Authority
        for line in result.stderr.split('\n'):
            if "Authority=Developer ID Application:" in line:
                return line.split(":", 1)[1].split("(", 1)[0].strip()
            elif "Authority=Apple Mac OS Application Signing" in line:
                return "Apple Inc."
            elif "Authority=" in line:
                return line.split("=", 1)[1].split("(", 1)[0].strip()
                
        return "Unsigned Process"
    except Exception:
        return "System / Unknown"

def get_location_info(ip):
    """Get geographic info for an IP address"""
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,country,city,org", timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return {
                    'location': f"{data.get('city')}, {data.get('country')}",
                    'org': data.get('org', 'Unknown ISP')
                }
    except Exception:
        pass
    return {'location': 'Unknown Location', 'org': 'Unknown ISP'}

# --- Helper Functions ---

class ConnectionMonitor(QThread):
    new_connection = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.seen_ips = set()
        self.running = True
        
    def run(self):
        # Initial scan to populate seen_ips
        self.scan(initial=True)
        
        while self.running:
            self.scan()
            time.sleep(CHECK_INTERVAL)
            
    def scan(self, initial=False):
        try:
            # Step 1: Get all established connections with PIDs using lsof (more direct)
            found_connections = []
            try:
                # -n (no DNS), -P (no port names), -i (internet)
                result = subprocess.run(['lsof', '-i', '-n', '-P'], capture_output=True, text=True, timeout=3)
                for line in result.stdout.split('\n'):
                    if 'ESTABLISHED' in line:
                        parts = line.split()
                        if len(parts) >= 9:
                            proc_name = parts[0]
                            pid = int(parts[1])
                            remote = parts[8]
                            if '->' in remote:
                                ip = remote.split('->')[1].rsplit(':', 1)[0].strip('[]')
                                found_connections.append({'ip': ip, 'pid': pid, 'proc_name': proc_name})
            except Exception as e:
                print(f"Lsof scan error: {e}")

            # Step 2: Use netstat as a fallback for IPs only if lsof missed some
            try:
                ns_result = subprocess.run(['netstat', '-an', '-f', 'inet'], capture_output=True, text=True, timeout=3)
                for line in ns_result.stdout.split('\n'):
                    if 'ESTABLISHED' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            remote = parts[4]
                            if '.' in remote:
                                ip = remote.rsplit('.', 1)[0]
                                if ip.count('.') >= 3:
                                    # Check if we already have this IP from lsof
                                    if not any(c['ip'] == ip for c in found_connections):
                                        found_connections.append({'ip': ip, 'pid': None, 'proc_name': "Network Process"})
            except Exception:
                pass

            # Step 3: Process found connections
            for conn in found_connections:
                self.process_conn(conn['ip'], conn['pid'], initial, conn['proc_name'])
                
        except Exception as e:
            print(f"Monitor error: {e}")

    def process_conn(self, ip, pid, initial, proc_name=None):
        if not ip or ip == '*' or ip == '0.0.0.0': return
        # Filter private IPs
        if (ip.startswith('127.') or ip.startswith('192.168.') or 
            ip.startswith('10.') or ip.startswith('172.')):
            return
            
        if ip not in self.seen_ips:
            self.seen_ips.add(ip)
            
            if not initial:
                # Try harder to get the process name if it's generic
                if (proc_name == "Network Process" or not proc_name) and pid:
                    try:
                        proc_name = psutil.Process(pid).name()
                    except:
                        pass
                
                print(f"DEBUG: New connection! {proc_name} -> {ip}")
                threading.Thread(target=self.fetch_details, args=(ip, proc_name, pid)).start()

    def fetch_details(self, ip, proc_name, pid):
        company = get_company_info(pid) if pid else "Unknown"
        loc_data = get_location_info(ip)
        
        data = {
            'process': proc_name,
            'company': company,
            'ip': ip,
            'location': loc_data['location'],
            'org': loc_data['org'],
            'time': datetime.now().strftime("%H:%M:%S")
        }
        self.new_connection.emit(data)

# --- Main App ---

class XConApp(QApplication):
    def __init__(self, args):
        super().__init__(args)
        
        # Paths
        self.history_file = Path("~/xcon_history.csv").expanduser()
        
        # Set macOS Activation Policy to Accessory
        if NSVisualEffectView:
            try:
                ns_app = NSApplication.sharedApplication()
                ns_app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
            except Exception as e:
                print(f"Failed to set activation policy: {e}")
                
        print("X-Con App initializing...")
        self.setQuitOnLastWindowClosed(False)
        
        self.history = []
        
        # Tray Icon availability check
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("Error: System tray is not available on this system.")
        
        # Tray Icon
        self.tray = QSystemTrayIcon(self)
        
        # Create custom "XN" Icon
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.GlobalColor.black) # Use black for the template
        font = QFont("Helvetica", 36, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "XN")
        painter.end()
        
        icon = QIcon(pixmap)
        icon.setIsMask(True) # This makes it a template icon on macOS (auto-colors)
        self.tray.setIcon(icon)
        self.tray.setToolTip("X-Con Network Monitor")
        
        self.menu = QMenu()
        self.update_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        
        # Start Monitor
        self.monitor = ConnectionMonitor()
        self.monitor.new_connection.connect(self.handle_new_connection)
        self.monitor.start()
        print("Initialization complete.")
        
        # Test notification
        QTimer.singleShot(2000, lambda: self.handle_new_connection({
            'process': 'System Test',
            'company': 'X-Con Monitor',
            'ip': '1.1.1.1',
            'location': 'Digital Space',
            'org': 'Cloudflare',
            'time': datetime.now().strftime("%H:%M:%S")
        }))

    def log_to_csv(self, data):
        """Save connection to local CSV"""
        file_exists = self.history_file.exists()
        try:
            with open(self.history_file, mode='a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['Timestamp', 'Process', 'Company', 'IP', 'Location', 'ISP'])
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    data['process'],
                    data['company'],
                    data['ip'],
                    data['location'],
                    data['org']
                ])
            # Auto-sync after each log
            self.sync_to_cloud()
        except Exception as e:
            print(f"Failed to log to CSV: {e}")

    def sync_to_cloud(self):
        """Sync CSV to Google Drive using rclone"""
        def sync_task():
            try:
                subprocess.run(["rclone", "copy", str(self.history_file), "Sys:xcon_history/"], check=True)
            except Exception as e:
                print(f"Cloud sync failed: {e}")
        
        # Run in separate thread to not block UI
        threading.Thread(target=sync_task, daemon=True).start()

    def send_notification(self, data):
        """Send native macOS notification with sound and severity"""
        # Determine Severity
        is_suspicious = data['company'] == "Unsigned Process"
        
        title = f"⚠️ SECURITY ALERT" if is_suspicious else f"🌐 NEW CONNECTION"
        subtitle = f"{data['process'].upper()} ({data['company']})"
        message = f"Location: {data['location']}\nIP: {data['ip']}"
        
        # Sound: "Basso" for suspicious, "Bottle" for normal
        sound = "Basso" if is_suspicious else "Bottle"
        
        cmd = [
            'osascript', '-e',
            f'display notification "{message}" with title "{title}" subtitle "{subtitle}" sound name "{sound}"'
        ]
        try:
            subprocess.run(cmd, check=True)
        except Exception as e:
            print(f"Notification failed: {e}")

    def handle_new_connection(self, data):
        print(f"New connection: {data['process']} ({data['ip']})")
        
        # Add to history
        self.history.insert(0, data)
        if len(self.history) > MAX_HISTORY:
            self.history.pop()
        
        self.update_menu()
        
        # 1. Log to CSV
        self.log_to_csv(data)
        
        # 2. Send Native Notification
        self.send_notification(data)
        
    def update_menu(self):
        self.menu.clear()
        
        header = self.menu.addAction("X-CON MONITORING")
        header.setEnabled(False)
        self.menu.addSeparator()
        
        # View Log Action
        view_log_action = self.menu.addAction("📂 View History Log (CSV)")
        view_log_action.triggered.connect(self.view_log)
        self.menu.addSeparator()
        
        if not self.history:
            self.menu.addAction("No connections yet...").setEnabled(False)
        else:
            for item in self.history:
                company = item.get('company', 'Unknown')
                # Highlight Unsigned in menu text
                prefix = "🚨 " if company == "Unsigned Process" else ""
                text = f"{prefix}[{item['time']}] {item['process']} ({company}) -> {item['location']}"
                self.menu.addAction(text)
        
        self.menu.addSeparator()
        quit_action = self.menu.addAction("Quit X-Con")
        quit_action.triggered.connect(self.quit)

    def view_log(self):
        """Open the CSV log file with the system default app"""
        if self.history_file.exists():
            try:
                subprocess.run(["open", str(self.history_file)], check=True)
            except Exception as e:
                print(f"Failed to open log: {e}")
        else:
            print("History file does not exist yet.")

    def quit(self):
        self.monitor.running = False
        self.monitor.wait()
        super().quit()

if __name__ == "__main__":
    app = XConApp(sys.argv)
    sys.exit(app.exec())
