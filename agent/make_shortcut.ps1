$wsh = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = $wsh.CreateShortcut("$desktop\JARVIS Agent.lnk")
$shortcut.TargetPath = "wscript.exe"
$shortcut.Arguments = '"C:\Users\yoash\Desktop\Jarvis\agent\start_jarvis.vbs"'
$shortcut.WorkingDirectory = "C:\Users\yoash\Desktop\Jarvis\agent"
$shortcut.Description = "JARVIS Local Agent - Silent Mode"
$shortcut.IconLocation = "%SystemRoot%\System32\imageres.dll, 77"
$shortcut.Save()
Write-Host "Shortcut created on Desktop!"
