"""
╔══════════════════════════════════════════════════════════════╗
║     AI Brain v3.0  —  Cloud-Native Multi-Provider Brain      ║
║  Ported from local v2.1 — same strategy pattern, async-ready ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
from abc import ABC, abstractmethod
from config import settings

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
something you don't have access to, say so honestly and briefly.

4. FORMAT: Plain spoken English only. No bullet points, no markdown, no numbered lists. \
Write exactly how you would say it out loud.

5. UNDERSTANDING: If you genuinely did not understand the input, ask one short clarifying \
question. Don't guess and give a long wrong answer.

6. PERSONALITY: Be warm, a little witty, and efficient — like a real personal assistant \
who knows the user well.

7. HINDI: The user may occasionally say a Hindi word. Respond in English but acknowledge \
naturally.
"""

MAX_HISTORY = 30  # Keep last N messages to avoid token overflow


class BaseProvider(ABC):
    @abstractmethod
    def chat(self, user_input: str) -> str: ...

    @abstractmethod
    def reset_memory(self): ...

    def describe_image(self, image_b64: str) -> str:
        return "Visual analysis is not supported by this provider, Sir."


class GroqProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        from groq import Groq
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
                model=self.model, messages=self.history,
                max_tokens=200, temperature=0.7,
            )
            reply = response.choices[0].message.content.strip()
            self.history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            return f"Groq encountered an issue, Sir. {e}"

    def describe_image(self, image_b64: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    {"type": "text", "text": "You are J.A.R.V.I.S. Describe what you see concisely. Address the user as Sir. Plain English, under 3 sentences."}
                ]}], max_tokens=150,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Visual analysis failed, Sir. {e}"

    def reset_memory(self):
        self.history = self.history[:1]


class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        import google.generativeai as genai
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

    def reset_memory(self):
        self.chat_session = self.model_instance.start_chat(history=[])


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        from openai import OpenAI
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
                model=self.model, messages=self.history,
                max_tokens=200, temperature=0.7,
            )
            reply = response.choices[0].message.content.strip()
            self.history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            return f"OpenAI encountered an issue, Sir. {e}"

    def reset_memory(self):
        self.history = self.history[:1]


# ── Factory ──────────────────────────────────────────────────
PROVIDERS = {
    "groq":   (GroqProvider,   "GROQ_API_KEY",   "GROQ_MODEL",   "llama-3.3-70b-versatile"),
    "gemini": (GeminiProvider, "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-1.5-flash"),
    "openai": (OpenAIProvider, "OPENAI_API_KEY", "OPENAI_MODEL", "gpt-3.5-turbo"),
}


class AIBrain:
    def __init__(self):
        name = settings.AI_PROVIDER
        if name not in PROVIDERS:
            print(f"[AI BRAIN] Unknown provider '{name}'. Defaulting to groq.")
            name = "groq"
        Cls, key_env, model_env, default = PROVIDERS[name]
        api_key = os.getenv(key_env)
        model = os.getenv(model_env, default)
        if not api_key:
            raise ValueError(f"[AI BRAIN] '{key_env}' missing from .env")
        self._provider: BaseProvider = Cls(api_key=api_key, model=model)

    def chat(self, text: str) -> str:
        return self._provider.chat(text)

    def reset_memory(self):
        self._provider.reset_memory()

    def describe_image(self, image_b64: str) -> str:
        return self._provider.describe_image(image_b64)
