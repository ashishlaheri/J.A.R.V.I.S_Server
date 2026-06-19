"""
J.A.R.V.I.S. Silent Tray Agent
================================
Runs the local agent invisibly in the background.
Shows a system tray icon — right-click to stop.

Install once:
    pip install pystray pillow websockets python-dotenv
"""

import sys
import os
import asyncio
import threading
import json
import time
from datetime import datetime
from pathlib import Path

# ── Force UTF-8 output ──────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── Load .env ───────────────────────────────────────────
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                os.environ.setdefault(key.strip(), val.strip())

SERVER = os.getenv("JARVIS_SERVER", "ws://localhost:8000/ws")
TOKEN  = os.getenv("JARVIS_TOKEN", "")

# ── Global state ────────────────────────────────────────
_status   = "Starting..."
_log_path = Path(__file__).parent / "jarvis_agent.log"
_stop_event = threading.Event()
_tray_icon  = None


def _log(msg: str):
    """Write to log file (since we have no console)."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(_log_path, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except Exception:
        pass


def _set_status(msg: str):
    global _status
    _status = msg
    _log(msg)
    if _tray_icon:
        try:
            _tray_icon.title = f"JARVIS Agent — {msg}"
        except Exception:
            pass


# ── Draw the tray icon ──────────────────────────────────
def _make_icon(connected: bool = False):
    """Draw a tiny arc reactor icon."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        # Fallback: minimal 16x16 solid color icon
        try:
            from PIL import Image
            img = Image.new('RGB', (64, 64), (0, 212, 255) if connected else (255, 71, 87))
            return img
        except Exception:
            return None

    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    cx, cy, r = size//2, size//2, size//2 - 4
    color = (0, 212, 255, 255) if connected else (255, 71, 87, 220)
    dim   = (0, 100, 130, 180)   if connected else (120, 30, 40, 150)

    # Outer ring
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=color, width=3)
    # Middle ring
    r2 = r - 8
    d.ellipse([cx-r2, cy-r2, cx+r2, cy+r2], outline=dim, width=2)
    # Core dot
    r3 = r - 18
    d.ellipse([cx-r3, cy-r3, cx+r3, cy+r3], fill=color)

    return img


# ── The actual agent logic (copy from local_agent.py) ──
# We import the agent functions from the sibling file
sys.path.insert(0, str(Path(__file__).parent))

try:
    from local_agent import (
        execute_command, take_screenshot_and_upload, connect_and_run as _agent_connect_and_run
    )
    _agent_available = True
except ImportError as e:
    _agent_available = False
    _log(f"Could not import local_agent: {e}")


async def _agent_loop():
    """Run the agent with reconnection logic."""
    _set_status("Connecting...")

    if not TOKEN:
        _set_status("ERROR: No token set")
        _log("JARVIS_TOKEN not set in agent/.env!")
        _show_notification("JARVIS Agent Error", "No token set. Check agent/.env")
        return

    retry_delay = 2

    while not _stop_event.is_set():
        try:
            import websockets

            extra_headers = {
                "User-Agent": "JARVIS-TrayAgent/3.0",
                "Origin": SERVER.replace("wss://", "https://").replace("ws://", "http://").split("/ws")[0],
            }

            _log(f"Connecting to {SERVER}...")
            async with websockets.connect(
                SERVER,
                ping_interval=20,
                ping_timeout=10,
                extra_headers=extra_headers,
                open_timeout=15
            ) as ws:
                # Authenticate
                await ws.send(json.dumps({"token": TOKEN}))
                first_raw = await asyncio.wait_for(ws.recv(), timeout=15)
                first_msg = json.loads(first_raw)

                if first_msg.get("type") == "error":
                    _set_status("Auth Failed")
                    _show_notification("JARVIS Auth Failed", first_msg.get("message", "Check your token"))
                    _stop_event.set()
                    return

                _set_status("Connected")
                _refresh_icon(connected=True)
                _show_notification("JARVIS Agent", "Connected! Ready for commands.")
                retry_delay = 2

                # Listen loop
                async for raw_msg in ws:
                    if _stop_event.is_set():
                        break
                    try:
                        data = json.loads(raw_msg)
                        msg_type = data.get("type", "")

                        if msg_type == "response" and "action" in data:
                            action = data["action"]
                            if action.get("type") == "local_command":
                                command = action.get("command", "")
                                target  = action.get("target", "")
                                _log(f"CMD: {command} -> '{target}'")

                                if command in ("screenshot_upload", "see_screen", "live_screenshot"):
                                    result = await take_screenshot_and_upload(ws)
                                else:
                                    result = execute_command(command, target)
                                _log(f"RES: {result}")

                                await ws.send(json.dumps({
                                    "type": "chat", "text": result
                                }))

                            elif action.get("type") == "open_url":
                                import webbrowser
                                url = action.get("url", "")
                                if url:
                                    if not url.startswith("http"):
                                        url = "https://" + url
                                    webbrowser.open(url)

                        elif msg_type == "notification":
                            title = data.get("title", "JARVIS")
                            body  = data.get("body", "")
                            _show_notification(title, body)

                    except Exception as e:
                        _log(f"Message error: {e}")

        except Exception as e:
            err = str(e)
            if "403" in err:
                _set_status("403 — Check URL/token")
            elif _stop_event.is_set():
                break
            else:
                _set_status(f"Disconnected ({err[:40]})")
                _refresh_icon(connected=False)

        if _stop_event.is_set():
            break

        _log(f"Reconnecting in {retry_delay}s...")
        _set_status(f"Reconnecting in {retry_delay}s...")
        await asyncio.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 30)

    _set_status("Stopped")
    _refresh_icon(connected=False)


def _refresh_icon(connected: bool):
    global _tray_icon
    if _tray_icon:
        try:
            _tray_icon.icon = _make_icon(connected)
        except Exception:
            pass


def _show_notification(title: str, body: str):
    """Show Windows balloon notification from tray icon."""
    if _tray_icon:
        try:
            _tray_icon.notify(body, title)
            return
        except Exception:
            pass
    # Fallback: PowerShell notification
    try:
        import subprocess
        ps = (
            f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms") | Out-Null;'
            f'$n=New-Object System.Windows.Forms.NotifyIcon;'
            f'$n.Icon=[System.Drawing.SystemIcons]::Information;'
            f'$n.Visible=$true;'
            f'$n.ShowBalloonTip(4000,"{title}","{body}",[System.Windows.Forms.ToolTipIcon]::Info)'
        )
        subprocess.Popen(
            ['powershell', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', ps],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def _open_log():
    """Open the log file in Notepad."""
    try:
        import subprocess
        subprocess.Popen(['notepad', str(_log_path)])
    except Exception:
        pass


def _stop_agent(icon, item):
    """Stop the agent and exit."""
    _stop_event.set()
    _set_status("Stopping...")
    icon.stop()


def _run_agent_thread():
    """Run the async agent loop in a background thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_agent_loop())
    except Exception as e:
        _log(f"Agent loop error: {e}")
    finally:
        loop.close()


def main():
    global _tray_icon

    # Write startup marker to log
    _log("=" * 40)
    _log("JARVIS Tray Agent starting")
    _log(f"Server: {SERVER}")
    _log("=" * 40)

    # Check pystray
    try:
        import pystray
    except ImportError:
        # No pystray — fall back to running agent directly (with a console)
        _log("pystray not installed — running without tray. Install: pip install pystray")
        import asyncio
        asyncio.run(_agent_loop())
        return

    # Start the agent in a background daemon thread
    agent_thread = threading.Thread(target=_run_agent_thread, daemon=True)
    agent_thread.start()

    # Build tray menu
    menu = pystray.Menu(
        pystray.MenuItem(lambda text: f"Status: {_status}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open Log File", lambda icon, item: _open_log()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Stop JARVIS Agent", _stop_agent, default=True),
    )

    icon_img = _make_icon(connected=False)

    _tray_icon = pystray.Icon(
        name="jarvis_agent",
        icon=icon_img,
        title="JARVIS Agent — Starting...",
        menu=menu,
    )

    # Run tray (blocks main thread — this is required by pystray)
    _tray_icon.run()

    # When tray exits, make sure everything stops
    _stop_event.set()
    _log("JARVIS Tray Agent stopped.")


if __name__ == "__main__":
    main()
