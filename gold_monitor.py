#!/usr/bin/env python3
"""
Gold Price Monitor - Modern notification-based gold price tracker
Sends macOS notifications every 3 minutes with current gold prices and trends
"""

import json
import urllib.request
import urllib.error
import ssl
import subprocess
import time
import sys
import os
import signal
import csv
from datetime import datetime, timedelta
from pathlib import Path

# Fix SSL certificate issues on macOS
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context

class GoldPriceMonitor:
    def __init__(self, config_file="~/.gold_monitor_config.json"):
        self.config_file = Path(config_file).expanduser()
        self.pid_file = Path("~/.gold_monitor.pid").expanduser()
        self.last_price_file = Path("~/.gold_monitor_last_price.json").expanduser()
        self.history_file = Path("~/gold_history.csv").expanduser()
        self.load_config()
        
        # Create SSL context
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
    def load_config(self):
        """Load configuration or create default"""
        default_config = {
            "interval_minutes": 3,
            "notification_sound": "Glass",  # macOS notification sounds
            "show_change_threshold": 0.5,  # Show notification only if change > 0.5%
            "always_notify": True,  # Set to False to only notify on significant changes
            "show_conversions": True,
            "quiet_hours": {
                "enabled": False,
                "start": "22:00",
                "end": "08:00"
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    config = json.load(f)
                    # Merge with defaults for any missing keys
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    self.config = config
            except:
                self.config = default_config
        else:
            self.config = default_config
            self.save_config()
    
    def save_config(self):
        """Save current configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def fetch_gold_price(self):
        """Fetch current gold price from multiple sources"""
        sources = [
            self.fetch_from_yahoo_finance,
            self.fetch_from_goldapi,
            self.fetch_from_alternative_api
        ]
        
        for source_func in sources:
            try:
                result = source_func()
                if result and 'error' not in result:
                    return result
            except Exception:
                continue
        
        return None
    
    def fetch_from_yahoo_finance(self):
        """Fetch gold price from Yahoo Finance"""
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read())
            
            chart = data['chart']['result'][0]
            meta = chart['meta']
            
            return {
                'price': meta['regularMarketPrice'],
                'prev_close': meta.get('previousClose', 0),
                'currency': 'USD',
                'source': 'Yahoo Finance',
                'timestamp': datetime.now()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def fetch_from_goldapi(self):
        """Fetch from goldapi.io"""
        try:
            url = "https://www.goldapi.io/api/XAU/USD"
            headers = {
                'x-access-token': 'goldapi-demo-key',
                'User-Agent': 'Gold Monitor'
            }
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read())
            
            return {
                'price': data['price'],
                'prev_close': data.get('prev_close_price', 0),
                'currency': 'USD',
                'source': 'GoldAPI',
                'timestamp': datetime.now()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def fetch_from_alternative_api(self):
        """Backup API source"""
        try:
            # This would be another API endpoint
            return {'error': 'Alternative API not configured'}
        except Exception as e:
            return {'error': str(e)}
    
    def load_last_price(self):
        """Load the last known price"""
        if self.last_price_file.exists():
            try:
                with open(self.last_price_file) as f:
                    return json.load(f)
            except:
                return None
        return None
    
    def save_last_price(self, price_data):
        """Save current price data"""
        with open(self.last_price_file, 'w') as f:
            # Convert datetime to string for JSON serialization
            data = price_data.copy()
            data['timestamp'] = data['timestamp'].isoformat()
            json.dump(data, f, indent=2)

    def log_to_csv(self, price_data):
        """Log price data to a CSV file for historical tracking"""
        file_exists = self.history_file.exists()
        
        try:
            with open(self.history_file, mode='a', newline='') as f:
                writer = csv.writer(f)
                
                # Write header if new file
                if not file_exists:
                    writer.writerow(['Timestamp', 'Price (USD)', 'Source', 'Prev Close'])
                
                writer.writerow([
                    price_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    f"{price_data['price']:.2f}",
                    price_data['source'],
                    f"{price_data.get('prev_close', 0):.2f}"
                ])
        except Exception as e:
            print(f"⚠️ Failed to log to CSV: {e}")
    
    def is_quiet_hours(self):
        """Check if we're in quiet hours"""
        if not self.config['quiet_hours']['enabled']:
            return False
        
        now = datetime.now().time()
        start = datetime.strptime(self.config['quiet_hours']['start'], '%H:%M').time()
        end = datetime.strptime(self.config['quiet_hours']['end'], '%H:%M').time()
        
        if start <= end:
            return start <= now <= end
        else:  # Overnight quiet hours
            return now >= start or now <= end
    
    def send_notification(self, title, message, subtitle=""):
        """Send macOS notification"""
        if self.is_quiet_hours():
            return
        
        cmd = [
            'osascript', '-e',
            f'display notification "{message}" with title "{title}" subtitle "{subtitle}" sound name "{self.config["notification_sound"]}"'
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # Fallback to simpler notification
            subprocess.run(['say', f'Gold price update: {title}'], capture_output=True)
    
    def format_price_message(self, current_price, last_price=None):
        """Format price information for notification"""
        price = current_price['price']
        
        if last_price:
            last_val = last_price['price']
            change = price - last_val
            change_pct = (change / last_val) * 100 if last_val > 0 else 0
            
            # Determine trend emoji
            if abs(change_pct) < 0.1:
                trend = "➡️"
            elif change > 0:
                trend = "📈"
            else:
                trend = "📉"
            
            title = f"{trend} Gold: ${price:,.2f}"
            
            if self.config['show_conversions']:
                gram_price = price / 31.1035
                message = f"Change: ${change:+.2f} ({change_pct:+.2f}%)\n1g: ${gram_price:.2f} | 10g: ${gram_price*10:.2f}"
            else:
                message = f"Change: ${change:+.2f} ({change_pct:+.2f}%)"
            
            subtitle = f"Updated {current_price['timestamp'].strftime('%H:%M:%S')}"
            
            return title, message, subtitle, abs(change_pct)
        else:
            # First notification
            title = f"🥇 Gold: ${price:,.2f}"
            
            if self.config['show_conversions']:
                gram_price = price / 31.1035
                message = f"24K Gold per troy ounce\n1g: ${gram_price:.2f} | 10g: ${gram_price*10:.2f}"
            else:
                message = "24K Gold per troy ounce"
            
            subtitle = f"Monitoring started - {current_price['source']}"
            
            return title, message, subtitle, float('inf')  # Always show first notification
    
    def should_notify(self, change_pct):
        """Determine if we should send a notification"""
        if self.config['always_notify']:
            return True
        
        return change_pct >= self.config['show_change_threshold']
    
    def monitor_loop(self):
        """Main monitoring loop"""
        print(f"🚀 Gold Price Monitor started!")
        print(f"📱 Notifications every {self.config['interval_minutes']} minutes")
        print(f"🔕 Quiet hours: {'Enabled' if self.config['quiet_hours']['enabled'] else 'Disabled'}")
        print(f"💾 PID: {os.getpid()}")
        print("Press Ctrl+C to stop\n")
        
        # Save PID
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                print(f"🔍 Fetching gold price... (#{iteration})")
                
                # Fetch current price
                current_price = self.fetch_gold_price()
                
                if current_price:
                    # Load last known price
                    last_price = self.load_last_price()
                    
                    # Format notification
                    title, message, subtitle, change_pct = self.format_price_message(current_price, last_price)
                    
                    # Send notification if criteria met
                    if self.should_notify(change_pct):
                        print(f"📱 Sending notification: {title}")
                        self.send_notification(title, message, subtitle)
                    else:
                        print(f"🔇 Skipping notification (change {change_pct:.2f}% < threshold {self.config['show_change_threshold']}%)")
                    
                    # Save current price
                    self.save_last_price(current_price)
                    
                    # Log to CSV for history
                    self.log_to_csv(current_price)
                    
                    print(f"✅ Price: ${current_price['price']:,.2f} | Source: {current_price['source']}")
                else:
                    print("❌ Failed to fetch price from all sources")
                    self.send_notification("Gold Monitor Error", "Unable to fetch current gold price", "Check internet connection")
                
                # Wait for next iteration
                sleep_time = self.config['interval_minutes'] * 60
                print(f"⏰ Next update in {self.config['interval_minutes']} minutes...\n")
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            print("\n🛑 Gold monitor stopped by user")
        except Exception as e:
            print(f"\n❌ Monitor error: {e}")
        finally:
            # Clean up PID file
            if self.pid_file.exists():
                self.pid_file.unlink()
    
    def start_daemon(self):
        """Start monitor as background daemon"""
        if self.is_running():
            print("❌ Gold monitor is already running!")
            return False
        
        print("🚀 Starting gold monitor in background...")
        
        # Start as background process
        cmd = [sys.executable, __file__, 'monitor']
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Wait a moment and check if it started
        time.sleep(2)
        if self.is_running():
            print("✅ Gold monitor started successfully!")
            print(f"📱 You'll receive notifications every {self.config['interval_minutes']} minutes")
            return True
        else:
            print("❌ Failed to start gold monitor")
            return False
    
    def stop_daemon(self):
        """Stop the background monitor"""
        if not self.is_running():
            print("❌ Gold monitor is not running")
            return False
        
        try:
            with open(self.pid_file) as f:
                pid = int(f.read().strip())
            
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            
            # Force kill if still running
            try:
                os.kill(pid, 0)  # Check if process exists
                os.kill(pid, signal.SIGKILL)
                print("🛑 Gold monitor force stopped")
            except ProcessLookupError:
                print("✅ Gold monitor stopped successfully")
            
            if self.pid_file.exists():
                self.pid_file.unlink()
            
            return True
            
        except Exception as e:
            print(f"❌ Error stopping monitor: {e}")
            return False
    
    def is_running(self):
        """Check if monitor is currently running"""
        if not self.pid_file.exists():
            return False
        
        try:
            with open(self.pid_file) as f:
                pid = int(f.read().strip())
            
            # Check if process is still running
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, ValueError):
            # Process not found or invalid PID
            if self.pid_file.exists():
                self.pid_file.unlink()
            return False
    
    def status(self):
        """Show monitor status"""
        if self.is_running():
            with open(self.pid_file) as f:
                pid = int(f.read().strip())
            print(f"✅ Gold monitor is running (PID: {pid})")
            print(f"📱 Notifications every {self.config['interval_minutes']} minutes")
            
            # Show last price if available
            last_price = self.load_last_price()
            if last_price:
                timestamp = datetime.fromisoformat(last_price['timestamp'])
                print(f"💰 Last price: ${last_price['price']:,.2f} at {timestamp.strftime('%H:%M:%S')}")
        else:
            print("❌ Gold monitor is not running")

def main():
    monitor = GoldPriceMonitor()
    
    if len(sys.argv) < 2:
        print("Gold Price Monitor - Modern notification system")
        print("\nUsage:")
        print("  python3 gold_monitor.py start    # Start background monitoring")
        print("  python3 gold_monitor.py stop     # Stop monitoring")
        print("  python3 gold_monitor.py status   # Check status")
        print("  python3 gold_monitor.py monitor  # Run in foreground (for debugging)")
        print("  python3 gold_monitor.py config   # Show configuration")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'start':
        monitor.start_daemon()
    elif command == 'stop':
        monitor.stop_daemon()
    elif command == 'status':
        monitor.status()
    elif command == 'monitor':
        monitor.monitor_loop()
    elif command == 'config':
        print("Configuration file:", monitor.config_file)
        print(json.dumps(monitor.config, indent=2))
    elif command == 'test':
        # Send test notification
        monitor.send_notification("Test Notification", "Gold monitor is working!", "Test complete")
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()