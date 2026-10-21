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
from ped_memory import PedMemoryManager

load_dotenv()

class LiveKitVoiceNPCAgent:
    """LiveKit-powered conversational voice agent for Red Dead Redemption 2.
    
    Orchestrates the full voice loop:
      - STT: Cartesia ink-whisper (ultra-fast ~0.15s transcription)
      - LLM: Google Gemini with Redis dialogue memory keyed by pedId
      - TTS: Cartesia Sonic-3 with consistent voice caching per pedId
    """
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.cartesia_key = os.getenv("CARTESIA_API_KEY", "").strip()
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
        
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

        # Initialize Redis Ped Memory & Voice Cache
        self.memory = PedMemoryManager()

        print("[LIVEKIT AGENT] Initialized LiveKit Voice Agent pipeline: Cartesia STT + Gemini LLM (Redis Memory) + Cartesia TTS (Cached Voice).")

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

    def build_system_instruction(self, context: dict, history_len: int = 0) -> tuple:
        """Constructs the period-accurate 1899 prompt from in-game telemetry and history awareness."""
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

        if history_len > 0:
            situation_notes.append(
                f"CONVERSATION CONTINUITY: You have exchanged dialogue with Arthur Morgan {history_len} time(s) moments ago. "
                "Maintain conversational continuity and remember what you previously discussed."
            )

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
        """Executes the LiveKit agent loop: Cartesia STT -> Gemini Reasoning (with Redis Memory) -> Cartesia TTS (Cached Voice)."""
        raw_ped_id = context.get("pedId")
        if raw_ped_id is None:
            raw_ped_id = context.get("ped_id") or context.get("id") or "default"
        ped_id = str(raw_ped_id)

        is_male = context.get("isMale", True)
        model_hash = context.get("model", 0)
        rel_group = context.get("relGroup", 0)
        occupation = get_ped_occupation(model_hash, rel_group)

        # 1. Fetch or cache consistent Cartesia Voice ID for this ped
        voice_id = self.memory.get_or_set_voice_id(
            ped_id=ped_id,
            is_male=is_male,
            occupation=occupation,
            voice_selector_fn=self.tts.select_voice
        )
        print(f"[PED MEMORY] Ped #{ped_id} bound to voice_id: {voice_id}")

        if not self.gemini_client:
            return {
                "transcription": "(API key missing)",
                "speaker": "Stranger",
                "text": "Don't just stare at me, mister! (Set GEMINI_API_KEY in AI/.env)",
                "ped_id": ped_id,
                "voice_id": voice_id
            }

        # 2. Step 1: Speech-to-Text via Cartesia STT (~0.15s)
        transcription = ""
        if text_input and text_input.strip():
            transcription = text_input.strip()
        elif audio_bytes and len(audio_bytes) > 2000:
            transcription = self.transcribe_audio(audio_bytes)

        if not transcription:
            transcription = "(Silence)" if (not audio_bytes or len(audio_bytes) <= 2000) else "(Silence / Inaudible)"

        # 3. Retrieve dialogue memory for this ped from Redis
        history = self.memory.get_history(ped_id, max_turns=6)
        instruction, occupation, zone_name = self.build_system_instruction(context, history_len=len(history))

        is_player_aiming = context.get("isPlayerAiming", False)
        is_hogtied = context.get("isHogtied", False)
        mode = context.get("mode", "greet")

        if transcription and transcription not in ["(Silence)", "(Silence / Inaudible)"]:
            current_user_prompt = f"Arthur Morgan says to you: \"{transcription}\". Respond in character in authentic 1899 dialect."
        else:
            if is_player_aiming:
                current_user_prompt = "Arthur Morgan is aiming his weapon directly at you without speaking. React to this immediate life threat!"
            elif is_hogtied:
                current_user_prompt = "Arthur Morgan stands over you while you are hogtied on the ground. React to being tied up!"
            elif mode == "antagonize":
                current_user_prompt = "Arthur Morgan glared at you and aggressively antagonized you without speaking. React naturally."
            else:
                current_user_prompt = "Arthur Morgan approaches you silently. React naturally to his presence."

        # Assemble multi-turn contents including Redis conversation history
        contents = []
        for past_turn in history:
            u_text = past_turn.get("user")
            a_text = past_turn.get("assistant")
            a_spk = past_turn.get("speaker") or occupation or "NPC"
            if u_text and a_text:
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=u_text)]
                ))
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=json.dumps({"speaker": a_spk, "text": a_text}))]
                ))

        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=current_user_prompt)]
        ))

        # 4. Step 2: LLM Dialogue Reasoning via Google Gemini (zero reasoning budget, with retry)
        try:
            config = types.GenerateContentConfig(
                system_instruction=instruction,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                max_output_tokens=70,
                temperature=0.8,
                top_p=0.9
            )

            response = None
            last_err = None
            for attempt in range(2):
                try:
                    response = self.gemini_client.models.generate_content(
                        model=self.model_name,
                        contents=contents,
                        config=config
                    )
                    break
                except Exception as ex:
                    last_err = ex
                    if attempt == 0:
                        time.sleep(0.5)

            if response is None:
                raise last_err or RuntimeError("No response from Gemini API")

            text_resp = response.text.strip()
            data = json.loads(text_resp)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]

            speaker = data.get("speaker")
            if not speaker or speaker in ["Stranger", "Local Resident", "Citizen", "Resident"] or (occupation and occupation not in speaker):
                speaker = occupation if occupation else (speaker or (f"{zone_name} Citizen" if zone_name else "Stranger"))

            text = data.get("text") or data.get("reply", "...")

            # 5. Persist interaction into Redis Ped Memory
            self.memory.add_turn(
                ped_id=ped_id,
                user_text=current_user_prompt,
                npc_speaker=speaker,
                npc_text=text
            )

            # 6. Step 3: Text-to-Speech via Cartesia Sonic TTS with consistent cached voice
            self.tts.speak(text, is_male=is_male, occupation=speaker, voice_id=voice_id, blocking=False)

            return {
                "transcription": transcription,
                "speaker": speaker,
                "text": text,
                "ped_id": ped_id,
                "voice_id": voice_id
            }

        except Exception as e:
            print(f"[LIVEKIT AGENT] Gemini model failed: {e}")
            fallback_text = "Howdy, mister! I ain't got much to say right now."
            # Record fallback turn in Redis memory so dialogue continuity remains intact
            self.memory.add_turn(
                ped_id=ped_id,
                user_text=current_user_prompt,
                npc_speaker=occupation or "Stranger",
                npc_text=fallback_text
            )
            self.tts.speak(fallback_text, is_male=is_male, occupation=occupation or "Stranger", voice_id=voice_id, blocking=False)
            return {
                "transcription": transcription or "(Speech processing error)",
                "speaker": occupation or "Stranger",
                "text": fallback_text,
                "ped_id": ped_id,
                "voice_id": voice_id
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
        cartesia_key = os.getenv("CARTESIA_API_KEY", "")
        gemini_key = os.getenv("GEMINI_API_KEY")
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

        stt = livekit_cartesia.STT(api_key=cartesia_key, model="ink-whisper")
        tts = livekit_cartesia.TTS(api_key=cartesia_key, model="sonic-3", voice="726d5ae5-055f-4c3d-8355-d9677de68937")
        llm = livekit_google.LLM(model=gemini_model, api_key=gemini_key)

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
