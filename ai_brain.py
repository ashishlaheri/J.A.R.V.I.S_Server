"""Compatibility shim — redirects to core.ai_brain for backward compatibility."""
# Both jarvis.py (local) and any old imports will find AIBrain here.
# The actual implementation lives in core/ai_brain.py (single source of truth).

from core.ai_brain import AIBrain, BaseProvider, JARVIS_SYSTEM_PROMPT

__all__ = ["AIBrain", "BaseProvider", "JARVIS_SYSTEM_PROMPT"]