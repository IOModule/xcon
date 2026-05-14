#!/bin/bash

# IOSYS by nelhorr - Linux Build Script
# Run this on your Linux Mint (LMDE) machine to compile the tool.

echo "Setting up dependencies for LMDE..."
sudo apt-get update
sudo apt-get install -y golang libayatana-appindicator3-dev libgtk-3-dev libglib2.0-dev

echo "Building IOSYS for Linux..."
go mod tidy
go build -o iosys_linux_lmde main.go

echo "Done! You can now run ./iosys_linux_lmde"
