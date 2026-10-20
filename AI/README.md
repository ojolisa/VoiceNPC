# VoiceNPC AI Bridge

Python backend for the Red Dead Redemption 2 VoiceNPC mod.

## Features
- **Direct Voice Understanding**: Uses Google Gemini (`gemini-flash-lite-latest` with automatic multi-model failover) for real-time audio comprehension and STT.
- **Authentic 1899 Dialogue**: Ingests in-game context (current town/zone, time of day, armed status, hostility/combat, NPC gender) to generate period-accurate responses.
- **Dynamic Character Personas**: Assigns distinct occupations (blacksmith, saloon drunk, municipal clerk, etc.) and mood temperaments to eliminate repetitive dialogue.
- **Anti-Cliché Filtering**: Banned tropes ensure varied and immersive conversations.
- **Fast Neural Speech (TTS)**: Streams natural character voices via Edge TTS directly to your PC audio output without consuming GPU resources.
- **Isolated Environment**: Runs completely inside its own virtual environment (`.venv`), keeping your global Python installation clean.

## Setup Instructions

1. Verify your API key is in [`AI/.env`](.env):
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

2. Start the AI bridge server:
   * Double-click [`start.bat`](start.bat) (or run `.venv\Scripts\python.exe server.py`).
   * Keep this command window open while playing.

3. Launch **Red Dead Redemption 2**.

## In-Game Controls
* Look at an NPC and **Hold** <kbd>T</kbd> on keyboard (or **Greet** / **Antagonize** on controller) while speaking into your microphone.
* **Release** the button when done speaking.
* The native RDR2 revolving cylinder spinner ("Thinking...") will appear while Gemini processes your words.
* The NPC's voice will play through your speakers, and two-line dialogue subtitles will appear:
  * **Arthur's Speech (STT)** in soft ice-blue.
  * **NPC's Reply** in native yellow/white.
