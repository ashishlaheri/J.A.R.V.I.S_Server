"""
╔══════════════════════════════════════════════════════════════╗
║        J.A.R.V.I.S. Local Agent v2.0 — PC Control Client     ║
║  Connects to cloud Jarvis and executes local PC commands.    ║
╚══════════════════════════════════════════════════════════════╝

Run:  python local_agent.py
Set JARVIS_SERVER and JARVIS_TOKEN in agent/.env or as env vars.

This agent connects to the cloud J.A.R.V.I.S. server via WebSocket
and executes commands on your local PC when triggered from the web UI.
"""

import os
import sys
import json
import asyncio
import subprocess
import webbrowser
import platform
import shutil
import time
from datetime import datetime
from dotenv import load_dotenv

# Load agent-specific .env
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

SERVER = os.getenv("JARVIS_SERVER", "ws://localhost:8000/ws")
TOKEN  = os.getenv("JARVIS_TOKEN", "")

# ── App registry: common Windows apps and their launch commands ──
APP_REGISTRY = {
    "notepad":      "notepad.exe",
    "calculator":   "calc.exe",
    "calc":         "calc.exe",
    "cmd":          "cmd.exe",
    "terminal":     "cmd.exe",
    "powershell":   "powershell.exe",
    "explorer":     "explorer.exe",
    "file explorer": "explorer.exe",
    "paint":        "mspaint.exe",
    "snipping tool": "snippingtool.exe",
    "task manager":  "taskmgr.exe",
    "settings":     "ms-settings:",
    "control panel": "control.exe",
    "vscode":       "code",
    "vs code":      "code",
    "visual studio code": "code",
    "chrome":       "chrome",
    "google chrome": "chrome",
    "firefox":      "firefox",
    "edge":         "msedge",
    "microsoft edge": "msedge",
    "spotify":      "spotify",
    "discord":      "discord",
    "slack":        "slack",
    "teams":        "teams",
    "zoom":         "zoom",
    "word":         "winword",
    "excel":        "excel",
    "powerpoint":   "powerpnt",
    "outlook":      "outlook",
    "obs":          "obs64",
    "obs studio":   "obs64",
    "steam":        "steam",
    "vlc":          "vlc",
    "media player": "wmplayer",
}


def open_app(target: str) -> str:
    """Try to open an application."""
    target_lower = target.lower().strip()
    cmd = APP_REGISTRY.get(target_lower, target_lower)

    # Handle ms-settings: URIs
    if cmd.startswith("ms-"):
        try:
            os.startfile(cmd)
            return f"Opened {target}, Sir."
        except Exception as e:
            return f"Could not open {target}: {e}"

    # Try to find the executable
    exe_path = shutil.which(cmd)
    try:
        if exe_path:
            subprocess.Popen([exe_path], shell=False)
        else:
            subprocess.Popen(cmd, shell=True)
        return f"Opened {target}, Sir."
    except Exception as e:
        return f"Could not open {target}: {e}"


def close_app(target: str) -> str:
    """Try to close an application."""
    target_lower = target.lower().strip()
    cmd = APP_REGISTRY.get(target_lower, target_lower)
    # Extract just the executable name
    exe_name = os.path.basename(cmd)
    if not exe_name.endswith('.exe'):
        exe_name += '.exe'
    try:
        subprocess.run(['taskkill', '/IM', exe_name, '/F'],
                      capture_output=True, check=True)
        return f"Closed {target}, Sir."
    except Exception:
        return f"Could not close {target}. It may not be running."


def set_volume(level: str) -> str:
    """Set system volume using PowerShell."""
    try:
        vol = max(0, min(100, int(level)))
        # Use PowerShell to set volume
        ps_cmd = (
            f'(New-Object -ComObject WScript.Shell).SendKeys('
            f'[char]173); '  # Mute first to reset
            f'1..50 | ForEach-Object {{ '
            f'(New-Object -ComObject WScript.Shell).SendKeys([char]175) }}'
        )
        # Simpler: use nircmd if available, otherwise report
        nircmd = shutil.which("nircmd") or shutil.which("nircmd.exe")
        if nircmd:
            subprocess.run([nircmd, "setsysvolume", str(int(vol * 655.35))],
                         check=True)
            return f"Volume set to {vol}%, Sir."
        else:
            return f"Volume control requires nircmd.exe. Please install it for volume control."
    except Exception as e:
        return f"Volume control failed: {e}"


def lock_pc() -> str:
    """Lock the workstation."""
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "PC locked, Sir."
    except Exception as e:
        return f"Could not lock PC: {e}"


def screenshot() -> str:
    """Take a screenshot and save it to Desktop."""
    try:
        import mss
        with mss.mss() as sct:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(os.path.expanduser("~"), "Desktop",
                               f"jarvis_screenshot_{timestamp}.png")
            sct.shot(output=path)
            return f"Screenshot saved to Desktop, Sir."
    except ImportError:
        return "Screenshot requires 'mss' package. Run: pip install mss"
    except Exception as e:
        return f"Screenshot failed: {e}"


def get_system_info() -> str:
    """Get basic system information."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        battery = psutil.sensors_battery()
        info = (
            f"CPU: {cpu}%, "
            f"RAM: {mem.percent}% ({mem.used // (1024**3)}/{mem.total // (1024**3)} GB), "
            f"Disk: {disk.percent}% used"
        )
        if battery:
            info += f", Battery: {battery.percent}%"
            if battery.power_plugged:
                info += " (charging)"
        return info
    except ImportError:
        return f"System: {platform.system()} {platform.release()}, {platform.processor()}"
    except Exception as e:
        return f"System info unavailable: {e}"


def execute_command(command: str, target: str = "") -> str:
    """Route a local command to the appropriate handler."""
    command = command.lower().strip()

    if command in ("open_app", "open", "launch"):
        return open_app(target)
    elif command in ("close_app", "close", "kill"):
        return close_app(target)
    elif command in ("lock", "lock_pc", "lock screen"):
        return lock_pc()
    elif command in ("volume", "set_volume"):
        return set_volume(target)
    elif command in ("screenshot", "screen capture", "screen shot"):
        return screenshot()
    elif command in ("open_url", "browse", "open url"):
        webbrowser.open(target)
        return f"Opened {target} in browser, Sir."
    elif command in ("system_info", "system info", "status"):
        return get_system_info()
    elif command in ("shutdown", "shut down"):
        return "Shutdown command received but blocked for safety, Sir."
    elif command in ("restart", "reboot"):
        return "Restart command received but blocked for safety, Sir."
    else:
        return f"Unknown local command: {command}"


async def main():
    """Main agent loop — connects to cloud Jarvis and processes commands."""
    try:
        import websockets
    except ImportError:
        print("[ERROR] websockets package not found. Run: pip install websockets")
        sys.exit(1)

    if not TOKEN:
        print("[ERROR] JARVIS_TOKEN not set!")
        print("  1. Login to your Jarvis web UI")
        print("  2. Get your JWT token")
        print("  3. Set it in agent/.env as JARVIS_TOKEN=your_token")
        sys.exit(1)

    print("=" * 60)
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║     J.A.R.V.I.S. Local Agent v2.0           ║")
    print("  ║     PC Control Bridge                        ║")
    print("  ╚══════════════════════════════════════════════╝")
    print(f"  Server: {SERVER}")
    print(f"  System: {platform.system()} {platform.release()}")
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    retry_delay = 2  # Start with 2 seconds, exponential backoff

    while True:
        try:
            print(f"\n[AGENT] Connecting to {SERVER}...")
            async with websockets.connect(SERVER, ping_interval=30, ping_timeout=10) as ws:
                # ── Authenticate ──
                await ws.send(json.dumps({"token": TOKEN}))

                # Wait for greeting or error
                first_msg = await asyncio.wait_for(ws.recv(), timeout=10)
                first_data = json.loads(first_msg)

                if first_data.get("type") == "error":
                    print(f"[AGENT] Auth failed: {first_data.get('message')}")
                    print("[AGENT] Check your JARVIS_TOKEN in agent/.env")
                    sys.exit(1)

                print("[AGENT] ✅ Connected and authenticated!")
                print("[AGENT] Waiting for commands from cloud...\n")
                retry_delay = 2  # Reset on successful connection

                # ── Listen for commands ──
                async for message in ws:
                    try:
                        data = json.loads(message)
                        msg_type = data.get("type", "")

                        if msg_type == "response" and "action" in data:
                            action = data["action"]
                            action_type = action.get("type", "")

                            if action_type == "local_command":
                                command = action.get("command", "")
                                target = action.get("target", "")
                                print(f"[COMMAND] {command} → {target}")

                                result = execute_command(command, target)
                                print(f"[RESULT]  {result}")

                                # Report result back to server
                                await ws.send(json.dumps({
                                    "type": "chat",
                                    "text": f"[Local Agent] {result}"
                                }))

                            elif action_type == "open_url":
                                url = action.get("url", "")
                                if url:
                                    webbrowser.open(url)
                                    print(f"[COMMAND] Opened URL: {url}")

                        elif msg_type == "notification":
                            title = data.get("title", "")
                            body = data.get("body", "")
                            print(f"[NOTIFY] {title}: {body}")

                    except json.JSONDecodeError:
                        print(f"[AGENT] Invalid message received")
                    except Exception as e:
                        print(f"[AGENT] Error processing message: {e}")

        except asyncio.TimeoutError:
            print("[AGENT] Connection timed out.")
        except ConnectionRefusedError:
            print(f"[AGENT] Connection refused. Is the server running?")
        except Exception as e:
            error_msg = str(e)
            if "1000" in error_msg or "1001" in error_msg:
                print("[AGENT] Server closed connection normally.")
            else:
                print(f"[AGENT] Disconnected: {error_msg}")

        # Exponential backoff reconnection
        print(f"[AGENT] Reconnecting in {retry_delay}s...")
        await asyncio.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 60)  # Max 60 seconds


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[AGENT] Shutting down. Goodbye, Sir.")
