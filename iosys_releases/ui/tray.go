package ui

import (
	"fmt"
	"os"
	"time"

	"github.com/getlantern/systray"
	"github.com/nelhorr/iosys/report"
	"github.com/nelhorr/iosys/scanner"
)

var (
	mStatus      *systray.MenuItem
	mLastReport  *systray.MenuItem
	latestReport string
)

func SetupTray() {
	systray.SetTitle("IOSYS")
	systray.SetTooltip("IOSYS by nelhorr")

	// Read icon
	iconData, err := os.ReadFile("icon/icon.png")
	if err == nil {
		systray.SetIcon(iconData)
	}

	systray.AddMenuItem("IOSYS by nelhorr", "Tool Title").Disable()
	systray.AddSeparator()

	mStatus = systray.AddMenuItem("Status: Protected", "Current Status")
	mStatus.Disable()

	mRunScan := systray.AddMenuItem("Run Quick Scan", "Start a manual scan")
	mLastReport = systray.AddMenuItem("View Latest Report", "Open the last generated report")
	mLastReport.Disable()

	systray.AddSeparator()
	mQuit := systray.AddMenuItem("Quit", "Quit the application")

	go func() {
		for {
			select {
			case <-mRunScan.ClickedCh:
				runManualScan()
			case <-mLastReport.ClickedCh:
				if latestReport != "" {
					report.OpenReport(latestReport)
				}
			case <-mQuit.ClickedCh:
				systray.Quit()
			}
		}
	}()

	// Start auto-scan loop
	go autoScanLoop()
}

func runManualScan() {
	mStatus.SetTitle("Status: Scanning...")
	issues := performScan()
	path, err := report.GenerateReport(issues)
	if err == nil {
		latestReport = path
		mLastReport.Enable()
		report.OpenReport(path)
	}
	mStatus.SetTitle("Status: Protected")
}

func autoScanLoop() {
	ticker := time.NewTicker(30 * time.Minute)
	for range ticker.C {
		issues := performScan()
		if len(issues) > 0 {
			path, _ := report.GenerateReport(issues)
			latestReport = path
			mLastReport.Enable()
			// Optional: Trigger a macOS notification here
			fmt.Println("Suspicious activity detected! Check report.")
		}
	}
}

func performScan() []scanner.Issue {
	var allIssues []scanner.Issue
	pIssues, _ := scanner.ScanProcesses()
	allIssues = append(allIssues, pIssues...)

	persIssues, _ := scanner.ScanPersistence()
	allIssues = append(allIssues, persIssues...)

	return allIssues
}
