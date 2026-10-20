# VoiceNPC AI Bridge (LiveKit + Cartesia + Gemini)

Python backend for the Red Dead Redemption 2 VoiceNPC mod, powered by **LiveKit Agents**, **Cartesia** (STT & TTS), and **Google Gemini** (LLM).

## Features
- **LiveKit Voice Agent Architecture**: Modular real-time agent framework (`livekit-agents`) orchestrating STT, LLM, and TTS.
- **Ultra-Fast Speech Recognition (Cartesia STT ink-whisper)**: Sub-200ms speech-to-text transcribing Arthur's spoken microphone input with exceptional accuracy.
- **Ultra-Low Latency Speech Synthesis (Cartesia Sonic-3)**: Expressive, authentic voices tailored for 1899 Western frontier characters (sheriffs, weathered elders, miners, saloon women, ranchers). Latency under 150ms.
- **1899 Frontier Dialogue Reasoning (Gemini)**: Uses Google Gemini (`gemini-3.5-flash-lite` / `gemini-3.8-flash` with multi-model failover) for period-accurate roleplay and context awareness.
- **Dynamic Character Personas**: Assigns distinct occupations (blacksmith, saloon drunk, municipal clerk, sheriff, etc.) and mood temperaments to eliminate repetitive dialogue.
- **Dual Subtitles & In-Game UI**: Streams dual-line subtitles (Arthur STT + NPC dialogue) and syncs with the native RDR2 revolving cylinder spinner.
- **Isolated Environment**: Runs completely inside its own virtual environment (`.venv`), keeping your global Python installation clean.

## Setup Instructions

1. Verify your API keys in [`AI/.env`](.env):
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   CARTESIA_API_KEY=sk_car_ecV7TQdX6AnxEwyYbpLvhk

   # LiveKit Cloud Project
   LIVEKIT_URL=wss://my-project-fbnm6kkc.livekit.cloud
   LIVEKIT_API_KEY=APIppXgc7eSyN7E
   LIVEKIT_API_SECRET=your_livekit_api_secret_here
   ```

2. Start the AI bridge server:
   * Double-click [`start.bat`](start.bat) (or run `.venv\Scripts\python.exe server.py`).
   * Keep this command window open while playing.

3. Launch **Red Dead Redemption 2**.

## In-Game Controls
* Look at an NPC and **Hold** <kbd>T</kbd> on keyboard (or <kbd>A</kbd> on controller) while speaking into your microphone.
* **Release** the button when done speaking.
* Cartesia STT transcribes your words in ~0.15s, Gemini generates the NPC's response, and Cartesia Sonic streams the voice to your speakers.
