#!/bin/bash
# Gold Price Monitor - Convenient aliases
# Add these to your ~/.zshrc or run: source ~/gold_aliases.sh

# Main commands
alias gold-start='python3 ~/gold_monitor.py start'
alias gold-stop='python3 ~/gold_monitor.py stop'  
alias gold-status='python3 ~/gold_monitor.py status'
alias gold-config='python3 ~/gold_monitor.py config'
alias gold-test='python3 ~/gold_monitor.py test'

# Quick shortcuts
alias goldstart='python3 ~/gold_monitor.py start'
alias goldstop='python3 ~/gold_monitor.py stop'
alias goldstatus='python3 ~/gold_monitor.py status'

# Original price checker (one-time)
alias goldprice='python3 ~/gold_price_checker.py'

echo "🥇 Gold monitoring aliases loaded!"
echo "Commands available:"
echo "  gold-start    - Start background monitoring"  
echo "  gold-stop     - Stop monitoring"
echo "  gold-status   - Check status"
echo "  gold-test     - Test notification"
echo "  goldprice     - One-time price check"