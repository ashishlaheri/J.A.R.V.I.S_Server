' J.A.R.V.I.S. Silent Launcher
' Double-click this to start the agent silently (no window at all)
' The agent will appear as a small icon in your taskbar tray.

Option Explicit

Dim fso, scriptDir, pythonCmd, agentScript, shell

Set fso    = CreateObject("Scripting.FileSystemObject")
Set shell  = CreateObject("WScript.Shell")

' Get the folder where this .vbs file lives
scriptDir   = fso.GetParentFolderName(WScript.ScriptFullName)
agentScript = scriptDir & "\tray_agent.py"

' Use pythonw.exe — runs Python with NO console window
' Try to find pythonw in common locations
Dim pythonw
pythonw = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe"

If Not fso.FileExists(pythonw) Then
    pythonw = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python311\pythonw.exe"
End If
If Not fso.FileExists(pythonw) Then
    pythonw = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python310\pythonw.exe"
End If
If Not fso.FileExists(pythonw) Then
    ' Try PATH
    pythonw = "pythonw"
End If

' Run silently: window style 0 = hidden, False = don't wait
Dim cmd
cmd = """" & pythonw & """ """ & agentScript & """"

shell.Run cmd, 0, False

' Done — nothing visible happens, agent is now running in tray
