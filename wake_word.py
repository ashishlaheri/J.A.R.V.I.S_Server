"""
╔══════════════════════════════════════════════════════════════╗
║          wake_word.py  —  Free Wake Word Detection           ║
║          Using openwakeword (no API key, runs locally)        ║
╚══════════════════════════════════════════════════════════════╝

WHY openwakeword INSTEAD OF pvporcupine?
─────────────────────────────────────────
  pvporcupine:
    ✗ Requires a Picovoice account + access key
    ✗ Free tier has device restrictions
    ✗ Closed-source model

  openwakeword:
    ✓ Completely free, no account, no key, no limits
    ✓ Open-source (Apache 2.0)
    ✓ Runs locally — no internet connection needed
    ✓ Pre-trained models for "hey jarvis", "alexa", etc.

INSTALL
────────
  pip install openwakeword pyaudio

  On first run it downloads the model files (~50MB) automatically.
  After that it works offline forever.

FALLBACK
─────────
  If PyAudio or openwakeword is unavailable, this module falls back
  to a keyboard-activated mode (press Enter to activate Jarvis).
"""

import time
import sys

# ════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ════════════════════════════════════════════════════════════════
WAKE_WORD_MODEL     = "hey_jarvis"       # pre-trained model name
DETECTION_THRESHOLD = 0.5                # 0.0–1.0, higher = fewer false positives
CHUNK_SIZE          = 1280               # audio frames per chunk (must be 1280 for oww)
SAMPLE_RATE         = 16000              # Hz — required by openwakeword
CHANNELS            = 1                  # mono audio


# ════════════════════════════════════════════════════════════════
#  KEYBOARD FALLBACK DETECTOR
# ════════════════════════════════════════════════════════════════
class KeyboardWakeDetector:
    """Fallback wake word detector that uses keyboard input.
    Used when PyAudio or openwakeword is not available."""

    def __init__(self, on_wake: callable, threshold: float = 0.5):
        self.on_wake = on_wake
        self._running = False
        print("[WAKE WORD] ⌨️  Using KEYBOARD fallback mode")
        print("[WAKE WORD] Press ENTER to activate Jarvis (no microphone detected)")

    def start(self):
        self._running = True
        print("\n" + "=" * 55)
        print("  J.A.R.V.I.S. — Keyboard Mode")
        print("  Press ENTER to talk to Jarvis")
        print("  Type 'quit' to exit")
        print("=" * 55 + "\n")

        try:
            while self._running:
                user_input = input("[Press ENTER to activate Jarvis] ")
                if user_input.lower().strip() in ("quit", "exit", "q"):
                    print("[JARVIS] Shutting down.")
                    sys.exit(0)
                self.on_wake()
        except KeyboardInterrupt:
            print("\n[WAKE WORD] Stopping.")
        except EOFError:
            print("\n[WAKE WORD] Input stream closed.")

    def stop(self):
        self._running = False


# ════════════════════════════════════════════════════════════════
#  MICROPHONE WAKE WORD DETECTOR
# ════════════════════════════════════════════════════════════════
class WakeWordDetector:
    """
    Listens passively for "Hey Jarvis" using openwakeword.
    When the wake word is heard, it calls the provided callback function.

    Falls back to KeyboardWakeDetector if dependencies are missing.

    Usage:
        detector = WakeWordDetector(on_wake=my_callback)
        detector.start()   ← blocks forever, call in a thread if needed
    """

    def __new__(cls, on_wake: callable, threshold: float = DETECTION_THRESHOLD):
        """Check dependencies before creating instance. Fall back to keyboard if needed."""
        try:
            import pyaudio
            import numpy as np
            from openwakeword.model import Model
            # Dependencies available — create normal instance
            instance = super().__new__(cls)
            instance._deps_available = True
            return instance
        except ImportError as e:
            missing = str(e)
            print(f"\n[WAKE WORD] ⚠️  Missing dependency: {missing}")
            if "pyaudio" in missing.lower():
                print("[WAKE WORD] Install PyAudio:")
                print("  Windows: pip install pyaudio")
                print("  Linux:   sudo apt install portaudio19-dev && pip install pyaudio")
                print("  Mac:     brew install portaudio && pip install pyaudio")
            elif "openwakeword" in missing.lower():
                print("[WAKE WORD] Install openwakeword: pip install openwakeword")
            print("[WAKE WORD] Falling back to keyboard activation...\n")
            return KeyboardWakeDetector(on_wake=on_wake, threshold=threshold)

    def __init__(self, on_wake: callable, threshold: float = DETECTION_THRESHOLD):
        if not getattr(self, '_deps_available', False):
            return  # Already initialized as KeyboardWakeDetector

        import numpy as np
        from openwakeword.model import Model

        self.on_wake = on_wake
        self.threshold = threshold
        self._running = False

        print("[WAKE WORD] Loading model... (downloads ~50MB on first run)")
        try:
            self.model = Model(
                wakeword_models=[WAKE_WORD_MODEL],
                inference_framework="onnx"
            )
            print(f"[WAKE WORD] ✅ Model ready. Listening for '{WAKE_WORD_MODEL}'")
        except Exception as e:
            print(f"[WAKE WORD] ⚠️  Model loading failed: {e}")
            print("[WAKE WORD] Falling back to keyboard activation...")
            # Transform into keyboard detector
            self.__class__ = KeyboardWakeDetector
            self.__init__(on_wake=on_wake, threshold=threshold)

    def start(self):
        """Start the passive listening loop. This method BLOCKS."""
        import pyaudio
        import numpy as np

        try:
            pa = pyaudio.PyAudio()
            stream = pa.open(
                rate=SAMPLE_RATE,
                channels=CHANNELS,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
        except Exception as e:
            print(f"[WAKE WORD] ⚠️  Microphone error: {e}")
            print("[WAKE WORD] Common fixes:")
            print("  - Check if your microphone is connected")
            print("  - Allow microphone access in Windows Privacy Settings")
            print("  - Try a different audio input device")
            print("[WAKE WORD] Falling back to keyboard activation...\n")
            fallback = KeyboardWakeDetector(on_wake=self.on_wake)
            fallback.start()
            return

        self._running = True
        print("[WAKE WORD] 🎤 Passively listening... say 'Hey Jarvis' to activate.")

        try:
            while self._running:
                raw_audio = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                audio_array = np.frombuffer(raw_audio, dtype=np.int16)
                predictions = self.model.predict(audio_array)
                score = predictions.get(WAKE_WORD_MODEL, 0)

                if score >= self.threshold:
                    print(f"[WAKE WORD] ✅ Detected! confidence={score:.2f}")
                    self.on_wake()
                    # Brief cooldown to prevent double-firing
                    time.sleep(1.5)
                    self.model.reset()

        except KeyboardInterrupt:
            print("\n[WAKE WORD] Stopping.")
        except Exception as e:
            print(f"[WAKE WORD] Error in listen loop: {e}")
        finally:
            self._running = False
            stream.stop_stream()
            stream.close()
            pa.terminate()

    def stop(self):
        self._running = False


# ════════════════════════════════════════════════════════════════
#  QUICK TEST — run this file directly to test your microphone
#  python wake_word.py
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    def test_callback():
        print("\n✅  WAKE WORD DETECTED — Jarvis would now listen for your command!\n")

    print("=" * 55)
    print("  Wake Word Test — say 'Hey Jarvis' into your mic")
    print("  Press Ctrl+C to stop")
    print("=" * 55)

    detector = WakeWordDetector(on_wake=test_callback, threshold=0.5)
    detector.start()