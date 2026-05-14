#!/bin/bash

# Setup for IOSYS by nelhorr
# This script ensures the icon is in the right place and runs the app.

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR/iosys"

if [ ! -f "./iosys_bin" ]; then
    echo "Building IOSYS..."
    go build -o iosys_bin main.go
fi

echo "Launching IOSYS by nelhorr..."
# Run in background so the terminal stays free
./iosys_bin &
disown
echo "IOSYS is now running in the system tray."
