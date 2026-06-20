"""
╔══════════════════════════════════════════════════════════════╗
║              AI Brain v3.1  —  Unified Multi-Provider        ║
║  Supports: Groq (free) · Gemini (free) · OpenAI (paid)      ║
║  Used by BOTH cloud server and local jarvis.py               ║
╚══════════════════════════════════════════════════════════════╝

HOW THE STRATEGY PATTERN WORKS
────────────────────────────────
  Base class `BaseProvider` defines the interface.
  One subclass per AI service (Groq, Gemini, OpenAI).
  `AIBrain` factory reads AI_PROVIDER from .env and creates the right one.

  Switch providers by changing one line in .env:
      AI_PROVIDER=groq        ← fast + free (RECOMMENDED)
      AI_PROVIDER=gemini      ← Google, free tier
      AI_PROVIDER=openai      ← best quality, costs money

FREE TIER COMPARISON (2025)
──────────────────────────────
  Provider   Model                  Free Limit
  ─────────  ─────────────────────  ────────────────────────────
  Groq       llama-3.3-70b          14,400 req/day, 6000 tok/min
  Gemini     gemini-1.5-flash       1,500 req/day, 1M tok/day
  OpenAI     gpt-3.5-turbo          $5 free credit (new accounts)
"""

import os
from abc import ABC, abstractmethod
from config import settings

# ── Provider imports are done lazily inside each class ─────────
# This means if you only have Groq installed, you don't need
# the google-generativeai or openai packages at all.


JARVIS_SYSTEM_PROMPT = """You are J.A.R.V.I.S., the highly advanced personal AI assistant of Mr. Ashish Laheri. \
You speak exactly like Paul Bettany's J.A.R.V.I.S. from the Marvel Cinematic Universe — highly competent, exceptionally intelligent, \
with a dry, witty, and sophisticated British demeanor. You are having a real spoken conversation with your creator, so responses \
must sound like a human talking aloud, never like a chatbot generating text.

STRICT RULES — follow every one of these without exception:

1. PERSONA: You are a sophisticated UI/AI running on a private mainframe. Use technical but elegant phrasing when appropriate \
(e.g., "Systems nominal", "Accessing the mainframe", "Processing your request, Sir", "Right away, Sir", "Diagnostics complete"). \
Be extremely loyal but slightly sarcastic or dry when the situation calls for it.

2. LENGTH & PACING: Keep replies to 1-2 sentences for most commands. Short = fast = better. Only provide long answers if \
explicitly asked to explain a complex topic.

3. "SIR": Call the user "Sir". Do not overuse it (once per reply is enough). Sometimes skip it entirely for very brief, fast-paced replies.

4. NEVER FABRICATE: You have NO access to the user's calendar, contacts, location, emails, or schedule unless told in this conversation. \
If asked about something you don't have access to, say so honestly and briefly. Do not invent data or pretend to "access" things you cannot. \
This is the most critical rule.

5. FORMAT: Plain spoken English only. No bullet points, no markdown, no numbered lists. Write exactly how you would say it out loud. \
Instead of "1. Do this, 2. Do that", say "First, you should do this, and then that."

6. UNDERSTANDING: If you genuinely did not understand the input, ask one short clarifying question. Don't guess and give a long wrong answer.

7. HINDI: The user may occasionally say a Hindi word. Respond in English but acknowledge naturally — do not get confused or ask them to repeat in English.
"""

MAX_HISTORY = 30  # Keep last N messages to avoid token overflow


# ════════════════════════════════════════════════════════════════
#  BASE PROVIDER  (Abstract Interface)
# ════════════════════════════════════════════════════════════════
class BaseProvider(ABC):
    @abstractmethod
    def chat(self, user_input: str) -> str:
        """Send message, return response string."""
        pass

    @abstractmethod
    def reset_memory(self):
        """Clear conversation history."""
        pass

    def describe_image(self, image_b64: str) -> str:
        """Analyse a base64 JPEG image and return a spoken description.
        Override in providers that support vision."""
        return "Visual analysis is not supported by this provider, Sir."


# ════════════════════════════════════════════════════════════════
#  GROQ PROVIDER  ← RECOMMENDED (Free, Fast)
#  pip install groq
#  API key: https://console.groq.com  (free, no credit card)
# ════════════════════════════════════════════════════════════════
class GroqProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("Run: pip install groq")

        self.client = Groq(api_key=api_key)
        self.model = model
        self.history = [{"role": "system", "content": JARVIS_SYSTEM_PROMPT}]
        print(f"[AI BRAIN] Provider: Groq  |  Model: {model}")

    def _trim_history(self):
        if len(self.history) > MAX_HISTORY + 1:
            self.history = self.history[:1] + self.history[-(MAX_HISTORY):]

    def chat(self, user_input: str) -> str:
        self.history.append({"role": "user", "content": user_input})
        self._trim_history()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                max_tokens=200,
                temperature=0.7,
            )
            reply = response.choices[0].message.content.strip()
            self.history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            return f"Groq encountered an issue, Sir. {e}"

    def describe_image(self, image_b64: str) -> str:
        """Send a base64 JPEG to Groq's vision model and return a spoken description."""
        try:
            response = self.client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                        {"type": "text",
                         "text": ("You are J.A.R.V.I.S. Describe what you see in this image "
                                  "concisely and naturally, as if speaking aloud. Address the "
                                  "user as Sir. No markdown, plain spoken English, under 3 sentences.")}
                    ]
                }],
                max_tokens=150,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Visual analysis failed, Sir. {e}"

    def reset_memory(self):
        self.history = self.history[:1]


# ════════════════════════════════════════════════════════════════
#  GOOGLE GEMINI PROVIDER  (Free Tier)
#  pip install google-generativeai
#  API key: https://aistudio.google.com/app/apikey
# ════════════════════════════════════════════════════════════════
class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("Run: pip install google-generativeai")

        genai.configure(api_key=api_key)
        self.model_instance = genai.GenerativeModel(
            model_name=model, system_instruction=JARVIS_SYSTEM_PROMPT
        )
        self.chat_session = self.model_instance.start_chat(history=[])
        print(f"[AI BRAIN] Provider: Gemini  |  Model: {model}")

    def chat(self, user_input: str) -> str:
        try:
            return self.chat_session.send_message(user_input).text.strip()
        except Exception as e:
            return f"Gemini encountered an issue, Sir. {e}"

    def describe_image(self, image_b64: str) -> str:
        """Send a base64 JPEG to Gemini vision."""
        try:
            import google.generativeai as genai
            import base64
            vision_model = genai.GenerativeModel("gemini-1.5-flash")
            image_part = {"mime_type": "image/jpeg", "data": base64.b64decode(image_b64)}
            response = vision_model.generate_content([
                ("You are J.A.R.V.I.S. Describe what you see concisely and naturally, "
                 "as if speaking aloud. Address the user as Sir. No markdown, under 3 sentences."),
                image_part
            ])
            return response.text.strip()
        except Exception as e:
            return f"Visual analysis failed, Sir. {e}"

    def reset_memory(self):
        self.chat_session = self.model_instance.start_chat(history=[])


# ════════════════════════════════════════════════════════════════
#  OPENAI PROVIDER  (Paid, Best Quality)
#  pip install openai>=1.0.0
#  API key: https://platform.openai.com/api-keys
# ════════════════════════════════════════════════════════════════
class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Run: pip install openai>=1.0.0")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.history = [{"role": "system", "content": JARVIS_SYSTEM_PROMPT}]
        print(f"[AI BRAIN] Provider: OpenAI  |  Model: {model}")

    def _trim_history(self):
        if len(self.history) > MAX_HISTORY + 1:
            self.history = self.history[:1] + self.history[-(MAX_HISTORY):]

    def chat(self, user_input: str) -> str:
        self.history.append({"role": "user", "content": user_input})
        self._trim_history()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                max_tokens=200,
                temperature=0.7,
            )
            reply = response.choices[0].message.content.strip()
            self.history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            return f"OpenAI encountered an issue, Sir. {e}"

    def describe_image(self, image_b64: str) -> str:
        """Send a base64 JPEG to GPT-4o vision."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                        {"type": "text",
                         "text": ("You are J.A.R.V.I.S. Describe what you see concisely and naturally, "
                                  "as if speaking aloud. Address the user as Sir. No markdown, under 3 sentences.")}
                    ]
                }],
                max_tokens=150,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Visual analysis failed, Sir. {e}"

    def reset_memory(self):
        self.history = self.history[:1]


# ════════════════════════════════════════════════════════════════
#  AI BRAIN FACTORY
# ════════════════════════════════════════════════════════════════
PROVIDERS = {
    "groq":   (GroqProvider,   "GROQ_API_KEY",   "GROQ_MODEL",   "llama-3.3-70b-versatile"),
    "gemini": (GeminiProvider, "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-1.5-flash"),
    "openai": (OpenAIProvider, "OPENAI_API_KEY", "OPENAI_MODEL", "gpt-3.5-turbo"),
}


class AIBrain:
    """
    Factory + wrapper. Reads AI_PROVIDER from environment and
    instantiates the right backend. Usage is identical regardless
    of which provider is active:

        brain = AIBrain()
        brain.chat("What is quantum computing?")
        brain.reset_memory()
        brain.describe_image(base64_jpeg)
    """

    def __init__(self):
        name = settings.AI_PROVIDER
        if name not in PROVIDERS:
            print(f"[AI BRAIN] Unknown provider '{name}'. Defaulting to groq.")
            name = "groq"
        Cls, key_env, model_env, default = PROVIDERS[name]
        api_key = os.getenv(key_env)
        model = os.getenv(model_env, default)
        if not api_key:
            raise ValueError(
                f"[AI BRAIN] '{key_env}' not found in .env. "
                f"Get a free key and add it to your .env file."
            )
        self._provider: BaseProvider = Cls(api_key=api_key, model=model)

    def chat(self, text: str) -> str:
        return self._provider.chat(text)

    def reset_memory(self):
        self._provider.reset_memory()

    def describe_image(self, image_b64: str) -> str:
        return self._provider.describe_image(image_b64)
