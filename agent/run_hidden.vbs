Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd.exe /c python local_agent.py", 0, False
