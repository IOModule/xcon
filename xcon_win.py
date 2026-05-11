import sys
import os
import subprocess
import json
import socket
import threading
import time
from datetime import datetime
import requests
import psutil

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QPoint
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                             QSystemTrayIcon, QMenu, QGraphicsDropShadowEffect)
from PyQt6.QtGui import QColor, QFont, QAction, QIcon

# --- Configuration ---
CHECK_INTERVAL = 2.0  # Seconds between connection checks
DISPLAY_TIME = 10000  # 10 seconds in milliseconds
MAX_HISTORY = 10
NEON_CYAN = "#00f2ff"
NEON_GREEN = "#39ff14"
NEON_MAGENTA = "#ff00ff"

# --- Helper Functions ---

def get_company_info(pid):
    """Get process info on Windows using psutil"""
    try:
        proc = psutil.Process(pid)
        # Windows doesn't have a simple 'codesign' CLI like Mac, 
        # but we can get the username or path as a proxy for identity
        return proc.username() if hasattr(proc, 'username') else "System Process"
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

# --- UI Components ---

class NotificationPopup(QWidget):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.init_ui()
        
    def init_ui(self):
        # Windows-friendly flags - prevent focus stealing
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.ToolTip |
                            Qt.WindowType.WindowDoesNotAcceptFocus)
        
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(layout)
        
        # Process Name (Neon Cyan)
        self.proc_label = QLabel(f"PROCESS: {self.data['process'].upper()}")
        self.proc_label.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        self.proc_label.setStyleSheet(f"color: {NEON_CYAN}; background: transparent;")
        layout.addWidget(self.proc_label)
        
        # Identity/User (Neon Magenta)
        self.comp_label = QLabel(f"USER: {self.data.get('company', 'Unknown')}")
        self.comp_label.setFont(QFont("Consolas", 10))
        self.comp_label.setStyleSheet(f"color: {NEON_MAGENTA}; background: transparent;")
        layout.addWidget(self.comp_label)
        
        # Location (Neon Green)
        self.loc_label = QLabel(f"LOCATION: {self.data['location']}")
        self.loc_label.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        self.loc_label.setStyleSheet(f"color: {NEON_GREEN}; background: transparent;")
        layout.addWidget(self.loc_label)
        
        # Window styling - SOLID BLACK with Neon Border
        self.setStyleSheet(f"""
            QWidget {{
                background-color: #000000;
                border: 2px solid {NEON_CYAN};
                border-radius: 10px;
            }}
            QLabel {{
                color: white;
                background: transparent;
            }}
        """)
        
        # Positioning (Bottom Right for Windows)
        screen = QApplication.primaryScreen().availableGeometry()
        width, height = 360, 150
        self.setFixedSize(width, height)
        x = screen.width() - width - 20
        y = screen.height() - height - 50
        self.move(x, y)
        
        # Simple timer to close
        self.close_timer = QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(self.close)
        self.close_timer.start(DISPLAY_TIME)

# --- Monitor Thread ---

class ConnectionMonitor(QThread):
    new_connection = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.seen_ips = set()
        self.running = True
        
    def run(self):
        # Initial scan
        self.scan(initial=True)
        
        while self.running:
            self.scan()
            time.sleep(CHECK_INTERVAL)
            
    def scan(self, initial=False):
        try:
            # Use psutil for cross-platform connection tracking
            connections = psutil.net_connections(kind='inet')
            for conn in connections:
                if conn.status == 'ESTABLISHED' and conn.remote_address:
                    ip = conn.remote_address.ip
                    pid = conn.pid
                    self.process_conn(ip, pid, initial)
        except Exception as e:
            print(f"Monitor error: {e}")

    def process_conn(self, ip, pid, initial):
        if not ip or ip == '127.0.0.1' or ip == '::1': return
        # Filter private IPs
        if (ip.startswith('192.168.') or ip.startswith('10.') or ip.startswith('172.')):
            return
            
        if ip not in self.seen_ips:
            self.seen_ips.add(ip)
            
            if not initial:
                proc_name = "Unknown"
                if pid:
                    try:
                        proc_name = psutil.Process(pid).name()
                    except:
                        pass
                
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
        self.setQuitOnLastWindowClosed(False)
        
        self.history = []
        self.active_popups = []
        
        # Tray Icon
        self.tray = QSystemTrayIcon(self)
        icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
        self.tray.setIcon(icon)
        self.tray.setToolTip("X-Con Windows Monitor")
        
        self.menu = QMenu()
        self.update_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        
        # Start Monitor
        self.monitor = ConnectionMonitor()
        self.monitor.new_connection.connect(self.handle_new_connection)
        self.monitor.start()

    def handle_new_connection(self, data):
        self.history.insert(0, data)
        if len(self.history) > MAX_HISTORY:
            self.history.pop()
        
        self.update_menu()
        
        popup = NotificationPopup(data)
        self.active_popups.append(popup)
        popup.show()
        
        # Cleanup
        self.active_popups = [p for p in self.active_popups if p.isVisible()] 
        
    def update_menu(self):
        self.menu.clear()
        header = self.menu.addAction("X-CON WINDOWS")
        header.setEnabled(False)
        self.menu.addSeparator()
        
        if not self.history:
            self.menu.addAction("No connections yet...").setEnabled(False)
        else:
            for item in self.history:
                text = f"[{item['time']}] {item['process']} -> {item['location']}"
                self.menu.addAction(text)
        
        self.menu.addSeparator()
        quit_action = self.menu.addAction("Quit X-Con")
        quit_action.triggered.connect(self.quit)

    def quit(self):
        self.monitor.running = False
        self.monitor.wait()
        super().quit()

if __name__ == "__main__":
    app = XConApp(sys.argv)
    sys.exit(app.exec())
