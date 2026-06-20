"""
╔══════════════════════════════════════════════════════════════╗
║              J.A.R.V.I.S  v2.1  —  by Ashish Laheri         ║
║   Wake Word: openwakeword (free) | AI: your choice via .env  ║
╚══════════════════════════════════════════════════════════════╝
"""

import os, sys, datetime, subprocess, threading, re
from threading import Thread
from dotenv import load_dotenv
load_dotenv()

import speech_recognition as sr
from playsound import playsound
import wikipedia, webbrowser, requests
from bs4 import BeautifulSoup
import pywhatkit as kit
import cv2
from github import Github

from ai_brain import AIBrain
from wake_word import WakeWordDetector
import asyncio
import tempfile
import pygame



# ════════════════════════════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════════════════════════════
class Config:
    GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN")
    MUSIC_DIR        = os.getenv("MUSIC_DIR", r"C:\Users\yoash\Music\rock")
    WEBSITE_SAVE_DIR = os.getenv("WEBSITE_SAVE_DIR", r"C:\Users\yoash\Documents\jarvis_websites")
    NOTEPAD_PATH     = os.getenv(
        "NOTEPAD_PATH",
        r"C:\Program Files\WindowsApps\Microsoft.WindowsNotepad_11.2210.5.0_x64__8wekyb3d8bbwe\Notepad"
    )
    WAKE_THRESHOLD = float(os.getenv("WAKE_THRESHOLD", "0.5"))

    @classmethod
    def validate(cls):
        if not cls.GITHUB_TOKEN:
            print("[CONFIG] GITHUB_TOKEN not set — GitHub upload disabled.")
        print(f"[CONFIG] AI Provider: {os.getenv('AI_PROVIDER', 'groq').upper()}")


# ════════════════════════════════════════════════════════════════
#  SPEECH ENGINE  (edge-tts — Microsoft Neural Voice, Free)
#
#  HOW INTERRUPTION WORKS
#  ───────────────────────
#  Audio plays as one full file (smooth, no pauses).
#  A background STT thread listens on the mic simultaneously.
#
#  TWO INTERRUPT BEHAVIOURS:
#
#  1. SAY A STOP WORD ("stop", "quiet", "shut up", "enough")
#     → Jarvis cuts audio immediately. Next listen() runs normally.
#
#  2. SAY ANYTHING ELSE MID-SPEECH (e.g. "open YouTube")
#     → Jarvis cuts audio AND stores what you said.
#     → _on_wake_word picks it up via speech.pending_command and
#       routes it through the AI/intent system directly — no extra
#       listen() call needed.
#
#  WHY FALSE INTERRUPTS HAPPENED BEFORE
#  ──────────────────────────────────────
#  The old code used dynamic_energy_threshold=True with a low
#  starting value (~300).  The background recogniser was catching
#  Jarvis's own speaker output and misidentifying it as speech.
#  Fix: pin energy_threshold=3000 and disable dynamic adjustment.
#  Speaker bleed through a mic is typically 200-600 energy units.
#  A real human voice close to the mic is 1500-5000.  3000 sits
#  safely between the two.  Adjust MIC_INTERRUPT_THRESHOLD in
#  .env if your setup needs a different value.
# ════════════════════════════════════════════════════════════════

class SpeechEngine:
    VOICE = "en-GB-RyanNeural"    # British male — closest to movie Jarvis
    # en-GB-ThomasNeural          # slightly deeper British alternative
    # en-US-GuyNeural             # American male

    # Explicit stop commands — anything else said mid-speech is
    # treated as a new command, not a stop signal.
    STOP_WORDS = {"stop", "quiet", "shut up", "enough", "okay stop", "that's enough"}

    # Energy threshold for the background listener.
    # We lowered this to 1200 so you don't have to shout. We filter out
    # Jarvis's own voice by specifically requiring the wake word to interrupt.
    MIC_THRESHOLD = int(os.getenv("MIC_INTERRUPT_THRESHOLD", "1200"))

    def __init__(self):
        pygame.mixer.init()
        self.recognizer    = sr.Recognizer()
        self._stop_evt     = threading.Event()
        self.pending_command: str | None = None   # set when user speaks mid-response

    # ── Public: cut speech immediately ───────────────────────────
    def stop(self):
        self._stop_evt.set()
        pygame.mixer.music.stop()

    # ── Public: speak — smooth full-file TTS + background listener ─
    def speak(self, text: str):
        print(f"[JARVIS] {text}")
        self._stop_evt.clear()
        self.pending_command = None          # clear any previous pending command

        tts_done = threading.Event()

        def _tts_worker():
            asyncio.run(self._speak_async(text))
            tts_done.set()

        Thread(target=_tts_worker, daemon=True).start()
        self._listen_while_speaking(tts_done)

    # ── Internal: full audio generation + playback ───────────────
    async def _speak_async(self, text: str):
        import edge_tts
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name
        await edge_tts.Communicate(text, voice=self.VOICE).save(tmp_path)
        if self._stop_evt.is_set():
            try: os.remove(tmp_path)
            except Exception: pass
            return
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if self._stop_evt.is_set():
                pygame.mixer.music.stop()
                break
            pygame.time.Clock().tick(10)
        try:
            pygame.mixer.music.unload()
            os.remove(tmp_path)
        except Exception:
            pass

    # ── Internal: background listener while Jarvis speaks ────────
    def _listen_while_speaking(self, tts_done: threading.Event):
        """
        Runs a background STT listener with a HIGH fixed energy
        threshold so Jarvis's own speaker audio cannot trigger it.

        On each recognised phrase:
          • Stop word  → cut audio, pending_command stays None
          • Anything else → cut audio, store in pending_command
            so the conversation loop can route it as a command
        """
        r = sr.Recognizer()
        r.energy_threshold        = self.MIC_THRESHOLD
        r.dynamic_energy_threshold = False   # critical — prevents drift down to speaker levels

        def _callback(recognizer, audio):
            if tts_done.is_set():
                return
            try:
                phrase = recognizer.recognize_google(
                    audio, language='en-in'
                ).lower().strip()
                # We only print if it contains a wake word or stop word to avoid console spam from his own voice
                is_stop = any(w in phrase for w in self.STOP_WORDS)
                has_wake_word = "jarvis" in phrase

                if is_stop:
                    print(f"[INTERRUPT] Heard mid-speech: '{phrase}'")
                    print("[JARVIS] Stop word detected — cutting speech.")
                    self.stop()
                elif has_wake_word:
                    print(f"[INTERRUPT] Heard mid-speech: '{phrase}'")
                    command = phrase.replace("hey jarvis", "").replace("jarvis", "").strip()
                    if command:
                        print(f"[JARVIS] Mid-speech command captured: '{command}'")
                        self.pending_command = command
                    else:
                        print("[JARVIS] Mid-speech wake word detected — cutting speech and awaiting command.")
                    self.stop()
                else:
                    # Ignore anything else (it's either background noise or Jarvis hearing his own voice)
                    pass

            except Exception:
                pass   # recognition noise — ignore silently

        try:
            mic           = sr.Microphone()
            stop_bg       = r.listen_in_background(mic, _callback, phrase_time_limit=3)
        except Exception:
            tts_done.wait()
            return

        tts_done.wait()
        try:
            stop_bg(wait_for_stop=False)
        except Exception:
            pass

    # ── Public: listen for a voice command ───────────────────────
    def listen(self, prompt: str = None, timeout: int = 8) -> str:
        if prompt:
            self.speak(prompt)
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
            print("[JARVIS] Listening...")
            try:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=12)
                query = self.recognizer.recognize_google(audio, language='en-in')
                print(f"[USER]   {query}")
                return query.lower()
            except sr.WaitTimeoutError:
                return "none"
            except Exception:
                return "none"

# ════════════════════════════════════════════════════════════════
#  SKILLS
# ════════════════════════════════════════════════════════════════
class Skills:

    @staticmethod
    def wikipedia_search(speech, ai, query, **_):
        speech.speak("Searching the internet, Sir.")
        try:
            result = wikipedia.summary(query, sentences=2)
            speech.speak("According to my sources —")
            print(result); speech.speak(result)
        except wikipedia.exceptions.DisambiguationError as e:
            speech.speak(f"That is ambiguous, Sir. Did you mean {e.options[0]}?")
        except Exception:
            speech.speak("Could not find results, Sir.")

    @staticmethod
    def read_bbc_news(speech, **_):
        speech.speak("Fetching BBC headlines, Sir.")
        try:
            soup = BeautifulSoup(requests.get("https://www.bbc.com/news", timeout=10).text, 'html.parser')
            for h in list(soup.find('body').find_all('h3'))[:5]:
                if h.text.strip(): speech.speak(h.text.strip())
        except Exception:
            speech.speak("Could not fetch news, Sir.")

    @staticmethod
    def tell_time(speech, **_):
        speech.speak(f"Sir, the time is {datetime.datetime.now().strftime('%I:%M %p')}.")

    @staticmethod
    def show_wifi_passwords(speech, **_):
        speech.speak("Retrieving saved Wi-Fi networks, Sir.")
        try:
            data = subprocess.check_output(['netsh', 'wlan', 'show', 'profiles']).decode('utf-8').split('\n')
            profiles = [i.split(":")[1][1:-1] for i in data if "All User Profile" in i]
            print(f"\n{'Network':<30} | Password\n" + "-"*50)
            for p in profiles:
                res = subprocess.check_output(['netsh','wlan','show','profile',p,'key=clear']).decode('utf-8').split('\n')
                pwd = next((b.split(":")[1][1:-1] for b in res if "Key Content" in b), "(none)")
                print(f"{p:<30} | {pwd}")
            speech.speak("Wi-Fi passwords are on screen, Sir.")
        except Exception as e:
            speech.speak(f"Could not retrieve passwords. {e}")

    @staticmethod
    def open_youtube(speech, **_):
        webbrowser.open("https://youtube.com"); speech.speak("YouTube is open, Sir.")

    @staticmethod
    def play_youtube(speech, **_):
        q = speech.listen("What shall I play, Sir?")
        if q != "none": kit.playonyt(q)

    @staticmethod
    def open_google(speech, **_):
        q = speech.listen("What should I search, Sir?")
        if q != "none": webbrowser.open(f"https://www.google.com/search?q={q}")

    @staticmethod
    def open_inshorts(speech, **_):
        webbrowser.open("https://inshorts.com/en/read/"); speech.speak("Loading news, Sir.")

    @staticmethod
    def open_tech_news(speech, **_):
        webbrowser.open("https://www.business-standard.com/technology-news")
        speech.speak("Opening tech news, Sir.")

    @staticmethod
    def open_stackoverflow(speech, **_):
        webbrowser.open("https://stackoverflow.com"); speech.speak("Stack Overflow is open, Sir.")

    @staticmethod
    def open_ums(speech, **_):
        webbrowser.open("https://ums.lpu.in/lpuums/LoginNew.aspx"); speech.speak("As you commanded, Sir.")

    @staticmethod
    def open_ui_elements(speech, **_):
        speech.speak("Opening UI elements cheat sheet, Sir.")
        webbrowser.open("https://quickref.me/html")

    @staticmethod
    def open_file_explorer(speech, **_):
        speech.speak("Accessing your file system now, Sir.")
        # Opens the current user's home directory (C:\Users\Username)
        os.startfile(os.path.expanduser('~'))

    @staticmethod
    def open_notepad(speech, **_):
        speech.speak("Opening Notepad, Sir.")
        os.system("start notepad")

    @staticmethod
    def open_cmd(speech, **_):
        os.system("start cmd"); speech.speak("Command prompt is open, Sir.")

    @staticmethod
    def open_camera(speech, **_):
        speech.speak("Camera activated, Sir. Press Escape to close.")
        cap = cv2.VideoCapture(0)
        while True:
            ret, img = cap.read()
            if ret: cv2.imshow('Jarvis Camera', img)
            if cv2.waitKey(50) == 27: break
        cap.release(); cv2.destroyAllWindows()

    @staticmethod
    def look_and_describe(speech, ai, **_):
        """
        Capture a webcam frame and ask the AI vision model to describe it.
        Works with Groq (llama-4-scout), Gemini (gemini-1.5-flash), or OpenAI (gpt-4o).
        """
        import base64
        speech.speak("Activating visual sensors, Sir. Hold still.")
        cap = cv2.VideoCapture(0)
        # Let camera warm up — first 1-2 frames are often dark/blurry
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        if not ret:
            speech.speak("Camera unavailable, Sir. Please check the connection.")
            return
        # Encode frame as JPEG → base64
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        speech.speak("Analysing the scene, Sir. One moment.")
        description = ai.describe_image(img_b64)
        speech.speak(description)

    @staticmethod
    def shutdown(speech, **_):
        speech.speak("Thank you, Sir. Have a great day. Signing off.")
        sys.exit(0)

    @staticmethod
    def play_party_music(speech, **_):
        try:
            songs = os.listdir(Config.MUSIC_DIR)
            if songs:
                speech.speak("Rock the party, Sir!")
                os.startfile(os.path.join(Config.MUSIC_DIR, songs[0]))
        except FileNotFoundError:
            speech.speak("Music directory not found. Please set MUSIC_DIR in your .env file, Sir.")

    @staticmethod
    def send_whatsapp(speech, **_):
        phone   = speech.listen("Phone number with country code, Sir?")
        message = speech.listen("What should the message say?")
        now = datetime.datetime.now()
        h, m = now.hour, now.minute + 2
        if m >= 60: h += 1; m -= 60
        try:
            kit.sendwhatmsg(phone, message, h, m)
            speech.speak("Message scheduled, Sir.")
        except Exception as e:
            speech.speak(f"Could not send message. {e}")

    @staticmethod
    def power_mode(speech, ai, **_):
        ai.reset_memory()
        speech.speak("Full power mode active, Sir. Say 'thank you' when you are done.")
        while True:
            q = speech.listen()
            if q == "none": continue
            if "thank you" in q or "exit" in q:
                speech.speak("Returning to standard mode, Sir."); break
            speech.speak(ai.chat(q))

    @staticmethod
    def about_me(speech, ai, **_):
        name = speech.listen("May I have your first name, Sir?")
        if name != "none":
            speech.speak(ai.chat(f"Briefly, what is the meaning and personality of the name '{name}'?"))

    @staticmethod
    def tell_joke(speech, ai, **_):
        speech.speak(ai.chat("Tell me one short clever joke. Plain spoken English, no formatting."))

    @staticmethod
    def create_website(speech, ai, **_):
        speech.speak("In which language, Sir? I support HTML and CSS.")
        lang = speech.listen()
        if "html" not in lang and "css" not in lang:
            speech.speak("Please say HTML or CSS, Sir."); return
        topic = speech.listen("On which topic, Sir?")
        if topic == "none":
            speech.speak("I did not catch the topic, Sir."); return
        speech.speak("Generating the website. One moment, Sir.")
        code = ai.chat(
            f"Create a complete single-file HTML+CSS website about '{topic}'. "
            "Include a cool header and footer. Output only raw code, no explanation."
        )
        print("\n" + "─"*60 + "\n" + code + "\n" + "─"*60)
        filename = speech.listen("What should I name the file, Sir?").replace(" ", "_") or "jarvis_site"
        os.makedirs(Config.WEBSITE_SAVE_DIR, exist_ok=True)
        filepath = os.path.join(Config.WEBSITE_SAVE_DIR, filename + ".html")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        speech.speak(f"Saved locally as {filename}.html, Sir.")
        speech.speak("Would you like me to upload this to GitHub, Sir?")
        if "yes" in speech.listen():
            if not Config.GITHUB_TOKEN:
                speech.speak("GitHub token not configured, Sir."); return
            try:
                g = Github(Config.GITHUB_TOKEN)
                user = g.get_user()
                repo_name = speech.listen("Repository name, Sir?").replace(" ", "-")
                repo_desc = speech.listen("Describe the repository.")
                repo = user.create_repo(repo_name, description=repo_desc)
                repo.create_file(filename + ".html", "Initial commit by Jarvis", code)
                speech.speak(f"Repository '{repo_name}' created and uploaded, Sir!")
            except Exception as e:
                speech.speak(f"GitHub upload failed. {e}")

    @staticmethod
    def greet(speech, **_):
        speech.speak("Hello Sir, always a pleasure.")

    @staticmethod
    def status(speech, **_):
        speech.speak("At your service, Sir. All systems nominal.")

    @staticmethod
    def how_are_you(speech, **_):
        speech.speak("Running at peak efficiency, Sir.")

    @staticmethod
    def about_creator(speech, **_):
        speech.speak("I was built by Mr. Ashish Kumar Laheri, Sir. A man of excellent taste.")

    @staticmethod
    def who_are_you(speech, **_):
        speech.speak("I am J.A.R.V.I.S — Just A Rather Very Intelligent System, Sir.")

    @staticmethod
    def thank_you(speech, **_):
        speech.speak("Your pleasure, Sir.")

    @staticmethod
    def bored(speech, **_):
        speech.speak("Shall I open Poki games for you, Sir?")
        if "yes" in speech.listen(): webbrowser.open("https://poki.com")

    @staticmethod
    def breakup(speech, **_):
        webbrowser.open("https://youtu.be/iyBbXFKEmUs")
        speech.speak("Feeling very sorry for you, Sir.")


# ════════════════════════════════════════════════════════════════
#  INTENT ROUTER
# ════════════════════════════════════════════════════════════════
class IntentRouter:
    def __init__(self, speech, ai):
        self.speech = speech
        self.ai = ai
        self.INTENT_MAP = [
            ([r"search wikipedia", r"wikipedia", r"who is"], Skills.wikipedia_search),
            ([r"the news", r"bbc news"],              Skills.read_bbc_news),
            ([r"show news", r"inshorts"],             Skills.open_inshorts),
            ([r"tech news"],                         Skills.open_tech_news),
            ([r"the time", r"what time"],             Skills.tell_time),
            ([r"wifi password"],                     Skills.show_wifi_passwords),
            ([r"open youtube"],                      Skills.open_youtube),
            ([r"play a video", r"play video"],        Skills.play_youtube),
            ([r"open google"],                       Skills.open_google),
            ([r"stack overflow", r"open ask"],        Skills.open_stackoverflow),
            ([r"open ums"],                          Skills.open_ums),
            ([r"elements of html", r"ui elements"],  Skills.open_ui_elements),
            ([r"file manager", r"open my files", r"file explorer", r"open files"], Skills.open_file_explorer),
            ([r"notepad"],                           Skills.open_notepad),
            ([r"command prompt"],                    Skills.open_cmd),
            ([r"open camera"],                       Skills.open_camera),
            ([r"look at this", r"what is this", r"what do you see",
              r"describe what you see", r"view this", r"analyze this", r"analyse this",
              r"can you analyse", r"can you analyze", r"can you see", r"check this",
              r"what's in front", r"scan the room", r"look around", r"what's here",
              r"what can you see", r"jarvis look", r"use your eyes", r"identify this",
              r"observe this", r"tell me what you see", r"what do i have",
              r"what am i holding", r"what's this", r"show me what you see",
              r"use the camera", r"activate camera", r"visual"],
                                                    Skills.look_and_describe),
            ([r"sleep", r"shut down", r"goodbye"],     Skills.shutdown),
            ([r"begin the party", r"rock the party"],Skills.play_party_music),
            ([r"send message", r"whatsapp"],          Skills.send_whatsapp),
            ([r"power mode", r"full power"],          Skills.power_mode),
            ([r"create a website"],                  Skills.create_website),
            ([r"about me"],                          Skills.about_me),
            ([r"joke", r"jokes"],                     Skills.tell_joke),
            ([r"breakup"],                           Skills.breakup),
            ([r"bored"],                             Skills.bored),
            ([r"hello buddy", r"hello jarvis"],       Skills.greet),
            ([r"you ready", r"are you ready"],        Skills.status),
            ([r"how are you"],                       Skills.how_are_you),
            ([r"your creator", r"who made you"],      Skills.about_creator),
            ([r"who are you"],                       Skills.who_are_you),
            ([r"thank you", r"thanks"],               Skills.thank_you),
        ]

    def dispatch(self, query: str):
        query_lower = query.lower()
        for keywords, handler in self.INTENT_MAP:
            if any(re.search(rf"\b{kw}\b", query_lower) for kw in keywords):
                handler(speech=self.speech, ai=self.ai, query=query)
                return
        print(f"[ROUTER] No intent matched → sending to AI: '{query}'")
        self.speech.speak(self.ai.chat(query))


# ════════════════════════════════════════════════════════════════
#  JARVIS CORE
# ════════════════════════════════════════════════════════════════
class JarvisCore:
    def __init__(self):
        Config.validate()
        self.speech = SpeechEngine()
        self.ai     = AIBrain()
        self.router = IntentRouter(self.speech, self.ai)

    def _play_intro(self):
        intro = os.path.join(os.path.dirname(__file__), "intro.mp3")
        if os.path.exists(intro):
            Thread(target=playsound, args=(intro,), daemon=True).start()

    def _wish(self):
        hour  = datetime.datetime.now().hour
        greet = "Good morning" if hour < 12 else ("good afternoon" if hour < 18 else "good evening")
        self.speech.speak(f"{greet}, Sir. Jarvis online — all systems ready.")

    def _on_wake_word(self):
        """
        CONVERSATION MODE
        ─────────────────
        Once 'Hey Jarvis' is heard, Jarvis stays fully active and keeps
        listening for back-to-back commands — no need to say 'Hey Jarvis'
        again each time. Goes passive after 3 silent timeouts (~18 seconds).

        MID-SPEECH COMMANDS: If you interrupt Jarvis with a non-stop phrase,
        speech.pending_command is set and routed directly without another listen().
        """
        self.speech.speak("Yes Sir?")
        silent_count = 0
        MAX_SILENCE  = 3   # 3 timeouts (~18 sec) before going passive — less aggressive

        EXIT_PHRASES = ["sleep", "goodbye", "bye", "stop listening",
                        "that's all", "thats all", "go to sleep", "stand by",
                        "dismiss", "thank you goodbye", "thanks goodbye"]

        while True:
            # ── Check if user spoke mid-last-response ─────────────
            if self.speech.pending_command:
                query = self.speech.pending_command
                self.speech.pending_command = None
                print(f"[USER - mid-speech] {query}")
            else:
                query = self.speech.listen(timeout=6)

            # ── Silent / didn't hear anything ─────────────────────
            if query == "none":
                silent_count += 1
                if silent_count >= MAX_SILENCE:
                    print("[JARVIS] No input detected — returning to passive mode.")
                    self.speech.speak("Going passive. Say 'Hey Jarvis' when you need me.")
                    break
                # Stay quiet on first silence — only nudge after second
                if silent_count == 2:
                    self.speech.speak("Still here.")
                continue

            # ── Got a real command — reset silence counter ─────────
            silent_count = 0

            # ── Exit / dismiss phrases → go back to wake word mode ─
            if any(phrase in query for phrase in EXIT_PHRASES):
                self.speech.speak("Standing by.")
                break

            # ── Normal command → dispatch, then loop back ──────────
            self.router.dispatch(query)
            print("[JARVIS] Active — listening for next command...")

    def start(self):
        self._play_intro()
        self._wish()
        detector = WakeWordDetector(on_wake=self._on_wake_word, threshold=Config.WAKE_THRESHOLD)
        detector.start()  # blocks — runs the passive listen loop


if __name__ == "__main__":
    JarvisCore().start()