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

import ctypes
from ctypes import c_void_p
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QPoint
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                             QSystemTrayIcon, QMenu, QGraphicsDropShadowEffect)
from PyQt6.QtGui import QColor, QFont, QAction, QIcon

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

# --- UI Components ---

class VibrancyHelper:
    @staticmethod
    def apply_vibrancy(widget):
        print(f"Applying vibrancy to {widget}...")
        if NSVisualEffectView is None:
            print("NSVisualEffectView is None, skipping vibrancy.")
            return
            
        try:
            view_ptr = widget.winId()
            print(f"Window ID: {view_ptr}")
            # In PyQt6, winId() returns an integer
            nsview = objc.objc_object(c_void_p=int(view_ptr))
            window = nsview.window()
            print(f"Native Window found: {window}")
            
            # Create the effect view
            effect_view = NSVisualEffectView.alloc().init()
            effect_view.setFrame_(window.contentView().bounds())
            effect_view.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
            effect_view.setMaterial_(NSVisualEffectMaterialDark)
            effect_view.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
            
            # Insert at the bottom
            window.contentView().addSubview_positioned_relativeTo_(effect_view, -1, None)
            
            # Make the window transparent to see the blur
            widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            widget.setStyleSheet("background: transparent;")
        except Exception as e:
            print(f"Failed to apply vibrancy: {e}")

class NotificationPopup(QWidget):
    def __init__(self, data):
        super().__init__()
        print(f"DEBUG: Creating NotificationPopup for {data['process']}")
        self.data = data
        self.init_ui()
        
    def init_ui(self):
        # High visibility flags for macOS - prevent focus stealing
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
        self.proc_label.setFont(QFont("SF Mono", 14, QFont.Weight.Bold))
        self.proc_label.setStyleSheet(f"color: {NEON_CYAN}; background: transparent;")
        layout.addWidget(self.proc_label)
        
        # Company (Neon Magenta)
        self.comp_label = QLabel(f"COMPANY: {self.data.get('company', 'Unknown')}")
        self.comp_label.setFont(QFont("SF Mono", 10))
        self.comp_label.setStyleSheet(f"color: {NEON_MAGENTA}; background: transparent;")
        layout.addWidget(self.comp_label)
        
        # Location (Neon Green)
        self.loc_label = QLabel(f"LOCATION: {self.data['location']}")
        self.loc_label.setFont(QFont("SF Mono", 11, QFont.Weight.Bold))
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
        
        # Positioning
        screen = QApplication.primaryScreen().availableGeometry()
        width, height = 360, 150
        self.setFixedSize(width, height)
        x = screen.width() - width - 20
        y = 50
        self.move(x, y)
        
        # Simple timer to close
        self.close_timer = QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(self.close)
        self.close_timer.start(DISPLAY_TIME)

    def showEvent(self, event):
        super().showEvent(event)
        # Vibrancy removed temporarily to fix 'black box' issue
        print("DEBUG: Popup shown")

# --- Monitor Thread ---

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
        
        # Set macOS Activation Policy to Accessory (no dock icon, but shows in menu bar)
        if NSVisualEffectView:
            try:
                ns_app = NSApplication.sharedApplication()
                ns_app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
            except Exception as e:
                print(f"Failed to set activation policy: {e}")
                
        print("X-Con App initializing...")
        self.setQuitOnLastWindowClosed(False)
        
        self.history = []
        self.active_popups = [] # KEY: Prevent garbage collection
        
        # Tray Icon availability check
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("Error: System tray is not available on this system.")
        
        # Tray Icon
        self.tray = QSystemTrayIcon(self)
        icon = self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxInformation)
        self.tray.setIcon(icon)
        self.tray.setToolTip("X-Con Network Monitor")
        
        self.menu = QMenu()
        self.update_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        
        if self.tray.isVisible():
            print("Tray icon is visible.")
        else:
            print("Warning: Tray icon is NOT visible.")
        
        # Start Monitor
        print("Starting connection monitor...")
        self.monitor = ConnectionMonitor()
        self.monitor.new_connection.connect(self.handle_new_connection)
        self.monitor.start()
        print("Initialization complete.")
        
        # Test notification after 2 seconds
        QTimer.singleShot(2000, lambda: self.handle_new_connection({
            'process': 'System Test',
            'company': 'X-Con Monitor',
            'ip': '1.1.1.1',
            'location': 'Digital Space',
            'org': 'Cloudflare',
            'time': datetime.now().strftime("%H:%M:%S")
        }))

    def handle_new_connection(self, data):
        print(f"New connection detected: {data['process']} ({data['ip']})")
        # Add to history
        self.history.insert(0, data)
        if len(self.history) > MAX_HISTORY:
            self.history.pop()
        
        self.update_menu()
        
        # Show notification
        popup = NotificationPopup(data)
        self.active_popups.append(popup)
        popup.show()
        
        # Cleanup closed popups
        self.active_popups = [p for p in self.active_popups if p.isVisible() or not p.isWidgetType()] 
        
    def update_menu(self):
        self.menu.clear()
        
        header = self.menu.addAction("X-CON MONITORING")
        header.setEnabled(False)
        self.menu.addSeparator()
        
        if not self.history:
            self.menu.addAction("No connections yet...").setEnabled(False)
        else:
            for item in self.history:
                # Include Company in the menu text
                company = item.get('company', 'Unknown')
                text = f"[{item['time']}] {item['process']} ({company}) -> {item['location']}"
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
