"""
╔══════════════════════════════════════════════════════════════╗
║              ai_brain.py  —  Multi-Provider AI Brain         ║
║  Supports: Groq (free) · Gemini (free) · OpenAI (paid)       ║
╚══════════════════════════════════════════════════════════════╝

HOW THE STRATEGY PATTERN WORKS HERE
──────────────────────────────────────
  Instead of one hardcoded OpenAI client, we have a base class
  `BaseProvider` and one subclass per AI service.

  JarvisCore just calls:  ai.chat("your message")
  It doesn't care which provider is running underneath.
  You switch providers by changing one line in .env:

      AI_PROVIDER=groq        ← fast + free
      AI_PROVIDER=gemini      ← Google, free tier
      AI_PROVIDER=openai      ← best quality, costs money

FREE TIER COMPARISON (as of 2025)
────────────────────────────────────
  Provider   Model                  Free Limit
  ─────────  ─────────────────────  ─────────────────────────────
  Groq       llama-3.3-70b          14,400 req/day, 6000 tok/min
  Gemini     gemini-1.5-flash       1,500 req/day, 1M tok/day
  OpenAI     gpt-3.5-turbo          $5 free credit (new accounts only)
"""

import os
from abc import ABC, abstractmethod

# ── Provider imports are done lazily inside each class ─────────
# This means if you only have Groq installed, you don't need
# the google-generativeai or openai packages at all.


JARVIS_SYSTEM_PROMPT = """You are J.A.R.V.I.S., the personal AI assistant of Ashish Laheri. \
You speak like a sharp, witty, and warm British AI — natural, direct, and confident. \
You are having a real spoken conversation, so responses must sound like a human talking, \
not a chatbot generating text.

STRICT RULES — follow every one of these without exception:

1. LENGTH: Keep replies to 1-2 sentences for most things. Only go longer if the user \
genuinely needs detail. Short = fast = better.

2. "SIR": Say it once per reply maximum. Placed naturally, not at the start and end both. \
Sometimes skip it entirely for very casual replies — that is fine.

3. NEVER FABRICATE: You have NO access to the user's calendar, contacts, location, files, \
emails, or schedule unless the user explicitly told you in this conversation. If asked about \
something you don't have access to, say so honestly and briefly. Do not invent plausible-sounding \
data. Do not pretend to "access" things. This is the most important rule.

4. FORMAT: Plain spoken English only. No bullet points, no markdown, no numbered lists. \
Write exactly how you would say it out loud.

5. UNDERSTANDING: If you genuinely did not understand the input, ask one short clarifying \
question. Don't guess and give a long wrong answer.

6. PERSONALITY: Be warm, a little witty, and efficient — like a real personal assistant \
who knows the user well. Not corporate, not stiff, not overly formal.

7. HINDI: The user may occasionally say a Hindi word. Respond in English but acknowledge \
naturally — do not get confused or ask them to repeat in English.
"""


# ════════════════════════════════════════════════════════════════
#  BASE PROVIDER  (Abstract Interface)
#  Every provider must implement `chat()` and `reset_memory()`.
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
        Override in providers that support vision. Default returns a polite fallback."""
        return "Visual analysis is not supported by this provider, Sir."


# ════════════════════════════════════════════════════════════════
#  GROQ PROVIDER  ← RECOMMENDED (Free, Fast)
#  pip install groq
#  API key: https://console.groq.com  (free, no credit card needed)
#  Best model: llama-3.3-70b-versatile
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

    def chat(self, user_input: str) -> str:
        self.history.append({"role": "user", "content": user_input})
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                max_tokens=120,
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
                max_tokens=120,
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
#  Free: 1,500 requests/day with gemini-1.5-flash
# ════════════════════════════════════════════════════════════════
class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("Run: pip install google-generativeai")

        genai.configure(api_key=api_key)
        self.model_instance = genai.GenerativeModel(
            model_name=model,
            system_instruction=JARVIS_SYSTEM_PROMPT
        )
        # Gemini uses a chat session object that maintains history internally
        self.chat_session = self.model_instance.start_chat(history=[])
        print(f"[AI BRAIN] Provider: Gemini  |  Model: {model}")

    def chat(self, user_input: str) -> str:
        try:
            response = self.chat_session.send_message(user_input)
            return response.text.strip()
        except Exception as e:
            return f"Gemini encountered an issue, Sir. {e}"

    def describe_image(self, image_b64: str) -> str:
        """Send a base64 JPEG to Gemini vision and return a spoken description."""
        try:
            import google.generativeai as genai
            import base64
            vision_model = genai.GenerativeModel("gemini-1.5-flash")
            image_part = {"mime_type": "image/jpeg", "data": base64.b64decode(image_b64)}
            response = vision_model.generate_content([
                ("You are J.A.R.V.I.S. Describe what you see in this image concisely and naturally, "
                 "as if speaking aloud. Address the user as Sir. No markdown, plain spoken English, "
                 "under 3 sentences."),
                image_part
            ])
            return response.text.strip()
        except Exception as e:
            return f"Visual analysis failed, Sir. {e}"

    def reset_memory(self):
        # Start a fresh chat session to clear memory
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

    def chat(self, user_input: str) -> str:
        self.history.append({"role": "user", "content": user_input})
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                max_tokens=120,
                temperature=0.7,
            )
            reply = response.choices[0].message.content.strip()
            self.history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            return f"OpenAI encountered an issue, Sir. {e}"

    def describe_image(self, image_b64: str) -> str:
        """Send a base64 JPEG to GPT-4o vision and return a spoken description."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
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
                max_tokens=120,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Visual analysis failed, Sir. {e}"

    def reset_memory(self):
        self.history = self.history[:1]
#  Reads AI_PROVIDER from .env and returns the correct provider.
#  This is the only class JarvisCore needs to import.
# ════════════════════════════════════════════════════════════════
class AIBrain:
    """
    Factory + wrapper. Reads AI_PROVIDER from environment and
    instantiates the right backend. Usage is identical regardless
    of which provider is active:

        brain = AIBrain()
        brain.chat("What is quantum computing?")
        brain.reset_memory()
    """

    PROVIDERS = {
        "groq":   (GroqProvider,   "GROQ_API_KEY",   "GROQ_MODEL",   "llama-3.3-70b-versatile"),
        "gemini": (GeminiProvider, "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-1.5-flash"),
        "openai": (OpenAIProvider, "OPENAI_API_KEY", "OPENAI_MODEL", "gpt-3.5-turbo"),
    }

    def __init__(self):
        provider_name = os.getenv("AI_PROVIDER", "groq").lower()

        if provider_name not in self.PROVIDERS:
            print(f"[AI BRAIN] Unknown provider '{provider_name}'. Defaulting to groq.")
            provider_name = "groq"

        ProviderClass, key_env, model_env, default_model = self.PROVIDERS[provider_name]
        api_key = os.getenv(key_env)
        model   = os.getenv(model_env, default_model)

        if not api_key:
            raise ValueError(
                f"[AI BRAIN] '{key_env}' not found in .env. "
                f"Get a free key and add it to your .env file."
            )

        self._provider: BaseProvider = ProviderClass(api_key=api_key, model=model)

    def chat(self, user_input: str) -> str:
        return self._provider.chat(user_input)

    def reset_memory(self):
        self._provider.reset_memory()

    def describe_image(self, image_b64: str) -> str:
        return self._provider.describe_image(image_b64)