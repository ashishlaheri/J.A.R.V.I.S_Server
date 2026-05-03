"""AI-powered intent router — replaces rigid keyword matching."""

import json
from core.ai_brain import AIBrain

INTENT_SCHEMA = """You are an intent classifier for J.A.R.V.I.S. Given the user's message, return a JSON object with:
- "intent": one of the intents listed below, or "chat" for general conversation
- "params": extracted parameters (if any)

AVAILABLE INTENTS:
- "weather" — user asks about weather/temperature/forecast. params: {"city": "..."}  (optional)
- "time" — user asks what time it is
- "date" — user asks the date / day of week
- "news" — user wants news headlines
- "set_reminder" — user wants to set a reminder. params: {"text": "...", "due": "..."}
- "list_reminders" — user wants to see their reminders
- "remember" — user asks to remember something. params: {"key": "...", "value": "..."}
- "recall" — user asks to recall something remembered. params: {"key": "..."}
- "forget" — user asks to forget something. params: {"key": "..."}
- "open_url" — user wants to open a website. params: {"url": "...", "name": "..."}
- "joke" — user wants a joke
- "greeting" — user says hello/hi
- "who_are_you" — user asks who Jarvis is
- "shutdown" — user says goodbye/sleep/shut down
- "local_command" — user wants to control their PC (open app, volume, brightness, lock, etc.). params: {"command": "...", "target": "..."}
- "chat" — anything else, general conversation

RULES:
- Return ONLY valid JSON, nothing else
- For "open_url", infer the URL (youtube.com, google.com, github.com, etc.)
- For "remember", split into key and value: "remember my wifi password is abc123" → {"key": "wifi password", "value": "abc123"}
- For "recall", extract what to recall: "what's my wifi password" → {"key": "wifi password"}
- For "set_reminder", extract the reminder text and time if given
- When unsure, default to "chat"

User message: """


class IntentRouter:
    def __init__(self, brain: AIBrain):
        self.brain = brain
        # Separate lightweight AI instance for classification so it doesn't pollute chat history
        self._classifier = AIBrain()

    def classify(self, query: str) -> dict:
        """Classify user intent using the AI. Returns {"intent": "...", "params": {...}}"""
        try:
            # Use a direct API call, not the chat history
            from groq import Groq
            from config import settings
            import os

            provider = settings.AI_PROVIDER
            if provider == "groq":
                client = Groq(api_key=os.getenv("GROQ_API_KEY"))
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": INTENT_SCHEMA + query}],
                    max_tokens=150, temperature=0.1,
                )
                raw = response.choices[0].message.content.strip()
            else:
                # Fallback: use the brain's chat (works for any provider)
                raw = self._classifier.chat(INTENT_SCHEMA + query)

            # Parse JSON from response
            # Handle cases where LLM wraps in markdown code blocks
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            
            result = json.loads(raw.strip())
            return result
        except (json.JSONDecodeError, Exception) as e:
            print(f"[INTENT] Classification failed: {e}, falling back to chat")
            return {"intent": "chat", "params": {}}
