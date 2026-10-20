import io
import asyncio
import random
import soundfile as sf
import sounddevice as sd
import edge_tts

# Voices suitable for 1899 Western frontier dialogues
MALE_VOICES = [
    "en-US-ChristopherNeural",  # Gruff, grounded
    "en-US-EricNeural",         # Older, weathered
    "en-US-GuyNeural",          # Standard frontier male
    "en-US-RogerNeural"         # Rustic tone
]

FEMALE_VOICES = [
    "en-US-JennyNeural",        # Pioneer / frontier female
    "en-US-AriaNeural",         # Expressive
    "en-US-MichelleNeural"      # Resolute
]

async def _synthesize_edge_tts(text: str, voice: str, rate: str, pitch: str) -> tuple:
    """Streams audio chunks from edge-tts into numpy array via soundfile."""
    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    buf = io.BytesIO()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    data, sr = sf.read(buf)
    return data, sr

class TTSManager:
    def __init__(self):
        pass

    def speak(self, text: str, is_male: bool = True, blocking: bool = False):
        """Generates TTS audio and plays it through the default audio output."""
        if not text or not text.strip():
            return

        # Clean text of quotes or artifacts
        clean_text = text.replace('"', '').replace("'", "'").strip()

        # Select character voice and acoustic parameters
        if is_male:
            voice = random.choice(MALE_VOICES)
            rate = "-5%"
            pitch = "-6Hz"
        else:
            voice = random.choice(FEMALE_VOICES)
            rate = "-3%"
            pitch = "-2Hz"

        try:
            data, sr = asyncio.run(_synthesize_edge_tts(clean_text, voice, rate, pitch))
            # Stop any previous playback and play new utterance
            sd.stop()
            sd.play(data, sr)
            if blocking:
                sd.wait()
        except Exception as e:
            print(f"[TTS ERROR] Failed to synthesize/play audio: {e}")
