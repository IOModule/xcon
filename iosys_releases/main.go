package main

import (
	"github.com/getlantern/systray"
	"github.com/nelhorr/iosys/ui"
)

func main() {
	systray.Run(onReady, onExit)
}

func onReady() {
	ui.SetupTray()
}

func onExit() {
	// Cleanup if necessary
}
