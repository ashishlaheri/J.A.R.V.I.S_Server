"""
╔══════════════════════════════════════════════════════════════╗
║        J.A.R.V.I.S. Local Agent — PC Control Client          ║
║  Connects to cloud Jarvis and executes local PC commands.    ║
╚══════════════════════════════════════════════════════════════╝

Run:  python local_agent.py
Set JARVIS_SERVER and JARVIS_TOKEN in agent/.env or as env vars.
"""

import os
import sys
import json
import asyncio
import subprocess
import webbrowser
import ctypes
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

SERVER = os.getenv("JARVIS_SERVER", "ws://localhost:8000/ws")
TOKEN  = os.getenv("JARVIS_TOKEN", "")

# ── App registry: common apps and their launch commands ────
APP_REGISTRY = {
    "notepad":    "notepad.exe",
    "calculator": "calc.exe",
    "cmd":        "cmd.exe",
    "terminal":   "cmd.exe",
    "explorer":   "explorer.exe",
    "paint":      "mspaint.exe",
    "vscode":     "code",
    "vs code":    "code",
    "chrome":     "chrome",
    "firefox":    "firefox",
    "edge":       "msedge",
    "spotify":    "spotify",
    "discord":    "discord",
}


def open_app(target: str):
    """Try to open an application."""
    target_lower = target.lower().strip()
    cmd = APP_REGISTRY.get(target_lower, target_lower)
    try:
        subprocess.Popen(cmd, shell=True)
        return f"Opened {target}."
    except Exception as e:
        return f"Could not open {target}: {e}"


def set_volume(level: str):
    """Placeholder — requires pycaw or nircmd for actual control."""
    try:
        # Using nircmd if available, otherwise just report
        subprocess.run(["nircmd.exe", "setsysvolume", str(int(level) * 655)], check=True)
        return f"Volume set to {level}%."
    except Exception:
        return f"Volume control requires nircmd.exe. Please install it."


def lock_pc():
    ctypes.windll.user32.LockWorkStation()
    return "PC locked."


def screenshot():
    """Take a screenshot and save it."""
    try:
        import mss
        with mss.mss() as sct:
            path = os.path.join(os.path.expanduser("~"), "Desktop", "jarvis_screenshot.png")
            sct.shot(output=path)
            return f"Screenshot saved to Desktop."
    except ImportError:
        return "Screenshot requires 'mss' package. Run: pip install mss"


def execute_command(command: str, target: str = "") -> str:
    """Route a local command to the appropriate handler."""
    command = command.lower().strip()

    if command in ("open_app", "open", "launch"):
        return open_app(target)
    elif command in ("lock", "lock_pc", "lock screen"):
        return lock_pc()
    elif command in ("volume", "set_volume"):
        return set_volume(target)
    elif command in ("screenshot", "screen capture"):
        return screenshot()
    elif command in ("open_url", "browse"):
        webbrowser.open(target)
        return f"Opened {target} in browser."
    else:
        return f"Unknown local command: {command}"


async def main():
    import websockets

    print("=" * 55)
    print("  J.A.R.V.I.S. Local Agent")
    print(f"  Connecting to: {SERVER}")
    print("  Press Ctrl+C to stop")
    print("=" * 55)

    while True:
        try:
            async with websockets.connect(SERVER) as ws:
                # Auth
                await ws.send(json.dumps({"token": TOKEN}))
                print("[AGENT] Connected and authenticated.")

                async for message in ws:
                    try:
                        data = json.loads(message)

                        # Only handle local_command actions
                        if data.get("type") == "response" and data.get("action", {}).get("type") == "local_command":
                            action = data["action"]
                            cmd = action.get("command", "")
                            target = action.get("target", "")
                            print(f"[AGENT] Executing: {cmd} → {target}")
                            result = execute_command(cmd, target)
                            print(f"[AGENT] Result: {result}")

                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            print(f"[AGENT] Connection lost: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[AGENT] Stopped.")
