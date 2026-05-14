package scanner

import (
	"fmt"
	"os/exec"
	"strings"
	"time"

	"github.com/shirou/gopsutil/v3/process"
)

type Issue struct {
	Type        string
	Description string
	Severity    string
	Timestamp   time.Time
}

func ScanProcesses() ([]Issue, error) {
	var issues []Issue
	procs, err := process.Processes()
	if err != nil {
		return nil, err
	}

	suspiciousPaths := []string{"/tmp", "/var/folders", "/private/tmp"}

	for _, p := range procs {
		exe, err := p.Exe()
		if err != nil {
			continue
		}

		// 1. Check for suspicious paths
		for _, path := range suspiciousPaths {
			if strings.HasPrefix(exe, path) {
				issues = append(issues, Issue{
					Type:        "Suspicious Path",
					Description: fmt.Sprintf("Process %d (%s) running from %s", p.Pid, exe, path),
					Severity:    "High",
					Timestamp:   time.Now(),
				})
			}
		}

		// 2. Heuristic: Unusually long names or random-looking names
		name, _ := p.Name()
		if len(name) > 50 {
			issues = append(issues, Issue{
				Type:        "Anomalous Name",
				Description: fmt.Sprintf("Process %d has unusually long name: %s", p.Pid, name),
				Severity:    "Medium",
				Timestamp:   time.Now(),
			})
		}

		// 3. Codesign check (macOS specific)
		if !isSigned(exe) {
			// Skip self-exclusion to avoid false positives from the tool itself
			if strings.Contains(exe, "iosys_bin") {
				continue
			}
			// Note: Many legit apps are unsigned, so we filter by path or other factors
			if strings.Contains(exe, "Library") || strings.Contains(exe, "Users") {
				issues = append(issues, Issue{
					Type:        "Unsigned Binary",
					Description: fmt.Sprintf("Unsigned binary running from user/library path: %s", exe),
					Severity:    "Low",
					Timestamp:   time.Now(),
				})
			}
		}
	}

	return issues, nil
}

func isSigned(path string) bool {
	// macOS check
	if strings.Contains(path, "/") && !strings.HasPrefix(path, "/home") && !strings.HasPrefix(path, "/usr") {
		cmd := exec.Command("codesign", "-v", path)
		return cmd.Run() == nil
	}
	// Windows check
	if strings.Contains(path, "\\") || strings.HasSuffix(path, ".exe") {
		cmd := exec.Command("powershell", "-Command", "Get-AuthenticodeSignature '"+path+"' | Select-Object -ExpandProperty Status")
		out, err := cmd.Output()
		if err == nil && strings.Contains(string(out), "Valid") {
			return true
		}
	}
	// Linux check (placeholder - Linux typically uses package managers/GPG)
	// For now, we consider binaries in /usr/bin or /bin as "trusted"
	if strings.HasPrefix(path, "/usr/bin") || strings.HasPrefix(path, "/bin") || strings.HasPrefix(path, "/usr/sbin") {
		return true
	}

	return false
}
