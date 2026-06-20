"""Hybrid intent router — fast keyword matching + AI fallback for ambiguous queries."""

import json
import re
from core.ai_brain import AIBrain

# ══════════════════════════════════════════════════════════════
#  KEYWORD PATTERNS — handles 80% of requests INSTANTLY (no API call)
# ══════════════════════════════════════════════════════════════
KEYWORD_RULES = [
    # (intent, patterns_list, param_extractor_function_or_None)
    ("weather", [
        r"\bweather\b", r"\btemperature\b", r"\bforecast\b",
        r"\bhow hot\b", r"\bhow cold\b", r"\bweather like\b",
        r"\brain\b.*\btoday\b", r"\bsunny\b", r"\bcloudy\b"
    ], None),

    ("time", [
        r"\bwhat time\b", r"\bthe time\b", r"\bcurrent time\b",
        r"\btime now\b", r"\btell me the time\b", r"\bwhat's the time\b"
    ], None),

    ("date", [
        r"\bwhat date\b", r"\btoday's date\b", r"\bwhat day\b",
        r"\bwhat is the date\b", r"\bwhat's the date\b"
    ], None),

    ("news", [
        r"\bnews\b", r"\bheadlines\b", r"\bwhat's happening\b",
        r"\bcurrent events\b", r"\btop stories\b"
    ], None),

    ("set_reminder", [
        r"\bremind me\b", r"\bset a reminder\b", r"\bset reminder\b",
        r"\bdon't let me forget\b", r"\bremember to\b"
    ], None),

    ("list_reminders", [
        r"\bmy reminders\b", r"\bshow reminders\b", r"\blist reminders\b",
        r"\bwhat are my reminders\b", r"\bany reminders\b", r"\bpending reminders\b"
    ], None),

    ("delete_reminder", [
        r"\bdelete reminder\b", r"\bremove reminder\b", r"\bcancel reminder\b",
        r"\bclear reminder\b", r"\bdelete all reminders\b", r"\bclear all reminders\b",
        r"\bremove all reminders\b", r"\bno more reminders\b"
    ], None),

    ("remember", [
        r"\bremember (?:that |my )\b", r"\bstore (?:that |my )\b",
        r"\bsave (?:that |my )\b", r"\bkeep in mind\b",
        r"\bnote that\b"
    ], None),

    ("recall", [
        r"\bwhat(?:'s| is) my\b", r"\bdo you remember\b",
        r"\bwhat did i (?:tell|say|store)\b", r"\brecall\b"
    ], None),

    ("forget", [
        r"\bforget (?:my |about |that )\b", r"\bdelete (?:my )\b",
        r"\berase (?:my )\b"
    ], None),

    ("joke", [
        r"\bjoke\b", r"\bfunny\b", r"\bmake me laugh\b",
        r"\btell me something funny\b", r"\bhumor\b"
    ], None),

    ("greeting", [
        r"^(?:hello|hi|hey|howdy|good morning|good evening|good afternoon|good night|sup|what's up)(?:\s|$|!|\?|,)",
    ], None),

    ("who_are_you", [
        r"\bwho are you\b", r"\bwhat are you\b", r"\btell me about yourself\b",
        r"\byour name\b", r"\bwhat is your name\b", r"\bintroduce yourself\b"
    ], None),

    ("shutdown", [
        r"\bgoodbye\b", r"\bbye\b", r"\bgo to sleep\b", r"\bshut down\b",
        r"\bgood night\b", r"\bsee you\b", r"\blog off\b"
    ], None),

    ("local_command", [
        r"\bopen (?!url|the url|a url)\w+", r"\blaunch\b", r"\bstart (?!a |the )\w+",
        r"\bclose \w+", r"\block (?:my |the )?(?:pc|computer|screen)\b",
        r"\bvolume\b", r"\bmute\b", r"\bunmute\b",
        r"\bscreenshot\b", r"\bscreen shot\b",
        r"\bshutdown (?:my |the )?(?:pc|computer)\b",
        r"\brestart (?:my |the )?(?:pc|computer)\b"
    ], None),

    ("open_url", [
        r"\bopen (?:the )?url\b", r"\bgo to (?:the )?website\b",
        r"\bbrowse to\b", r"\bvisit\b.*\.(?:com|org|net|io|in)\b",
        r"\bopen (?:the )?(?:website|site|page)\b"
    ], None),
]


# AI classification prompt (only used for ambiguous queries)
INTENT_SCHEMA = """You are an intent classifier for J.A.R.V.I.S. Given the user's message, return a JSON object with:
- "intent": one of the intents listed below, or "chat" for general conversation
- "params": extracted parameters (if any)

AVAILABLE INTENTS:
- "weather" — user asks about weather/temperature/forecast. params: {"city": "..."} (optional)
- "time" — user asks what time it is
- "date" — user asks the date / day of week
- "news" — user wants news headlines
- "set_reminder" — user wants to set a reminder. params: {"text": "...", "due": "..."}
- "list_reminders" — user wants to see their reminders
- "delete_reminder" — user wants to delete/remove/clear reminders. params: {"text": "...", "all": true/false}
- "remember" — user asks to remember something. params: {"key": "...", "value": "..."}
- "recall" — user asks to recall something remembered. params: {"key": "..."}
- "forget" — user asks to forget something. params: {"key": "..."}
- "open_url" — user wants to open a website. params: {"url": "...", "name": "..."}
- "joke" — user wants a joke
- "greeting" — user says hello/hi
- "who_are_you" — user asks who Jarvis is
- "shutdown" — user says goodbye/sleep
- "local_command" — user wants to control their PC (open app, volume, brightness, lock, etc.). params: {"command": "...", "target": "..."}
- "chat" — anything else, general conversation

RULES:
- Return ONLY valid JSON, nothing else
- For "open_url", infer the URL (youtube.com, google.com, github.com, etc.)
- For "remember", split into key and value: "remember my wifi password is abc123" → {"key": "wifi password", "value": "abc123"}
- For "recall", extract what to recall: "what's my wifi password" → {"key": "wifi password"}
- For "set_reminder", extract the reminder text and time if given
- For "delete_reminder", set "all": true if user says "clear all" or "delete all"
- For "local_command", extract: "open chrome" → {"command": "open_app", "target": "chrome"}
- When unsure, default to "chat"

User message: """


class IntentRouter:
    def __init__(self, brain: AIBrain):
        self.brain = brain

    def _keyword_match(self, query: str) -> dict | None:
        """Try to classify via keyword patterns. Returns None if no match."""
        query_lower = query.lower().strip()

        for intent, patterns, _ in KEYWORD_RULES:
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    params = self._extract_params(intent, query)
                    return {"intent": intent, "params": params}
        return None

    def _extract_params(self, intent: str, query: str) -> dict:
        """Extract parameters for known intents from the raw query."""
        q = query.lower().strip()
        params = {}

        if intent == "set_reminder":
            # Remove the trigger phrase to get the reminder text
            # We use non-anchored matching to allow "please remind me to" etc.
            text = re.sub(r".*?(?:remind me to |set (?:a )?reminder (?:to |for )?|remember to )", "", q, flags=re.IGNORECASE).strip()
            params["text"] = text or query

        elif intent == "delete_reminder":
            if re.search(r"\ball\b", q):
                params["all"] = True
            else:
                text = re.sub(r".*?(?:delete |remove |cancel |clear )(?:the )?(?:reminder )?(?:about |for )?", "", q, flags=re.IGNORECASE).strip()
                params["text"] = text
                params["all"] = False

        elif intent == "remember":
            # "remember my wifi password is abc123"
            match = re.search(r"(?:remember|store|save|note)\s+(?:that\s+)?(?:my\s+)?(.+?)\s+is\s+(.+)", q, re.IGNORECASE)
            if match:
                params["key"] = match.group(1).strip()
                params["value"] = match.group(2).strip()

        elif intent == "recall":
            # "what's my wifi password"
            match = re.search(r"(?:what(?:'s| is) my\s+)(.+?)(?:\?|$)", q, re.IGNORECASE)
            if match:
                params["key"] = match.group(1).strip()

        elif intent == "forget":
            match = re.search(r"(?:forget|delete|erase)\s+(?:my\s+)?(.+?)(?:\?|$)", q, re.IGNORECASE)
            if match:
                params["key"] = match.group(1).strip()

        elif intent == "local_command":
            # "open chrome" → command=open_app, target=chrome
            match = re.search(r"(?:open|launch|start)\s+(.+)", q, re.IGNORECASE)
            if match:
                params["command"] = "open_app"
                params["target"] = match.group(1).strip()
            elif re.search(r"close\s+(.+)", q, re.IGNORECASE):
                match = re.search(r"close\s+(.+)", q, re.IGNORECASE)
                params["command"] = "close_app"
                params["target"] = match.group(1).strip()
            elif re.search(r"lock", q):
                params["command"] = "lock"
            elif re.search(r"screenshot|screen shot", q):
                params["command"] = "screenshot"
            elif re.search(r"volume", q):
                params["command"] = "volume"
                vol_match = re.search(r"(\d+)", q)
                params["target"] = vol_match.group(1) if vol_match else "50"

        elif intent == "weather":
            # Try to extract city: "weather in Mumbai"
            match = re.search(r"(?:weather|temperature|forecast)\s+(?:in|for|at)\s+(.+?)(?:\?|$)", q, re.IGNORECASE)
            if match:
                params["city"] = match.group(1).strip()

        return params

    def _ai_classify(self, query: str) -> dict:
        """Use AI for intent classification (slower but handles edge cases)."""
        try:
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
                # For non-Groq, use a fresh brain call
                from core.ai_brain import AIBrain
                classifier = AIBrain()
                raw = classifier.chat(INTENT_SCHEMA + query)

            # Parse JSON from response (handle markdown code blocks)
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            # Try to find JSON in the response
            json_match = re.search(r'\{[^}]+\}', raw)
            if json_match:
                return json.loads(json_match.group())

            return json.loads(raw.strip())
        except (json.JSONDecodeError, Exception) as e:
            print(f"[INTENT] AI classification failed: {e}")
            return {"intent": "chat", "params": {}}

    def classify(self, query: str) -> dict:
        """Classify user intent. Keyword-first, AI-fallback.

        Keyword matching handles ~80% of requests instantly (no API call).
        AI classification is only used for ambiguous queries.
        """
        # Step 1: Try keyword matching (instant, free)
        result = self._keyword_match(query)
        if result:
            print(f"[INTENT] Keyword match → {result['intent']}")
            return result

        # Step 2: Fall back to AI classification
        print(f"[INTENT] No keyword match, using AI classification...")
        result = self._ai_classify(query)
        print(f"[INTENT] AI result → {result.get('intent', 'chat')}")
        return result
