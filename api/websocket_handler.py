"""WebSocket handler — real-time voice + text pipeline with full skill routing."""

import json
import base64
from fastapi import WebSocket, WebSocketDisconnect
from api.auth import verify_token, create_token
from core.ai_brain import AIBrain
from core.intent_router import IntentRouter
from core.tts_engine import generate_speech
from skills import weather, reminders, memory, news
from skills.time_date import get_time, get_date, get_briefing_intro
from config import settings

# Shared brain instance (per-connection would waste memory)
brain = AIBrain()
router = IntentRouter(brain)

# Track connected clients for broadcasting notifications
connected_clients: list[WebSocket] = []
# Track which clients are local agents (vs web browsers)
agent_clients: set[WebSocket] = set()


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

            # Handle ping/pong keepalive (from both web UI and local agent)
            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
                continue

            # Handle agent registration
            if msg_type == "agent_hello":
                agent_clients.add(ws)
                print(f"[WS] Local agent registered. Agents online: {len(agent_clients)}")
                await ws.send_json({"type": "agent_registered"})
                continue

            # Handle token refresh request (from local agent)
            if msg_type == "refresh_token":
                new_token = create_token(settings.JARVIS_PASSWORD)
                if new_token:
                    await ws.send_json({"type": "new_token", "token": new_token})
                    print("[WS] Token refreshed for agent.")
                continue

            if not text and msg_type != "agent_data":
                continue

            print(f"[USER] {text or msg_type}")

            if msg_type == "action":
                await _handle_action(ws, data.get("skill", ""), data)
            elif msg_type == "agent_data":
                # Local agent is sending data back (screenshot, status, etc.)
                await _handle_agent_data(ws, data)
            elif msg_type == "agent_response":
                # Text response from local agent execution
                for client in connected_clients:
                    if client != ws:
                        try:
                            await client.send_json({"type": "response", "text": text})
                        except Exception:
                            pass
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
        agent_clients.discard(ws)
        print(f"[WS] Client disconnected. Total: {len(connected_clients)}, Agents: {len(agent_clients)}")


async def _handle_chat(ws: WebSocket, text: str):
    """Classify intent and route to the appropriate handler."""
    await ws.send_json({"type": "status", "state": "processing"})

    try:
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

        elif intent == "delete_reminder":
            if params.get("all", False):
                response_text = await reminders.clear_all_reminders()
            else:
                search_text = params.get("text", "")
                if search_text:
                    response_text = await reminders.delete_reminder(text_search=search_text)
                else:
                    # If no specific text, clear all
                    response_text = await reminders.clear_all_reminders()

        elif intent == "remember":
            key = params.get("key", "")
            value = params.get("value", "")
            if key and value:
                response_text = await memory.remember(key, value)
            else:
                # AI couldn't extract key/value, ask for clarification
                response_text = brain.chat(text)

        elif intent == "recall":
            key = params.get("key", "")
            if key:
                recalled = await memory.recall(key)
                if recalled:
                    response_text = f"You told me: {recalled}, Sir."
                else:
                    response_text = f"I don't have anything stored about '{key}', Sir."
            else:
                # Show all memories
                response_text = await memory.get_all_memories()

        elif intent == "forget":
            key = params.get("key", "")
            if key:
                response_text = await memory.forget(key)
            else:
                response_text = "What would you like me to forget, Sir?"

        elif intent == "open_url":
            url = params.get("url", "")
            name = params.get("name", "the page")
            if url and not url.startswith("http"):
                url = "https://" + url
            response_text = f"Opening {name}, Sir."
            action = {"type": "open_url", "url": url}

        elif intent == "joke":
            response_text = brain.chat("Tell me one short clever joke. Plain spoken English, no formatting.")

        elif intent == "greeting":
            response_text = brain.chat(f"The user greeted you: '{text}'. Respond warmly and briefly as JARVIS.")

        elif intent == "who_are_you":
            response_text = "I am J.A.R.V.I.S. — Just A Rather Very Intelligent System, Sir. Built by Mr. Ashish Kumar Laheri."

        elif intent == "shutdown":
            response_text = "Standing by, Sir. I'll be here when you need me."

        elif intent == "local_command":
            if not agent_clients:
                await ws.send_json({"type": "agent_data", "text": "Local agent is not connected, Sir. Command cancelled."})
                return

            command = params.get("command", "")
            target = params.get("target", "")
            response_text = f"Sending command to your local agent, Sir."
            action = {"type": "local_command", "command": command, "target": target}

            # Send command specifically to agent clients
            for agent_ws in agent_clients:
                try:
                    await agent_ws.send_json({"type": "response", "text": response_text, "action": action})
                except Exception:
                    pass

        else:
            # General chat — send to AI
            response_text = brain.chat(text)

        await _send_response(ws, response_text, action)

    except Exception as e:
        print(f"[CHAT] Error handling message: {e}")
        await _send_response(ws, "Something went wrong processing your request, Sir. Please try again.")


async def _handle_agent_data(ws: WebSocket, data: dict):
    """Handle data sent back from the local agent (screenshots, status, etc.)."""
    subtype = data.get("subtype", "")
    print(f"[AGENT_DATA] subtype={subtype}")

    # Broadcast to all web UI clients (everyone except the agent socket itself)
    broadcast_payload = {"type": "agent_data", "subtype": subtype}

    if subtype in ("screenshot", "webcam"):
        broadcast_payload["image"] = data.get("image", "")
        broadcast_payload["text"] = "Live image from your PC, Sir."
    elif subtype == "status":
        broadcast_payload["text"] = data.get("text", "")
    elif subtype == "file_transfer":
        broadcast_payload["filename"] = data.get("filename", "file")
        broadcast_payload["mime_type"] = data.get("mime_type", "application/octet-stream")
        broadcast_payload["file_data"] = data.get("file_data", "")
        broadcast_payload["text"] = f"File ready for download: {broadcast_payload['filename']}"
    elif subtype == "directory_listing":
        broadcast_payload["path"] = data.get("path", "")
        broadcast_payload["items"] = data.get("items", [])
        broadcast_payload["text"] = f"Directory contents received."
    else:
        broadcast_payload["text"] = data.get("text", "Data received from agent.")

    for client in connected_clients:
        if client != ws:
            try:
                await client.send_json(broadcast_payload)
            except Exception:
                pass


async def _handle_action(ws: WebSocket, skill: str, raw_data: dict = None):
    """Handle quick action button presses."""
    await ws.send_json({"type": "status", "state": "processing"})

    try:
        # Security panel commands — broadcast to the local agent
        if skill == "security" and raw_data:
            if not agent_clients:
                await ws.send_json({"type": "agent_data", "text": "Local agent is offline, Sir. Action cancelled."})
                return
                
            # Extract command and target accurately
            command = raw_data.get("command", "") or raw_data.get("text", "")
            target = ""
            nested_action = raw_data.get("action", {})
            if isinstance(nested_action, dict):
                target = nested_action.get("target", "")
                if nested_action.get("command"):
                    command = nested_action.get("command")

            action_payload = {
                "type": "response",
                "text": f"Security command '{command}' sent to your PC.",
                "action": {"type": "local_command", "command": command, "target": target}
            }
            # Send specifically to agent clients
            for agent_ws in agent_clients:
                try:
                    await agent_ws.send_json(action_payload)
                except Exception:
                    pass
            # Acknowledge to web client
            await ws.send_json({"type": "status", "state": "processing"})
            return

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
        elif skill == "clear_reminders":
            text = await reminders.clear_all_reminders()
        else:
            text = "I don't recognise that action, Sir."
        await _send_response(ws, text)
    except Exception as e:
        print(f"[ACTION] Error: {e}")
        await _send_response(ws, "That action failed, Sir. Please try again.")


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

    try:
        await ws.send_json(payload)
    except Exception as e:
        print(f"[WS] Send error: {e}")


async def broadcast_notification(title: str, body: str):
    """Send a notification to all connected clients."""
    msg = {"type": "notification", "title": title, "body": body}
    for ws in connected_clients[:]:
        try:
            await ws.send_json(msg)
        except Exception:
            if ws in connected_clients:
                connected_clients.remove(ws)
