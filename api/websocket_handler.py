"""WebSocket handler — real-time voice + text pipeline."""

import json
import base64
from fastapi import WebSocket, WebSocketDisconnect
from api.auth import verify_token
from core.ai_brain import AIBrain
from core.intent_router import IntentRouter
from core.tts_engine import generate_speech
from skills import weather, reminders, memory, news
from skills.time_date import get_time, get_date, get_briefing_intro

# Shared brain instance (per-connection would waste memory)
brain = AIBrain()
router = IntentRouter(brain)

# Track connected clients for broadcasting notifications
connected_clients: list[WebSocket] = []


async def handle_websocket(ws: WebSocket):
    """Main WebSocket handler — authenticates, then processes messages."""
    await ws.accept()

    # ── Auth: first message must be the JWT token ──
    try:
        auth_msg = await ws.receive_text()
        auth_data = json.loads(auth_msg)
        if not verify_token(auth_data.get("token", "")):
            await ws.send_json({"type": "error", "message": "Authentication failed."})
            await ws.close()
            return
    except Exception:
        await ws.close()
        return

    connected_clients.append(ws)
    print(f"[WS] Client connected. Total: {len(connected_clients)}")

    # Send greeting
    greeting = get_briefing_intro()
    await _send_response(ws, greeting)

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "chat")
            text = data.get("text", "").strip()

            if not text:
                continue

            print(f"[USER] {text}")

            if msg_type == "action":
                # Quick action buttons (weather, news, etc.)
                await _handle_action(ws, data.get("skill", ""))
            else:
                # Chat / voice input — classify and route
                await _handle_chat(ws, text)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        if ws in connected_clients:
            connected_clients.remove(ws)
        print(f"[WS] Client disconnected. Total: {len(connected_clients)}")


async def _handle_chat(ws: WebSocket, text: str):
    """Classify intent and route to the appropriate handler."""
    await ws.send_json({"type": "status", "state": "processing"})

    # Classify intent
    intent_data = router.classify(text)
    intent = intent_data.get("intent", "chat")
    params = intent_data.get("params", {})
    print(f"[INTENT] {intent} | params={params}")

    response_text = ""
    action = None

    if intent == "weather":
        city = params.get("city")
        response_text = await weather.get_weather(city)

    elif intent == "time":
        response_text = get_time()

    elif intent == "date":
        response_text = get_date()

    elif intent == "news":
        response_text = await news.get_headlines()

    elif intent == "set_reminder":
        r_text = params.get("text", text)
        due = params.get("due")
        response_text = await reminders.add_reminder(r_text, due)

    elif intent == "list_reminders":
        response_text = await reminders.get_reminders()

    elif intent == "remember":
        key = params.get("key", "")
        value = params.get("value", "")
        if key and value:
            response_text = await memory.remember(key, value)
        else:
            response_text = brain.chat(text)

    elif intent == "recall":
        key = params.get("key", "")
        recalled = await memory.recall(key)
        if recalled:
            response_text = f"You told me: {recalled}, Sir."
        else:
            response_text = f"I don't have anything stored about '{key}', Sir."

    elif intent == "forget":
        key = params.get("key", "")
        response_text = await memory.forget(key)

    elif intent == "open_url":
        url = params.get("url", "")
        name = params.get("name", "the page")
        response_text = f"Opening {name}, Sir."
        action = {"type": "open_url", "url": url}

    elif intent == "joke":
        response_text = brain.chat("Tell me one short clever joke. Plain spoken English, no formatting.")

    elif intent == "greeting":
        response_text = "Hello Sir, always a pleasure."

    elif intent == "who_are_you":
        response_text = "I am J.A.R.V.I.S. — Just A Rather Very Intelligent System, Sir. Built by Mr. Ashish Kumar Laheri."

    elif intent == "shutdown":
        response_text = "Standing by, Sir. I'll be here when you need me."

    elif intent == "local_command":
        command = params.get("command", "")
        target = params.get("target", "")
        response_text = f"Sending command to your local agent, Sir."
        action = {"type": "local_command", "command": command, "target": target}

    else:
        # General chat — send to AI
        response_text = brain.chat(text)

    await _send_response(ws, response_text, action)


async def _handle_action(ws: WebSocket, skill: str):
    """Handle quick action button presses."""
    if skill == "weather":
        text = await weather.get_weather()
    elif skill == "news":
        text = await news.get_headlines()
    elif skill == "reminders":
        text = await reminders.get_reminders()
    elif skill == "briefing":
        w = await weather.get_weather()
        n = await news.get_headlines(3)
        r = await reminders.get_reminders()
        text = f"{get_briefing_intro()} {w} {n} {r}"
    else:
        text = "I don't recognise that action, Sir."
    await _send_response(ws, text)


async def _send_response(ws: WebSocket, text: str, action: dict = None):
    """Generate TTS audio and send response to client."""
    try:
        audio_bytes = await generate_speech(text)
        audio_b64 = base64.b64encode(audio_bytes).decode()
    except Exception as e:
        print(f"[TTS] Error: {e}")
        audio_b64 = None

    payload = {"type": "response", "text": text}
    if audio_b64:
        payload["audio"] = audio_b64
    if action:
        payload["action"] = action

    await ws.send_json(payload)


async def broadcast_notification(title: str, body: str):
    """Send a notification to all connected clients."""
    msg = {"type": "notification", "title": title, "body": body}
    for ws in connected_clients[:]:
        try:
            await ws.send_json(msg)
        except Exception:
            connected_clients.remove(ws)
