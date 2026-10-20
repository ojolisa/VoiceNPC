import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from zones import get_zone_name
from ped_models import get_ped_occupation

load_dotenv()

# Verified working model on API gateway
MODELS_TO_TRY = [
    "gemini-3.5-flash-lite"
]

class GeminiAgent:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("[WARNING] GEMINI_API_KEY not found in environment or .env file!")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)

    def generate_npc_reply(self, context: dict, audio_bytes: bytes = None, text_input: str = None) -> dict:
        """Processes Arthur's spoken audio or text and in-game context, returning STT transcription, speaker, and dialogue text."""
        if not self.client:
            return {
                "transcription": "(API key missing)",
                "speaker": "Stranger",
                "text": "Don't just stare at me, mister! (Set GEMINI_API_KEY in AI/.env)"
            }

        # Ground-truth game context directly from RDR2
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

        # Newly hooked engine parameters
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

        # Build dynamic factual state descriptions
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

        system_instruction = (
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
            "1. SPEECH-TO-TEXT (STT): Transcribe Arthur Morgan's exact words verbatim into the 'transcription' field. If audio is silent/empty, set 'transcription' to '(Silence)'.\n"
            "2. SITUATION AWARENESS: React directly to your immediate reality. If Arthur is aiming a gun at you, panic, freeze, or plead. If hogtied, demand or beg to be freed. If you are a specific occupation (bartender, deputy, miner, etc.), speak from that real identity.\n"
            "3. NO REPETITIVE CLICHÉS: Speak like a real human being living in 1899. Avoid generic movie lines like 'keep your hands where I can see em'.\n"
            "4. LENGTH: Keep it brief and authentic — exactly 1 or 2 spoken sentences (under 25 words).\n"
            "5. OUTPUT FORMAT: Return STRICT JSON:\n"
            "   {\n"
            "     \"transcription\": \"Verbatim words spoken by Arthur in the audio (or '(Silence)')\",\n"
            "     \"speaker\": \"Fitting NPC title (e.g. 'Valentine Bartender', 'Rhodes Deputy', 'Local Woman', 'Rancher')\",\n"
            "     \"text\": \"Your dialogue reply in authentic 1899 dialect.\"\n"
            "   }\n"
        )

        contents = []
        explicit_text = None
        if text_input and text_input.strip():
            explicit_text = text_input.strip()
            contents.append(f"Arthur Morgan says to you: \"{explicit_text}\". Respond in character.")
        elif audio_bytes and len(audio_bytes) > 2000:
            if audio_bytes.startswith(b'\x1aE\xdf\xa3'):
                mime = "audio/webm"
            elif audio_bytes.startswith(b'OggS'):
                mime = "audio/ogg"
            elif audio_bytes.startswith(b'ID3') or audio_bytes.startswith(b'\xff\xfb'):
                mime = "audio/mp3"
            else:
                mime = "audio/wav"

            contents.append(types.Part.from_bytes(data=audio_bytes, mime_type=mime))
            contents.append("Listen to the attached audio. 1) Transcribe what Arthur Morgan said. 2) Respond in character.")
        else:
            if is_player_aiming:
                contents.append("Arthur Morgan is aiming his weapon directly at you without speaking. React to this immediate life threat!")
            elif is_hogtied:
                contents.append("Arthur Morgan stands over you while you are hogtied on the ground. React to being tied up!")
            elif mode == "antagonize":
                contents.append("Arthur Morgan glared at you and aggressively antagonized you without speaking. React naturally.")
            else:
                contents.append("Arthur Morgan approaches you to talk. React naturally to his presence.")

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.85,
            top_p=0.9
        )

        last_error = None
        for model in MODELS_TO_TRY:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config
                )

                text_resp = response.text.strip()
                data = json.loads(text_resp)
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]

                transcription = explicit_text if explicit_text else data.get("transcription")
                if not transcription or transcription.strip() == "":
                    transcription = "(Silence / Gesture)" if not audio_bytes else "(Inaudible audio)"

                speaker = data.get("speaker")
                if not speaker or speaker in ["Stranger", "Local Resident", "Citizen", "Resident"] or (occupation and occupation not in speaker):
                    speaker = occupation if occupation else (speaker or (f"{zone_name} Citizen" if zone_name else "Stranger"))

                text = data.get("text") or data.get("reply", "...")

                return {
                    "transcription": transcription,
                    "speaker": speaker,
                    "text": text
                }

            except Exception as e:
                last_error = e
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                    print(f"[GEMINI] Model '{model}' busy. Cascading to backup model...")
                    continue
                else:
                    print(f"[GEMINI ERROR] ({model}): {e}")
                    break

        print(f"[GEMINI FINAL ERROR] All model attempts failed: {last_error}")
        return {
            "transcription": explicit_text or "(Speech processing error)",
            "speaker": "Stranger",
            "text": "What in tarnation was that?"
        }
