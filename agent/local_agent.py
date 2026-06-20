"""
J.A.R.V.I.S. Local Agent v3.0 - PC Control Bridge
===================================================
Connects to cloud Jarvis and executes local PC commands.

Setup:
  1. Create agent/.env with:
       JARVIS_SERVER=wss://your-url.trycloudflare.com/ws
       JARVIS_TOKEN=your_jwt_token
  2. Install deps: pip install websockets python-dotenv
  3. Run: python local_agent.py
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
from pathlib import Path

# Force UTF-8 output on Windows to avoid codec crashes
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Load .env from agent directory
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                os.environ.setdefault(key.strip(), val.strip())

SERVER = os.getenv("JARVIS_SERVER", "ws://localhost:8000/ws")
TOKEN  = os.getenv("JARVIS_TOKEN", "")

# ══════════════════════════════════════════════════════
#  APP REGISTRY — covers most common Windows apps
# ══════════════════════════════════════════════════════
APP_REGISTRY = {
    # System tools
    "notepad":           "notepad",
    "calculator":        "calc",
    "calc":              "calc",
    "cmd":               "cmd",
    "command prompt":    "cmd",
    "terminal":          "wt",           # Windows Terminal
    "powershell":        "powershell",
    "explorer":          "explorer",
    "file explorer":     "explorer",
    "task manager":      "taskmgr",
    "taskmgr":           "taskmgr",
    "control panel":     "control",
    "paint":             "mspaint",
    "wordpad":           "write",
    "snipping tool":     "snippingtool",
    "snip":              "snippingtool",
    "magnifier":         "magnify",
    "sticky notes":      "stikynot",
    "clock":             "ms-clock:",
    "settings":          "ms-settings:",
    "store":             "ms-windows-store:",
    "camera":            "ms-camera:",

    # Browsers
    "chrome":            "chrome",
    "google chrome":     "chrome",
    "firefox":           "firefox",
    "edge":              "msedge",
    "microsoft edge":    "msedge",
    "brave":             "brave",
    "opera":             "opera",

    # Dev tools
    "vscode":            "code",
    "vs code":           "code",
    "visual studio code":"code",
    "visual studio":     "devenv",
    "git bash":          "git-bash",
    "github desktop":    "github",
    "android studio":    "studio64",
    "postman":           "postman",
    "docker":            "docker desktop",

    # Communication
    "discord":           "discord",
    "slack":             "slack",
    "teams":             "teams",
    "zoom":              "zoom",
    "skype":             "skype",
    "telegram":          "telegram",
    "whatsapp":          "whatsapp",

    # Productivity
    "word":              "winword",
    "excel":             "excel",
    "powerpoint":        "powerpnt",
    "outlook":           "outlook",
    "onenote":           "onenote",
    "access":            "msaccess",

    # Media & Entertainment
    "spotify":           "spotify",
    "vlc":               "vlc",
    "media player":      "wmplayer",
    "photos":            "ms-photos:",
    "movies":            "mswindowsvideo:",

    # Gaming
    "steam":             "steam",
    "epic games":        "epicgameslauncher",
    "xbox":              "xbox",

    # Other
    "obs":               "obs64",
    "obs studio":        "obs64",
    "7zip":              "7zFM",
    "winrar":            "winrar",
    "adobe reader":      "acrord32",
}


def _run_silent(cmd: list | str, shell: bool = False, timeout: int = 5) -> bool:
    """Run a process silently. Returns True if launched successfully."""
    try:
        subprocess.Popen(
            cmd,
            shell=shell,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        return True
    except Exception:
        return False


def open_app(target: str) -> str:
    """Open an application using multiple fallback strategies."""
    if not target:
        return "Please specify an app to open, Sir."

    target_lower = target.lower().strip()
    display_name = target.title()

    # 1. Check our registry
    cmd = APP_REGISTRY.get(target_lower)

    # 2. Try the raw target if not in registry
    if cmd is None:
        cmd = target_lower

    # 3. ms-xxx: URI scheme (Windows Settings, Store, etc.)
    if cmd.startswith("ms-"):
        try:
            os.startfile(cmd)
            return f"Opened {display_name}, Sir."
        except Exception:
            pass

    # 4. Try Windows 'start' command (handles .exe, ms- URIs, shortcuts, etc.)
    if _run_silent(f'start "" "{cmd}"', shell=True):
        return f"Opened {display_name}, Sir."

    # 5. Try shutil.which (finds executables on PATH)
    exe = shutil.which(cmd) or shutil.which(cmd + ".exe")
    if exe:
        if _run_silent([exe]):
            return f"Opened {display_name}, Sir."

    # 6. Try the target name directly via subprocess
    if _run_silent(cmd, shell=True):
        return f"Opened {display_name}, Sir."

    return (
        f"Could not open '{target}', Sir. "
        f"Make sure the app is installed. "
        f"Supported apps: Chrome, VS Code, Notepad, Calculator, Discord, Spotify, and more."
    )


def close_app(target: str) -> str:
    """Close/kill an application by name."""
    if not target:
        return "Please specify an app to close, Sir."

    target_lower = target.lower().strip()

    # Build list of process names to try
    process_names = []

    cmd = APP_REGISTRY.get(target_lower)
    if cmd and not cmd.startswith("ms-"):
        exe = os.path.basename(cmd)
        process_names.append(exe if exe.endswith('.exe') else exe + '.exe')

    # Also try the raw target name
    raw = target_lower.replace(' ', '')
    process_names.append(raw if raw.endswith('.exe') else raw + '.exe')

    # Common mappings
    common = {
        "chrome": "chrome.exe",
        "firefox": "firefox.exe",
        "edge": "msedge.exe",
        "discord": "discord.exe",
        "spotify": "spotify.exe",
        "notepad": "notepad.exe",
        "vs code": "code.exe",
        "vscode": "code.exe",
        "teams": "teams.exe",
        "zoom": "zoom.exe",
    }
    if target_lower in common:
        process_names.insert(0, common[target_lower])

    for pname in process_names:
        try:
            result = subprocess.run(
                ['taskkill', '/IM', pname, '/F'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return f"Closed {target}, Sir."
        except Exception:
            pass

    return f"Could not close '{target}'. It may not be running, Sir."


def take_screenshot() -> str:
    """Take a SINGLE screenshot and save it to the Desktop."""
    try:
        desktop = Path.home() / "Desktop"
        desktop.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = desktop / f"jarvis_{timestamp}.png"

        # Method 1: PIL/Pillow (most reliable)
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()  # Single screenshot
            img.save(str(save_path))
            return f"Screenshot saved as jarvis_{timestamp}.png on your Desktop, Sir."
        except ImportError:
            pass

        # Method 2: PowerShell (no extra packages needed)
        ps_script = (
            f'Add-Type -AssemblyName System.Windows.Forms; '
            f'$bitmap = New-Object System.Drawing.Bitmap('
            f'[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width,'
            f'[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); '
            f'$graphics = [System.Drawing.Graphics]::FromImage($bitmap); '
            f'$graphics.CopyFromScreen(0, 0, 0, 0, $bitmap.Size); '
            f'$bitmap.Save("{save_path}"); '
            f'$graphics.Dispose(); $bitmap.Dispose()'
        )
        result = subprocess.run(
            ['powershell', '-NonInteractive', '-Command', ps_script],
            capture_output=True, timeout=10
        )
        if result.returncode == 0 and save_path.exists():
            return f"Screenshot saved as jarvis_{timestamp}.png on your Desktop, Sir."

        return "Screenshot failed. Install Pillow: pip install Pillow"

    except Exception as e:
        return f"Screenshot error: {e}"


def set_volume(level: str) -> str:
    """Set system volume (0-100) using PowerShell."""
    try:
        vol = max(0, min(100, int(str(level).strip())))
        # Convert 0-100 to 0.0-1.0 scalar
        scalar = vol / 100.0
        ps_script = (
            f'$obj = New-Object -ComObject WScript.Shell; '
            f'$vol = [Math]::Round({scalar} * 65535); '
            f'(New-Object -ComObject WMPlayer.OCX.7).settings.volume = {vol}'
        )
        # Simpler approach with PowerShell audio API
        ps_simple = f"""
$code = @'
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {{
    int Reserved1(); int Reserved2();
    int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
    int Reserved3();
    int GetMasterVolumeLevelScalar(out float pfLevel);
}}
[Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
class MMDeviceEnumerator {{}}
'@
Add-Type $code
"""
        # Actually, easiest reliable method: use nircmd or SendKeys volume
        # Most reliable without extra tools: use PowerShell with audio
        ps_volume = (
            f"$wshell = New-Object -ComObject wscript.shell; "
            f"1..50 | ForEach-Object {{ $wshell.SendKeys([char]174) }}; "  # Vol down 50 times to go to 0
            f"1..{vol // 2} | ForEach-Object {{ $wshell.SendKeys([char]175) }}"  # Vol up to target
        )
        subprocess.run(
            ['powershell', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', ps_volume],
            capture_output=True, timeout=10
        )
        return f"Volume set to approximately {vol}%, Sir."
    except Exception as e:
        return f"Volume control error: {e}"


def mute_volume() -> str:
    """Toggle mute."""
    try:
        ps = "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"
        subprocess.run(
            ['powershell', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', ps],
            capture_output=True, timeout=5
        )
        return "Toggled mute, Sir."
    except Exception as e:
        return f"Mute error: {e}"


def lock_pc() -> str:
    """Lock the workstation."""
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "PC locked, Sir."
    except Exception as e:
        return f"Could not lock PC: {e}"


def get_system_info() -> str:
    """Return readable system info without requiring psutil."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        battery = psutil.sensors_battery()

        parts = [
            f"CPU: {cpu}%",
            f"RAM: {mem.percent}% used ({mem.used // (1024**3)}/{mem.total // (1024**3)} GB)",
            f"Disk C: {disk.percent}% used",
        ]
        if battery:
            status = "charging" if battery.power_plugged else "on battery"
            parts.append(f"Battery: {battery.percent}% ({status})")
        return ", ".join(parts)
    except ImportError:
        # Fallback without psutil
        try:
            result = subprocess.run(
                ['wmic', 'cpu', 'get', 'loadpercentage'],
                capture_output=True, text=True, timeout=5
            )
            cpu = result.stdout.strip().split('\n')[-1].strip()
            return f"System: {platform.system()} {platform.release()}, CPU Load: {cpu}%"
        except Exception:
            return f"System: {platform.system()} {platform.release()}"


def play_alarm(duration_sec: int = 8) -> str:
    """Play a loud repeating alarm sound through PC speakers."""
    try:
        # Use PowerShell to play system sounds + beeps
        ps_script = f"""
$duration = {duration_sec}
$end = (Get-Date).AddSeconds($duration)
while ((Get-Date) -lt $end) {{
    [System.Console]::Beep(1500, 200)
    [System.Console]::Beep(800, 200)
    [System.Console]::Beep(1500, 200)
    [System.Console]::Beep(800, 200)
    [System.Media.SystemSounds]::Exclamation.Play()
    Start-Sleep -Milliseconds 100
}}
"""
        subprocess.Popen(
            ['powershell', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', ps_script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return f"Alarm sounding for {duration_sec} seconds on your PC, Sir!"
    except Exception as e:
        return f"Alarm error: {e}"


def show_warning_popup(message: str = "") -> str:
    """Show a large scary warning popup on the PC screen."""
    msg = message or (
        "WARNING: This laptop is being monitored remotely by J.A.R.V.I.S. "
        "Your activity has been logged. The owner has been notified."
    )
    # Escape quotes for PowerShell
    msg_safe = msg.replace('"', '`"').replace("'", "`'")
    try:
        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$form = New-Object System.Windows.Forms.Form
$form.Text = "J.A.R.V.I.S. Security Alert"
$form.Size = New-Object System.Drawing.Size(600, 300)
$form.StartPosition = "CenterScreen"
$form.TopMost = $true
$form.BackColor = [System.Drawing.Color]::FromArgb(20, 0, 0)
$form.FormBorderStyle = "FixedDialog"
$label = New-Object System.Windows.Forms.Label
$label.Text = "{msg_safe}"
$label.ForeColor = [System.Drawing.Color]::Red
$label.Font = New-Object System.Drawing.Font("Arial", 14, [System.Drawing.FontStyle]::Bold)
$label.Dock = "Fill"
$label.TextAlign = "MiddleCenter"
$label.Padding = New-Object System.Windows.Forms.Padding(20)
$btn = New-Object System.Windows.Forms.Button
$btn.Text = "I UNDERSTAND"
$btn.Dock = "Bottom"
$btn.Height = 50
$btn.BackColor = [System.Drawing.Color]::DarkRed
$btn.ForeColor = [System.Drawing.Color]::White
$btn.Font = New-Object System.Drawing.Font("Arial", 12, [System.Drawing.FontStyle]::Bold)
$btn.Add_Click({{ $form.Close() }})
$form.Controls.Add($label)
$form.Controls.Add($btn)
$form.ShowDialog()
"""
        subprocess.Popen(
            ['powershell', '-NonInteractive', '-Command', ps_script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return "Warning popup displayed on your PC screen, Sir."
    except Exception as e:
        return f"Warning popup error: {e}"


def freeze_input(seconds: int = 10) -> str:
    """Block keyboard and mouse input for N seconds (Windows only)."""
    try:
        import ctypes
        def _do_freeze():
            ctypes.windll.user32.BlockInput(True)
            time.sleep(seconds)
            ctypes.windll.user32.BlockInput(False)
        import threading
        t = threading.Thread(target=_do_freeze, daemon=True)
        t.start()
        return f"Keyboard and mouse frozen for {seconds} seconds on your PC, Sir."
    except Exception as e:
        return f"Freeze input error: {e}"


def logoff_user() -> str:
    """Force log off the current Windows user session."""
    try:
        subprocess.run(
            ['shutdown', '/l', '/f'],
            capture_output=True, timeout=5
        )
        return "Logging off current user, Sir."
    except Exception as e:
        return f"Logoff error: {e}"


def disable_wifi() -> str:
    """Disable the WiFi adapter."""
    try:
        result = subprocess.run(
            ['netsh', 'interface', 'set', 'interface', 'Wi-Fi', 'disable'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return "Wi-Fi disabled on your PC, Sir."
        if "elevation" in result.stderr or "elevation" in result.stdout:
            return "Wi-Fi disable failed: The local agent must be run as Administrator, Sir."
        return f"Wi-Fi disable failed: {result.stderr.strip() or 'Check adapter name'}"
    except Exception as e:
        return f"WiFi disable error: {e}"


def enable_wifi() -> str:
    """Re-enable the WiFi adapter."""
    try:
        result = subprocess.run(
            ['netsh', 'interface', 'set', 'interface', 'Wi-Fi', 'enable'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return "Wi-Fi re-enabled on your PC, Sir."
        if "elevation" in result.stderr or "elevation" in result.stdout:
            return "Wi-Fi enable failed: The local agent must be run as Administrator, Sir."
        return f"Wi-Fi enable failed: {result.stderr.strip() or 'Check adapter name'}"
    except Exception as e:
        return f"WiFi enable error: {e}"


def get_running_apps() -> str:
    """List all visible running applications (not background services)."""
    try:
        result = subprocess.run(
            ['tasklist', '/FO', 'CSV', '/NH'],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split('\n')
        # Parse CSV: "Name","PID","Session","Num","Mem"
        seen = set()
        apps = []
        skip = {
            'svchost.exe', 'csrss.exe', 'smss.exe', 'wininit.exe', 'winlogon.exe',
            'services.exe', 'lsass.exe', 'fontdrvhost.exe', 'dwm.exe', 'spoolsv.exe',
            'SearchIndexer.exe', 'WmiPrvSE.exe', 'dllhost.exe', 'conhost.exe',
            'RuntimeBroker.exe', 'tasklist.exe', 'sihost.exe', 'ctfmon.exe',
        }
        for line in lines[:50]:
            try:
                parts = line.strip().strip('"').split('","')
                name = parts[0].strip('"')
                mem = parts[4].strip('"').replace(',', '').replace(' K', 'KB') if len(parts) > 4 else ''
                name_lower = name.lower()
                if name_lower not in seen and name not in skip and not name_lower.startswith('system'):
                    seen.add(name_lower)
                    apps.append(f"{name} ({mem})")
            except Exception:
                pass
        if apps:
            return "Running apps: " + ", ".join(apps[:15])
        return "No visible applications found."
    except Exception as e:
        return f"Process list error: {e}"


async def take_screenshot_and_upload(ws) -> str:
    """Take screenshot, encode as base64, send to cloud server."""
    try:
        import io
        screenshot_bytes = None

        # Method 1: PIL
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            # Resize to max 1280px wide to keep base64 size manageable
            w, h = img.size
            if w > 1280:
                ratio = 1280 / w
                img = img.resize((1280, int(h * ratio)))
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=70, optimize=True)
            screenshot_bytes = buf.getvalue()
        except ImportError:
            pass

        # Method 2: PowerShell → temp file → read
        if not screenshot_bytes:
            tmp = Path.home() / "AppData" / "Local" / "Temp" / "jarvis_tmp_ss.jpg"
            ps_script = (
                f'Add-Type -AssemblyName System.Windows.Forms, System.Drawing;'
                f'$s=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;'
                f'$b=New-Object System.Drawing.Bitmap($s.Width,$s.Height);'
                f'$g=[System.Drawing.Graphics]::FromImage($b);'
                f'$g.CopyFromScreen(0,0,0,0,$b.Size);'
                f'$b.Save("{tmp}", [System.Drawing.Imaging.ImageFormat]::Jpeg);'
                f'$g.Dispose();$b.Dispose()'
            )
            result = subprocess.run(
                ['powershell', '-NonInteractive', '-Command', ps_script],
                capture_output=True, timeout=15
            )
            if tmp.exists():
                with open(tmp, 'rb') as f:
                    screenshot_bytes = f.read()
                tmp.unlink(missing_ok=True)

        if not screenshot_bytes:
            return "Screenshot capture failed. Try: pip install Pillow"

        import base64
        img_b64 = base64.b64encode(screenshot_bytes).decode()

        # Send to cloud server as agent_data
        await ws.send(json.dumps({
            "type": "agent_data",
            "subtype": "screenshot",
            "image": img_b64,
        }))

        # Also save locally
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = Path.home() / "Desktop" / f"jarvis_{timestamp}.jpg"
        with open(save_path, 'wb') as f:
            f.write(screenshot_bytes)

        return f"Screenshot captured and sent to your phone, Sir. ({len(screenshot_bytes)//1024}KB)"

    except Exception as e:
        return f"Screenshot upload error: {e}"


def execute_command(command: str, target: str = "") -> str:
    """Route a local command to the appropriate handler."""
    command = command.lower().strip()
    target = (target or "").strip()

    if command in ("open_app", "open", "launch", "start"):
        return open_app(target)
    elif command in ("close_app", "close", "kill", "quit"):
        return close_app(target)
    elif command in ("lock", "lock_pc", "lock_screen", "lock_now"):
        return lock_pc()
    elif command in ("volume", "set_volume", "vol"):
        return set_volume(target)
    elif command in ("mute", "unmute", "toggle_mute"):
        return mute_volume()
    elif command in ("screenshot", "screen_capture", "snap"):
        # Note: screenshot_and_upload is handled separately (needs ws)
        return take_screenshot()
    elif command in ("open_url", "browse", "open_browser"):
        if target:
            if not target.startswith("http"):
                target = "https://" + target
            webbrowser.open(target)
            return f"Opened {target} in browser, Sir."
        return "No URL provided, Sir."
    elif command in ("system_info", "sysinfo", "status", "pc_status"):
        return get_system_info()
    elif command in ("alarm", "play_alarm", "siren"):
        secs = int(target) if target.isdigit() else 8
        return play_alarm(secs)
    elif command in ("warning", "warn", "warning_popup", "alert_popup"):
        return show_warning_popup(target)
    elif command in ("freeze", "freeze_input", "block_input"):
        secs = int(target) if target.isdigit() else 10
        return freeze_input(secs)
    elif command in ("logoff", "log_off", "force_logoff", "kick_user"):
        return logoff_user()
    elif command in ("disable_wifi", "wifi_off", "cut_internet"):
        return disable_wifi()
    elif command in ("enable_wifi", "wifi_on", "restore_internet"):
        return enable_wifi()
    elif command in ("running_apps", "who_is_running", "processes", "list_apps"):
        return get_running_apps()
    elif command in ("shutdown", "shut_down"):
        return "Shutdown blocked for safety, Sir. Use the Start Menu to shut down."
    elif command in ("restart", "reboot"):
        return "Restart blocked for safety, Sir. Use the Start Menu to restart."
    else:
        if target:
            return open_app(target)
        return f"Unknown command: {command}, Sir."



# ══════════════════════════════════════════════════════
#  MAIN AGENT LOOP
# ══════════════════════════════════════════════════════
async def connect_and_run():
    """Single connection attempt. Returns True if should retry, False to exit."""
    try:
        import websockets
    except ImportError:
        print("[ERROR] Missing 'websockets' package.")
        print("        Run: pip install websockets")
        return False

    try:
        print(f"[AGENT] Connecting to {SERVER}...")

        # Cloudflare requires specific headers to not get 403
        extra_headers = {
            "User-Agent": "JARVIS-LocalAgent/3.0",
            "Origin": SERVER.replace("wss://", "https://").replace("ws://", "http://").split("/ws")[0],
        }

        async with websockets.connect(
            SERVER,
            ping_interval=20,
            ping_timeout=10,
            additional_headers=extra_headers,
            open_timeout=15
        ) as ws:
            # Send auth token immediately
            await ws.send(json.dumps({"token": TOKEN}))

            # Wait for server response (greeting or error)
            try:
                first_raw = await asyncio.wait_for(ws.recv(), timeout=15)
                first_msg = json.loads(first_raw)
            except asyncio.TimeoutError:
                print("[AGENT] Server did not respond to auth. Check token.")
                return True
            except Exception as e:
                print(f"[AGENT] Auth handshake failed: {e}")
                return True

            if first_msg.get("type") == "error":
                print(f"[AGENT] AUTH FAILED: {first_msg.get('message', 'Unknown error')}")
                print("[AGENT] Your token may be wrong or expired.")
                print("[AGENT] Get a new token by logging into the web UI.")
                return False  # Don't retry auth failures

            print("[AGENT] Connected and authenticated!")
            print("[AGENT] Waiting for commands from cloud...\n")

            # Listen for commands
            async for raw_msg in ws:
                try:
                    data = json.loads(raw_msg)
                    msg_type = data.get("type", "")

                    if msg_type == "response" and "action" in data:
                        action = data["action"]
                        action_type = action.get("type", "")

                        if action_type == "local_command":
                            command = action.get("command", "")
                            target = action.get("target", "")
                            print(f"[COMMAND] {command} -> '{target}'")

                            # screenshot_upload needs ws reference — handle separately
                            if command in ("screenshot_upload", "see_screen", "live_screenshot"):
                                result = await take_screenshot_and_upload(ws)
                            else:
                                result = execute_command(command, target)
                            print(f"[RESULT]  {result}")

                            # Send result text back to cloud server
                            await ws.send(json.dumps({
                                "type": "agent_response",
                                "text": result
                            }))

                        elif action_type == "open_url":
                            url = action.get("url", "")
                            if url:
                                if not url.startswith("http"):
                                    url = "https://" + url
                                webbrowser.open(url)
                                print(f"[COMMAND] Opened URL: {url}")

                    elif msg_type == "notification":
                        title = data.get("title", "Notice")
                        body = data.get("body", "")
                        print(f"[REMINDER] {title}: {body}")
                        # Show Windows toast notification
                        try:
                            ps = (
                                f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms") | Out-Null;'
                                f'$notify = New-Object System.Windows.Forms.NotifyIcon;'
                                f'$notify.Icon = [System.Drawing.SystemIcons]::Information;'
                                f'$notify.Visible = $true;'
                                f'$notify.ShowBalloonTip(5000, "{title}", "{body}", [System.Windows.Forms.ToolTipIcon]::Info)'
                            )
                            subprocess.Popen(
                                ['powershell', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', ps],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                            )
                        except Exception:
                            pass

                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    print(f"[AGENT] Message error: {e}")

    except OSError as e:
        print(f"[AGENT] Connection failed: {e}")
    except Exception as e:
        err = str(e)
        if "403" in err:
            print("[AGENT] HTTP 403 - Cloudflare blocked connection.")
            print("        This can happen when the tunnel URL changes.")
            print("        Make sure JARVIS_SERVER in agent/.env has /ws at the end.")
            print(f"        Current URL: {SERVER}")
        elif "1000" in err or "1001" in err:
            print("[AGENT] Server closed connection normally.")
        else:
            print(f"[AGENT] Disconnected: {err}")

    return True  # Retry


async def main():
    """Main entry point."""
    print("=" * 60)
    print("  J.A.R.V.I.S. Local Agent v3.0")
    print("  PC Control Bridge")
    print("=" * 60)
    print(f"  Server: {SERVER}")
    print(f"  System: {platform.system()} {platform.release()}")
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    if not TOKEN:
        print()
        print("[ERROR] JARVIS_TOKEN is not set!")
        print()
        print("  How to get your token:")
        print("  1. Open your Jarvis URL in a browser and login")
        print("  2. Press F12 -> Console tab")
        print("  3. Type: localStorage.getItem('jarvis_token')")
        print("  4. Copy the long string")
        print("  5. Paste it in agent/.env as: JARVIS_TOKEN=<paste here>")
        print()
        sys.exit(1)

    if not SERVER.endswith("/ws"):
        print()
        print(f"[WARNING] Server URL should end with /ws")
        print(f"  Current: {SERVER}")
        print(f"  Fix in agent/.env: add /ws at the end")
        print()

    retry_delay = 2

    while True:
        should_retry = await connect_and_run()
        if not should_retry:
            break
        print(f"[AGENT] Reconnecting in {retry_delay}s...")
        await asyncio.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 30)  # Max 30s backoff


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[AGENT] Goodbye, Sir.")
