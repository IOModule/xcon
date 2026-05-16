#!/usr/bin/env python3
"""
Gold Price Checker - 24K Gold Price per Ounce
Real-time gold price fetcher with multiple data sources
"""

import json
import urllib.request
import urllib.error
import ssl
from datetime import datetime
import sys
import time
import ssl

# Fix SSL certificate issues on macOS
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context

class GoldPriceChecker:
    def __init__(self):
        # Create SSL context that doesn't verify certificates (for some APIs)
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
    def fetch_from_yahoo_finance(self):
        """Fetch gold price from Yahoo Finance API"""
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
                'currency': meta.get('currency', 'USD'),
                'exchange': meta.get('exchangeName', 'COMEX'),
                'source': 'Yahoo Finance (GC=F)',
                'timestamp': datetime.now()
            }
        except Exception as e:
            return {'error': f"Yahoo Finance error: {str(e)}"}
    
    def fetch_from_metals_api(self):
        """Fetch from metals-api.com (free tier)"""
        try:
            url = "https://metals-api.com/api/latest?access_key=YOUR_API_KEY&base=USD&symbols=XAU"
            # Note: This would need a real API key, but we'll try the demo
            url = "https://api.metals.live/v1/spot/gold"
            
            headers = {'User-Agent': 'Gold Price Checker'}
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=10, context=self.ssl_context) as response:
                data = json.loads(response.read())
            
            if 'price' in data:
                return {
                    'price': data['price'],
                    'currency': 'USD',
                    'source': 'Metals Live API',
                    'timestamp': datetime.now()
                }
        except Exception as e:
            return {'error': f"Metals API error: {str(e)}"}
    
    def fetch_from_goldapi(self):
        """Fetch from goldapi.io (demo key)"""
        try:
            url = "https://www.goldapi.io/api/XAU/USD"
            headers = {
                'x-access-token': 'goldapi-demo-key',
                'User-Agent': 'Gold Price Checker'
            }
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read())
            
            return {
                'price': data['price'],
                'prev_close': data.get('prev_close_price', 0),
                'currency': 'USD',
                'source': 'GoldAPI.io',
                'timestamp': datetime.now()
            }
        except Exception as e:
            return {'error': f"GoldAPI error: {str(e)}"}
    
    def get_gold_price(self):
        """Try multiple sources and return the first successful one"""
        sources = [
            self.fetch_from_yahoo_finance,
            self.fetch_from_goldapi,
            self.fetch_from_metals_api
        ]
        
        print("🔍 Fetching current gold price...")
        
        for source_func in sources:
            result = source_func()
            if 'error' not in result:
                return result
            else:
                print(f"   ⚠️  {result['error']}")
        
        return None
    
    def display_price(self, price_data):
        """Display formatted price information"""
        if not price_data:
            print("\n❌ Unable to fetch gold price from any source")
            print("\nAlternative ways to check gold prices:")
            print("• https://finance.yahoo.com/quote/GC=F")
            print("• https://www.goldprice.org")
            print("• https://www.kitco.com/gold-price-today-usa/")
            print("• Local precious metals dealers")
            return
        
        price = price_data['price']
        prev_close = price_data.get('prev_close', 0)
        
        # Calculate change
        if prev_close > 0:
            change = price - prev_close
            change_pct = (change / prev_close) * 100
        else:
            change = 0
            change_pct = 0
        
        # Display formatted output
        print("\n" + "="*60)
        print("🥇 24K GOLD PRICE - CURRENT MARKET")
        print("="*60)
        print(f"💰 Current Price: ${price:,.2f} USD per troy ounce")
        
        if prev_close > 0:
            print(f"📈 Previous Close: ${prev_close:,.2f}")
            
            change_symbol = "📈" if change >= 0 else "📉"
            print(f"{change_symbol} Change: ${change:+,.2f} ({change_pct:+.2f}%)")
        
        print(f"🏛️  Source: {price_data['source']}")
        print(f"💱 Currency: {price_data['currency']}")
        print(f"⏰ Updated: {price_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Additional info
        print("\n📋 Additional Information:")
        print("• Price shown is for 1 troy ounce (31.1035 grams)")
        print("• 24K gold is 99.9%+ pure gold")
        print("• Physical gold purchases include dealer premiums")
        print("• Swiss/Suisse gold bars typically have 1-5% premium over spot")
        
        # Quick conversions
        print(f"\n🔄 Quick Conversions (at ${price:,.2f}/oz):")
        print(f"• 1 gram: ${price/31.1035:.2f}")
        print(f"• 10 grams: ${price*10/31.1035:.2f}")
        print(f"• 1/2 ounce: ${price/2:.2f}")
        print(f"• 1/4 ounce: ${price/4:.2f}")

def main():
    """Main function"""
    checker = GoldPriceChecker()
    
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print("Gold Price Checker - Get current 24K gold price")
        print("Usage: python3 gold_price_checker.py")
        print("       goldprice  (if alias is set up)")
        return
    
    try:
        price_data = checker.get_gold_price()
        checker.display_price(price_data)
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()