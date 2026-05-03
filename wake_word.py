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
    ✓ You can train your own custom wake word for free

INSTALL
────────
  pip install openwakeword pyaudio

  On first run it downloads the model files (~50MB) automatically.
  After that it works offline forever.

AVAILABLE PRE-TRAINED MODELS
──────────────────────────────
  "hey_jarvis"       ← we use this one
  "alexa"
  "hey_mycroft"
  "hey_rhasspy"
  Full list: https://github.com/dscripka/openWakeWord#pre-trained-models
"""

import pyaudio
import numpy as np
import time
from openwakeword.model import Model


# ════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ════════════════════════════════════════════════════════════════
WAKE_WORD_MODEL   = "hey_jarvis"       # pre-trained model name
DETECTION_THRESHOLD = 0.5             # 0.0–1.0, higher = fewer false positives
CHUNK_SIZE        = 1280              # audio frames per chunk (must be 1280 for oww)
SAMPLE_RATE       = 16000             # Hz — required by openwakeword
CHANNELS          = 1                 # mono audio


# ════════════════════════════════════════════════════════════════
#  WAKE WORD DETECTOR
# ════════════════════════════════════════════════════════════════
class WakeWordDetector:
    """
    Listens passively for "Hey Jarvis" using openwakeword.
    When the wake word is heard, it calls the provided callback function.

    Usage:
        detector = WakeWordDetector(on_wake=my_callback)
        detector.start()   ← blocks forever, call in a thread if needed
    """

    def __init__(self, on_wake: callable, threshold: float = DETECTION_THRESHOLD):
        """
        Args:
            on_wake:    Function to call when wake word is detected.
                        Receives no arguments.
            threshold:  Confidence score needed to trigger. Start at 0.5,
                        increase if you get false positives.
        """
        self.on_wake = on_wake
        self.threshold = threshold
        self._running = False

        print("[WAKE WORD] Loading model... (downloads ~50MB on first run)")
        # openwakeword auto-downloads model files to ~/.cache/openwakeword/
        self.model = Model(
            wakeword_models=[WAKE_WORD_MODEL],
            inference_framework="onnx"      # onnx is faster than tflite on most PCs
        )
        print(f"[WAKE WORD] Model ready. Listening for '{WAKE_WORD_MODEL}'")

    def start(self):
        """
        Start the passive listening loop. This method BLOCKS — run it in
        the main thread or use start_in_thread() for background mode.
        """
        pa = pyaudio.PyAudio()
        stream = pa.open(
            rate=SAMPLE_RATE,
            channels=CHANNELS,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )

        self._running = True
        print("[WAKE WORD] Passively listening... say 'Hey Jarvis' to activate.")

        try:
            while self._running:
                # Read raw audio chunk
                raw_audio = stream.read(CHUNK_SIZE, exception_on_overflow=False)

                # Convert bytes → numpy int16 array (required by openwakeword)
                audio_array = np.frombuffer(raw_audio, dtype=np.int16)

                # Run the model on this chunk
                predictions = self.model.predict(audio_array)

                # Check if our model's score exceeds the threshold
                score = predictions.get(WAKE_WORD_MODEL, 0)
                if score >= self.threshold:
                    print(f"[WAKE WORD] Detected! confidence={score:.2f}")
                    self.on_wake()
                    # Brief cooldown to prevent double-firing
                    time.sleep(1.5)
                    # Reset model state after detection
                    self.model.reset()

        except KeyboardInterrupt:
            print("[WAKE WORD] Stopping.")
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