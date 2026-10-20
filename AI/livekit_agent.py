import os
import io
import json
import time
import random
from dotenv import load_dotenv

from cartesia import Cartesia
from google import genai
from google.genai import types

from zones import get_zone_name
from ped_models import get_ped_occupation
from tts_manager import TTSManager, CARTESIA_MALE_VOICES, CARTESIA_FEMALE_VOICES

load_dotenv()

class LiveKitVoiceNPCAgent:
    """LiveKit-powered conversational voice agent for Red Dead Redemption 2.
    
    Orchestrates the full voice loop:
      - STT: Cartesia ink-whisper (ultra-fast ~0.15s transcription)
      - LLM: Google Gemini (zero reasoning budget for sub-2s period dialogue)
      - TTS: Cartesia Sonic-3 (ultra-low latency frontier character speech)
    """
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.cartesia_key = os.getenv("CARTESIA_API_KEY", "sk_car_ecV7TQdX6AnxEwyYbpLvhk").strip()
        
        # Initialize Gemini LLM Client
        if not self.gemini_key:
            print("[LIVEKIT AGENT WARNING] GEMINI_API_KEY not found in .env!")
            self.gemini_client = None
        else:
            self.gemini_client = genai.Client(api_key=self.gemini_key)

        # Initialize Cartesia Client for STT
        if not self.cartesia_key:
            print("[LIVEKIT AGENT WARNING] CARTESIA_API_KEY not found in .env!")
            self.cartesia_client = None
        else:
            try:
                self.cartesia_client = Cartesia(api_key=self.cartesia_key)
                print("[LIVEKIT AGENT] Initialized Cartesia STT (ink-whisper).")
            except Exception as e:
                print(f"[LIVEKIT AGENT WARNING] Failed to initialize Cartesia STT: {e}")
                self.cartesia_client = None

        # Initialize Cartesia TTS Manager
        self.tts = TTSManager()
        print(f"[LIVEKIT AGENT] Initialized LiveKit Voice Agent pipeline: Cartesia STT + Gemini LLM (0-reasoning) + Cartesia TTS.")

    def transcribe_audio(self, audio_bytes: bytes) -> str:
        """Transcribes Arthur Morgan's audio bytes using Cartesia STT (ink-whisper)."""
        if not self.cartesia_client or not audio_bytes or len(audio_bytes) < 2000:
            return ""

        try:
            t0 = time.time()
            stt_resp = self.cartesia_client.stt.transcribe(
                file=("speech.wav", io.BytesIO(audio_bytes), "audio/wav"),
                model="ink-whisper",
                language="en"
            )
            t1 = time.time()
            transcript = getattr(stt_resp, "text", "") or ""
            transcript = transcript.strip()
            print(f"[CARTESIA STT] Transcribed in {t1 - t0:.2f}s: \"{transcript}\"")
            return transcript
        except Exception as e:
            print(f"[CARTESIA STT ERROR] Transcription failed: {e}")
            return ""

    def build_system_instruction(self, context: dict) -> tuple:
        """Constructs the period-accurate 1899 prompt from in-game telemetry."""
        zone_val = context.get("zone", 0)
        zone_name = zone_val if isinstance(zone_val, str) else get_zone_name(zone_val)

        is_male = context.get("isMale", True)
        gender = "male" if is_male else "female"
        hour = context.get("hour", 12)
        is_armed = context.get("isArmed", False)
        is_combat = context.get("isCombat", False)
        is_fleeing = context.get("isFleeing", False)
        health = context.get("health", 100)
        mode = context.get("mode", "greet")

        model_hash = context.get("model", 0)
        rel_group = context.get("relGroup", 0)
        occupation = get_ped_occupation(model_hash, rel_group)

        is_player_aiming = context.get("isPlayerAiming", False)
        is_hogtied = context.get("isHogtied", False)
        is_mounted = context.get("isMounted", False)
        in_vehicle = context.get("inVehicle", False)
        is_injured = context.get("isInjured", False)
        is_using_scenario = context.get("isUsingScenario", False)
        is_indoors = context.get("isIndoors", False)
        is_raining = context.get("isRaining", False)
        is_snowing = context.get("isSnowing", False)
        is_arthur_mounted = context.get("isArthurMounted", False)
        wanted_level = context.get("wantedLevel", 0)
        distance = round(context.get("distance", 2.0), 1)

        situation_notes = []
        if occupation:
            situation_notes.append(f"Your Identity / Profession: You are {occupation}. Set the 'speaker' JSON field to '{occupation}'.")
        if is_hogtied:
            situation_notes.append("CRITICAL: You are bound tightly with a lasso (HOGTIED) lying on the dirt/floor! You cannot move and are completely at Arthur's mercy.")
        elif is_injured:
            situation_notes.append("You are wounded and bleeding, in physical pain.")
        elif is_combat:
            situation_notes.append("You are in active combat/gunfight!")
        elif is_fleeing:
            situation_notes.append("You are terrified and running away for your life.")
        elif is_using_scenario:
            situation_notes.append("You were interrupted while doing daily chores/work.")

        if is_player_aiming:
            situation_notes.append("CRITICAL THREAT: Arthur Morgan has his gun drawn and pointed directly at your face right now!")
        elif wanted_level > 0:
            situation_notes.append(f"Arthur has the law actively hunting him (Wanted Level {wanted_level}).")

        if is_mounted:
            situation_notes.append("You are sitting on horseback.")
        elif in_vehicle:
            situation_notes.append("You are seated in a wagon/carriage.")

        if is_arthur_mounted:
            situation_notes.append("Arthur is mounted on horseback looking down at you.")

        if is_indoors:
            situation_notes.append("You are indoors (e.g. saloon, shop, bank).")
        else:
            if is_raining:
                situation_notes.append("It is pouring rain and muddy outside.")
            elif is_snowing:
                situation_notes.append("It is freezing and snowing heavily.")

        situation_str = "\n- ".join(situation_notes)
        if situation_str:
            situation_str = "- " + situation_str

        instruction = (
            "You are an authentic non-player character (NPC) in Red Dead Redemption 2, living in the year 1899.\n\n"
            "GROUND-TRUTH GAME STATE (Directly from game engine):\n"
            f"- Location: {zone_name} (Time: {hour}:00)\n"
            f"- Gender: {gender}\n"
            f"- Distance from Arthur: {distance} meters\n"
            f"- Armed: {is_armed}\n"
            f"- Health: {health}/100\n"
            f"- Player Action: Arthur approached you to speak directly.\n"
            f"{situation_str}\n\n"
            "INSTRUCTIONS:\n"
            "1. SITUATION AWARENESS: React directly to your immediate reality. If Arthur is aiming a gun at you, panic, freeze, or plead. If hogtied, demand or beg to be freed. If you are a specific occupation (bartender, deputy, miner, etc.), speak from that real identity.\n"
            "2. NO REPETITIVE CLICHÉS: Speak like a real human being living in 1899. Avoid generic movie lines.\n"
            "3. LENGTH: Exactly 1 short spoken sentence (under 20 words).\n"
            "4. OUTPUT FORMAT: Return STRICT JSON:\n"
            "   {\n"
            "     \"speaker\": \"Fitting NPC title (e.g. 'Valentine Bartender', 'Rhodes Deputy', 'Local Woman', 'Rancher')\",\n"
            "     \"text\": \"Your dialogue reply in authentic 1899 dialect.\"\n"
            "   }\n"
        )
        return instruction, occupation, zone_name

    def process_turn(self, context: dict, audio_bytes: bytes = None, text_input: str = None) -> dict:
        """Executes the LiveKit agent loop: Cartesia STT -> Gemini Reasoning (0-thinking) -> Cartesia TTS."""
        if not self.gemini_client:
            return {
                "transcription": "(API key missing)",
                "speaker": "Stranger",
                "text": "Don't just stare at me, mister! (Set GEMINI_API_KEY in AI/.env)"
            }

        # 1. Step 1: Speech-to-Text via Cartesia STT (~0.15s)
        transcription = ""
        if text_input and text_input.strip():
            transcription = text_input.strip()
        elif audio_bytes and len(audio_bytes) > 2000:
            transcription = self.transcribe_audio(audio_bytes)

        if not transcription:
            transcription = "(Silence)" if (not audio_bytes or len(audio_bytes) <= 2000) else "(Silence / Inaudible)"

        # 2. Step 2: LLM Dialogue Reasoning via Google Gemini (zero reasoning budget)
        instruction, occupation, zone_name = self.build_system_instruction(context)
        is_male = context.get("isMale", True)
        is_player_aiming = context.get("isPlayerAiming", False)
        is_hogtied = context.get("isHogtied", False)
        mode = context.get("mode", "greet")

        contents = []
        if transcription and transcription not in ["(Silence)", "(Silence / Inaudible)"]:
            contents.append(f"Arthur Morgan says to you: \"{transcription}\". Respond in character in authentic 1899 dialect.")
        else:
            if is_player_aiming:
                contents.append("Arthur Morgan is aiming his weapon directly at you without speaking. React to this immediate life threat!")
            elif is_hogtied:
                contents.append("Arthur Morgan stands over you while you are hogtied on the ground. React to being tied up!")
            elif mode == "antagonize":
                contents.append("Arthur Morgan glared at you and aggressively antagonized you without speaking. React naturally.")
            else:
                contents.append("Arthur Morgan approaches you silently. React naturally to his presence.")

        last_error = None
        try:
            config = types.GenerateContentConfig(
                system_instruction=instruction,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                max_output_tokens=70,
                temperature=0.8,
                top_p=0.9
            )

            response = self.gemini_client.models.generate_content(
                model="gemini-3.5-flash",
                contents=contents,
                config=config
            )
            text_resp = response.text.strip()
            data = json.loads(text_resp)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]

            speaker = data.get("speaker")
            if not speaker or speaker in ["Stranger", "Local Resident", "Citizen", "Resident"] or (occupation and occupation not in speaker):
                speaker = occupation if occupation else (speaker or (f"{zone_name} Citizen" if zone_name else "Stranger"))

            text = data.get("text") or data.get("reply", "...")

            # 3. Step 3: Text-to-Speech via Cartesia Sonic TTS
            self.tts.speak(text, is_male=is_male, occupation=speaker, blocking=False)

            return {
                "transcription": transcription,
                "speaker": speaker,
                "text": text
            }

        except Exception as e:
            print(f"[LIVEKIT AGENT] Gemini model failed: {e}")
            fallback_text = "Howdy, mister! I ain't got much to say right now."
            self.tts.speak(fallback_text, is_male=is_male, occupation=occupation or "Stranger", blocking=False)
            return {
                "transcription": transcription or "(Speech processing error)",
                "speaker": occupation or "Stranger",
                "text": fallback_text
            }

# --- Standalone LiveKit Agents CLI Runner ---
try:
    from livekit.agents import AgentServer, AgentSession, Agent, JobContext
    from livekit.plugins import cartesia as livekit_cartesia, google as livekit_google

    server = AgentServer(
        ws_url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET")
    )

    @server.rtc_session()
    async def entrypoint(ctx: JobContext):
        cartesia_key = os.getenv("CARTESIA_API_KEY", "sk_car_ecV7TQdX6AnxEwyYbpLvhk")
        gemini_key = os.getenv("GEMINI_API_KEY")

        stt = livekit_cartesia.STT(api_key=cartesia_key, model="ink-whisper")
        tts = livekit_cartesia.TTS(api_key=cartesia_key, model="sonic-3", voice="726d5ae5-055f-4c3d-8355-d9677de68937")
        llm = livekit_google.LLM(model="gemini-3.5-flash", api_key=gemini_key)

        session = AgentSession(
            stt=stt,
            llm=llm,
            tts=tts
        )

        agent = Agent(
            instructions=(
                "You are an authentic 1899 non-player character in Red Dead Redemption 2. "
                "Keep responses under 20 words in authentic Western frontier dialect."
            )
        )

        await session.start(room=ctx.room, agent=agent)
        await session.generate_reply(instructions="Greet Arthur Morgan as he walks by.")

except Exception:
    server = None

if __name__ == "__main__":
    if server:
        server.run()
