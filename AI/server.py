import socket
import json
import threading
import time
from audio_recorder import AudioRecorder
from ai_agent import GeminiAgent
from tts_manager import TTSManager

HOST = "127.0.0.1"
PORT = 8765

recorder = AudioRecorder()
agent = GeminiAgent()
tts = TTSManager()

current_context = {}
is_recording = False
lock = threading.Lock()

def process_interaction(client_sock, context: dict, audio_bytes: bytes):
    """Processes Arthur's voice with Gemini, triggers TTS, and sends back subtitles."""
    is_male = context.get("isMale", True)
    mode = context.get("mode", "greet")
    print(f"\n[AI] Processing conversation... (Mode: {mode}, Audio size: {len(audio_bytes)} bytes)")

    t0 = time.time()
    result = agent.generate_npc_reply(context, audio_bytes)
    t1 = time.time()

    transcription = result.get("transcription", "")
    speaker = result.get("speaker", "Stranger")
    text = result.get("text", "...")
    print(f"[AI] Gemini generated reply in {t1 - t0:.2f}s:")
    print(f"     [STT] Arthur:  \"{transcription}\"")
    print(f"     [NPC] {speaker}: \"{text}\"")

    # 1. Send subtitle back to RDR2 over TCP
    try:
        payload = json.dumps({"transcription": transcription, "speaker": speaker, "text": text}) + "\n"
        client_sock.sendall(payload.encode("utf-8"))
    except Exception as e:
        print(f"[TCP ERROR] Failed to send response to RDR2: {e}")

    # 2. Synthesize & play speech through Windows audio output
    try:
        tts.speak(text, is_male=is_male, blocking=False)
    except Exception as e:
        print(f"[TTS ERROR] {e}")

def handle_client(conn, addr):
    global current_context, is_recording
    print(f"\n[SERVER] Connected to RDR2 VoiceNPC plugin from {addr}")

    buffer = ""
    while True:
        try:
            try:
                data = conn.recv(1024)
            except socket.timeout:
                continue

            if not data:
                break
            buffer += data.decode("utf-8", errors="ignore")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue

                try:
                    event_data = json.loads(line)
                except Exception:
                    continue

                event = event_data.get("event")

                if event == "START_TALK":
                    with lock:
                        current_context = event_data
                        is_recording = True
                        print(f"\n[MIC] Started recording... (Target Ped: {event_data.get('pedId')})")
                        recorder.start()

                elif event == "STOP_TALK":
                    with lock:
                        if is_recording:
                            is_recording = False
                            print("[MIC] Stopped recording. Querying Gemini...")
                            audio_bytes = recorder.stop()
                            # Run inference in separate thread so TCP listener stays responsive
                            threading.Thread(
                                target=process_interaction,
                                args=(conn, current_context.copy(), audio_bytes),
                                daemon=True
                            ).start()

        except ConnectionResetError:
            break
        except Exception as e:
            print(f"[SERVER ERROR] {e}")
            break

    print("[SERVER] RDR2 disconnected. Waiting for reconnection...")
    try:
        conn.close()
    except Exception:
        pass

def main():
    print("=" * 60)
    print("  RDR2 VoiceNPC AI Bridge Server")
    print(f"  Listening on {HOST}:{PORT}")
    print("=" * 60)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    # 1.0s timeout ensures Python catches Ctrl+C / KeyboardInterrupt on Windows
    server.settimeout(1.0)

    print("\nReady. Start Red Dead Redemption 2 to begin voice interactions.")
    print("Press Ctrl+C to stop the server anytime.\n")

    try:
        while True:
            try:
                conn, addr = server.accept()
                conn.settimeout(1.0)
                handle_client(conn, addr)
            except socket.timeout:
                continue
    except KeyboardInterrupt:
        print("\n[SERVER] Shutdown requested by user (Ctrl+C). Exiting cleanly...")
    finally:
        try:
            server.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
