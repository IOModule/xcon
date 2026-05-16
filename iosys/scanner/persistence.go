package scanner

import (
	"fmt"
	"os"
	"path/filepath"
	"time"
)

func ScanPersistence() ([]Issue, error) {
	var issues []Issue

	// --- macOS Logic ---
	home, _ := os.UserHomeDir()
	macPaths := []string{
		"/Library/LaunchAgents",
		"/Library/LaunchDaemons",
		filepath.Join(home, "Library/LaunchAgents"),
	}

	for _, p := range macPaths {
		files, err := os.ReadDir(p)
		if err != nil {
			continue
		}
		for _, f := range files {
			if info, err := f.Info(); err == nil && time.Since(info.ModTime()) < 24*time.Hour {
				issues = append(issues, Issue{
					Type:        "Recent Persistence (macOS)",
					Description: fmt.Sprintf("New or modified persistence item: %s/%s", p, f.Name()),
					Severity:    "Medium",
					Timestamp:   time.Now(),
				})
			}
		}
	}

	// --- Windows Logic (Heuristic) ---
	// Check Startup folder
	winStartup := filepath.Join(os.Getenv("APPDATA"), `Microsoft\Windows\Start Menu\Programs\Startup`)
	if files, err := os.ReadDir(winStartup); err == nil {
		for _, f := range files {
			if info, err := f.Info(); err == nil && time.Since(info.ModTime()) < 24*time.Hour {
				issues = append(issues, Issue{
					Type:        "Recent Persistence (Windows)",
					Description: fmt.Sprintf("New item in Startup folder: %s", f.Name()),
					Severity:    "Medium",
					Timestamp:   time.Now(),
				})
			}
		}
	}

	// --- Linux Logic (Heuristic for LMDE/Debian) ---
	linuxPaths := []string{
		"/etc/systemd/system",
		"/etc/init.d",
		filepath.Join(home, ".config/autostart"),
	}
	for _, p := range linuxPaths {
		files, err := os.ReadDir(p)
		if err != nil {
			continue
		}
		for _, f := range files {
			if info, err := f.Info(); err == nil && time.Since(info.ModTime()) < 24*time.Hour {
				issues = append(issues, Issue{
					Type:        "Recent Persistence (Linux)",
					Description: fmt.Sprintf("New or modified persistence item: %s/%s", p, f.Name()),
					Severity:    "Medium",
					Timestamp:   time.Now(),
				})
			}
		}
	}

	return issues, nil
}
