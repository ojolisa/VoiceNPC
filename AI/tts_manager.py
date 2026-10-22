import io
import os
import random
import threading
import soundfile as sf
import sounddevice as sd
from dotenv import load_dotenv

load_dotenv()

# Cloned & Dedicated Story Character Voices
NAMED_CHARACTER_VOICES = {
    "dutch": "895b84f0-e43b-441b-8b91-b4e5942be367",
    "dutch van der linde": "895b84f0-e43b-441b-8b91-b4e5942be367",
    "cs_dutch": "895b84f0-e43b-441b-8b91-b4e5942be367",
}

# High-fidelity Western frontier Cartesia voices
CARTESIA_MALE_VOICES = [
    {"name": "Dutch van der Linde (Cloned)", "id": "895b84f0-e43b-441b-8b91-b4e5942be367", "style": "leader"},
    {"name": "Troy", "id": "726d5ae5-055f-4c3d-8355-d9677de68937", "style": "cowboy"},
    {"name": "Trevor", "id": "c45bc5ec-dc68-4feb-8829-6e6b2748095d", "style": "elder"},
    {"name": "James", "id": "42b39f37-515f-4eee-8546-73e841679c1d", "style": "lawman"},
    {"name": "Mark", "id": "5619d38c-cf51-4d8e-9575-48f61a280413", "style": "rancher"},
    {"name": "Clive", "id": "b24f41fd-00a3-4cd8-992a-a0c9f13f3ef1", "style": "clerk"},
    {"name": "Ray", "id": "565510e8-6b45-45de-8758-13588fbaec73", "style": "vagrant"},
]

CARTESIA_FEMALE_VOICES = [
    {"name": "Darla", "id": "996a8b96-4804-46f0-8e05-3fd4ef1a87cd", "style": "pioneer"},
    {"name": "Ruth", "id": "11af83e2-23eb-452f-956e-7fee218ccb5c", "style": "authoritative"},
    {"name": "Linda", "id": "829ccd10-f8b3-43cd-b8a0-4aeaa81f3b30", "style": "ranch_wife"},
    {"name": "Jacqueline", "id": "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc", "style": "saloon_worker"},
    {"name": "Skylar", "id": "db6b0ed5-d5d3-463d-ae85-518a07d3c2b4", "style": "townswoman"},
]

class TTSManager:
    """Ultra-low latency speech synthesizer powered by Cartesia and LiveKit."""
    def __init__(self):
        self.api_key = os.getenv("CARTESIA_API_KEY", "").strip()
        self.client = None
        self.model_id = "sonic-3"
        self._init_cartesia()

    def _init_cartesia(self):
        if self.api_key:
            try:
                from cartesia import Cartesia
                self.client = Cartesia(api_key=self.api_key)
                print("[TTS] Initialized Cartesia Sonic TTS engine.")
            except Exception as e:
                print(f"[TTS WARNING] Failed to initialize Cartesia client: {e}")
                self.client = None
        else:
            print("[TTS WARNING] CARTESIA_API_KEY not found in environment!")

    def select_voice(self, is_male: bool = True, occupation: str = "") -> str:
        """Selects an authentic Cartesia voice ID based on NPC gender, role, or specific character."""
        occ_lower = (occupation or "").lower()

        # Check for dedicated / cloned story character voices (e.g. Dutch)
        for char_name, voice_id in NAMED_CHARACTER_VOICES.items():
            if char_name in occ_lower:
                return voice_id

        if is_male:
            if any(k in occ_lower for k in ["sheriff", "marshal", "deputy", "police", "guard", "officer"]):
                return "42b39f37-515f-4eee-8546-73e841679c1d"  # James (Authoritative)
            if any(k in occ_lower for k in ["old", "veteran", "miner", "hermit", "beggar"]):
                return "c45bc5ec-dc68-4feb-8829-6e6b2748095d"  # Trevor (Weathered elder)
            if any(k in occ_lower for k in ["clerk", "banker", "doctor", "lawyer", "mayor"]):
                return "b24f41fd-00a3-4cd8-992a-a0c9f13f3ef1"  # Clive (Articulate)
            if any(k in occ_lower for k in ["drunk", "vagrant"]):
                return "565510e8-6b45-45de-8758-13588fbaec73"  # Ray (Laid-back)
            if any(k in occ_lower for k in ["rancher", "outlaw", "hunter"]):
                return "5619d38c-cf51-4d8e-9575-48f61a280413"  # Mark (Deep presence)
            # Default male pool
            return random.choice(CARTESIA_MALE_VOICES)["id"]
        else:
            if any(k in occ_lower for k in ["saloon", "dancer", "young"]):
                return "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"  # Jacqueline
            if any(k in occ_lower for k in ["madam", "matron", "store", "shop"]):
                return "11af83e2-23eb-452f-956e-7fee218ccb5c"  # Ruth
            if any(k in occ_lower for k in ["ranch", "farmer"]):
                return "829ccd10-f8b3-43cd-b8a0-4aeaa81f3b30"  # Linda
            # Default female pool
            return random.choice(CARTESIA_FEMALE_VOICES)["id"]

    def _play_audio_data(self, data, sr, blocking: bool = False):
        try:
            sd.stop()
            sd.play(data, sr)
            if blocking:
                sd.wait()
        except Exception as e:
            print(f"[TTS AUDIO ERROR] Audio playback failed: {e}")

    def _synthesize_cartesia(self, text: str, voice_id: str) -> tuple:
        """Synthesizes speech using Cartesia and returns (numpy_array, sample_rate)."""
        response = self.client.tts.generate(
            model_id=self.model_id,
            transcript=text,
            voice=voice_id,
            output_format={"container": "wav", "encoding": "pcm_s16le", "sample_rate": 24000}
        )
        audio_bytes = response.read()
        buf = io.BytesIO(audio_bytes)
        data, sr = sf.read(buf)
        return data, sr

    def _speak_worker(self, text: str, is_male: bool, occupation: str, voice_id: str = None, blocking: bool = False):
        clean_text = text.replace('"', '').replace("'", "'").strip()
        if not voice_id:
            voice_id = self.select_voice(is_male, occupation)

        # 1. Primary: Cartesia
        if self.client:
            try:
                data, sr = self._synthesize_cartesia(clean_text, voice_id)
                self._play_audio_data(data, sr, blocking)
                return
            except Exception as e:
                print(f"[TTS CARTESIA ERROR] {e}. Falling back to edge-tts...")

        # 2. Backup: Edge TTS
        try:
            import asyncio
            import edge_tts
            fallback_voice = "en-US-GuyNeural" if is_male else "en-US-JennyNeural"
            comm = edge_tts.Communicate(clean_text, fallback_voice)
            buf = io.BytesIO()
            async def _run():
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        buf.write(chunk["data"])
            asyncio.run(_run())
            buf.seek(0)
            data, sr = sf.read(buf)
            self._play_audio_data(data, sr, blocking)
        except Exception as e:
            print(f"[TTS FALLBACK ERROR] Failed to synthesize/play audio: {e}")

    def speak(self, text: str, is_male: bool = True, occupation: str = "", voice_id: str = None, blocking: bool = False):
        """Generates TTS audio using Cartesia and plays through PC audio output."""
        if not text or not text.strip():
            return

        if blocking:
            self._speak_worker(text, is_male, occupation, voice_id=voice_id, blocking=True)
        else:
            t = threading.Thread(
                target=self._speak_worker,
                args=(text, is_male, occupation, voice_id, False),
                daemon=True
            )
            t.start()
