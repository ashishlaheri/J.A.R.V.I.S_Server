# ============================================================
#  J.A.R.V.I.S. — Create Desktop Shortcut
#  Run this once to put the JARVIS icon on your Desktop.
#  After that, just double-click the Desktop icon to start.
# ============================================================

Write-Host ""
Write-Host "  J.A.R.V.I.S. Desktop Shortcut Creator" -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host ""

# Paths
$agentDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$vbsLauncher = Join-Path $agentDir "start_jarvis.vbs"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "JARVIS Agent.lnk"

# Check VBScript exists
if (-not (Test-Path $vbsLauncher)) {
    Write-Host "  ERROR: start_jarvis.vbs not found at:" -ForegroundColor Red
    Write-Host "  $vbsLauncher" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Install required packages if not present
Write-Host "  Checking Python packages..." -ForegroundColor Yellow
$packages = @("pystray", "pillow", "websockets", "python-dotenv")
foreach ($pkg in $packages) {
    $check = & python -c "import $($pkg.Replace('-','_').Replace('pillow','PIL'))" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Installing $pkg..." -ForegroundColor Yellow
        & pip install $pkg --quiet
    }
}
Write-Host "  Packages ready!" -ForegroundColor Green
Write-Host ""

# Create the .lnk shortcut using WScript.Shell COM
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)

# Target = wscript.exe running the VBScript silently
$shortcut.TargetPath       = "wscript.exe"
$shortcut.Arguments        = """$vbsLauncher"""
$shortcut.WorkingDirectory = $agentDir
$shortcut.Description      = "J.A.R.V.I.S. Local Agent - Silent Mode"

# Use a shell icon (shield icon looks cool)
$shortcut.IconLocation = "%SystemRoot%\System32\imageres.dll, 77"

$shortcut.Save()

Write-Host "  Desktop shortcut created!" -ForegroundColor Green
Write-Host "  Location: $shortcutPath" -ForegroundColor White
Write-Host ""
Write-Host "  HOW TO USE:" -ForegroundColor Cyan
Write-Host "  1. Double-click 'JARVIS Agent' on your Desktop" -ForegroundColor White
Write-Host "  2. Nothing visible happens — agent starts silently" -ForegroundColor White
Write-Host "  3. Look for the small icon in your taskbar tray (bottom-right)" -ForegroundColor White
Write-Host "     - CYAN  icon = Connected to server" -ForegroundColor Cyan
Write-Host "     - RED   icon = Disconnected (reconnecting)" -ForegroundColor Red
Write-Host "  4. RIGHT-CLICK the tray icon to:" -ForegroundColor White
Write-Host "     - See connection status" -ForegroundColor White
Write-Host "     - Open log file" -ForegroundColor White
Write-Host "     - STOP the agent" -ForegroundColor White
Write-Host ""

# Optionally launch right now
$launch = Read-Host "  Start JARVIS Agent now? (y/n)"
if ($launch -eq "y" -or $launch -eq "Y") {
    Write-Host ""
    Write-Host "  Starting JARVIS Agent silently..." -ForegroundColor Green
    Start-Process "wscript.exe" -ArgumentList """$vbsLauncher""" -WindowStyle Hidden
    Write-Host "  Done! Check your taskbar tray." -ForegroundColor Green
}

Write-Host ""
Write-Host "  Setup complete!" -ForegroundColor Cyan
Write-Host ""
Start-Sleep -Seconds 2
