import socket
import json
import threading
import time
from audio_recorder import AudioRecorder
from livekit_agent import LiveKitVoiceNPCAgent

HOST = "127.0.0.1"
PORT = 8765

recorder = AudioRecorder()
agent = LiveKitVoiceNPCAgent()

current_context = {}
is_recording = False
lock = threading.Lock()

def process_interaction(client_sock, context: dict, audio_bytes: bytes):
    """Processes Arthur's voice with LiveKit Voice Agent (Gemini + Cartesia) and sends subtitles to RDR2."""
    mode = context.get("mode", "greet")
    ped_id = context.get("pedId", "Unknown")
    print(f"\n[AI] Processing conversation via LiveKit Agent... (Target Ped: {ped_id}, Mode: {mode}, Audio size: {len(audio_bytes)} bytes)")

    t0 = time.time()
    result = agent.process_turn(context, audio_bytes=audio_bytes)
    t1 = time.time()

    transcription = result.get("transcription", "")
    speaker = result.get("speaker", "Stranger")
    text = result.get("text", "...")
    voice_id = result.get("voice_id", "N/A")

    print(f"[AI] LiveKit pipeline finished in {t1 - t0:.2f}s:")
    print(f"     [PED] ID: {ped_id} | Voice ID: {voice_id}")
    print(f"     [STT] Arthur:  \"{transcription}\"")
    print(f"     [NPC] {speaker}: \"{text}\"")

    # Send subtitle back to RDR2 over TCP so RDR2 draws subtitles and turns off spinner
    try:
        payload = json.dumps({"transcription": transcription, "speaker": speaker, "text": text}) + "\n"
        client_sock.sendall(payload.encode("utf-8"))
    except Exception as e:
        print(f"[TCP ERROR] Failed to send response to RDR2: {e}")

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
                            print("[MIC] Stopped recording. Querying LiveKit Agent...")
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
    print("=" * 65)
    print("  RDR2 VoiceNPC AI Bridge Server")
    print("  LiveKit Agent Pipeline: Gemini (STT & LLM) + Cartesia (Sonic TTS)")
    print("  Redis Memory: Conversation Turns & Voice ID Caching per Ped")
    print(f"  Listening on {HOST}:{PORT}")
    print("=" * 65)

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
