import os
import json
import time
from typing import Optional, List, Dict, Any, Callable
from dotenv import load_dotenv

load_dotenv()

class PedMemoryManager:
    """Manages persistent conversation memory and voice caching for RDR2 Peds using Redis.
    
    Keys schema:
      - ped:{ped_id}:voice   -> Cartesia voice ID string
      - ped:{ped_id}:history -> Redis list of JSON conversation turns
    """

    def __init__(self, redis_url: str = None, default_ttl: int = 86400):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "").strip()
        self.default_ttl = int(os.getenv("REDIS_TTL", default_ttl))
        self.client = None
        self._connected = False
        self._in_memory_voices: Dict[str, str] = {}
        self._in_memory_history: Dict[str, List[Dict[str, Any]]] = {}
        
        self._init_redis()

    def _init_redis(self):
        """Initializes the Redis connection pool."""
        try:
            import redis
            if self.redis_url:
                self.client = redis.from_url(
                    self.redis_url,
                    socket_connect_timeout=4.0,
                    socket_timeout=4.0,
                    retry_on_timeout=True,
                    decode_responses=True
                )
            else:
                host = os.getenv("REDIS_HOST", "127.0.0.1")
                port = int(os.getenv("REDIS_PORT", 6379))
                password = os.getenv("REDIS_PASSWORD", None) or None
                db = int(os.getenv("REDIS_DB", 0))
                self.client = redis.Redis(
                    host=host,
                    port=port,
                    password=password,
                    db=db,
                    socket_connect_timeout=4.0,
                    socket_timeout=4.0,
                    retry_on_timeout=True,
                    decode_responses=True
                )
            self.client.ping()
            self._connected = True
            print("[PED MEMORY] Connected to Redis instance successfully.")
        except Exception as e:
            self._connected = False
            self.client = None
            print(f"[PED MEMORY WARNING] Could not connect to Redis: {e}. Falling back to in-memory store.")

    def is_connected(self) -> bool:
        """Checks if active Redis connection is healthy."""
        if not self._connected or not self.client:
            return False
        try:
            return bool(self.client.ping())
        except Exception:
            self._connected = False
            return False

    # --- Key Generators ---
    @staticmethod
    def _voice_key(ped_id: str | int) -> str:
        return f"ped:{ped_id}:voice"

    @staticmethod
    def _history_key(ped_id: str | int) -> str:
        return f"ped:{ped_id}:history"

    # --- Voice Caching ---
    def get_voice_id(self, ped_id: str | int) -> Optional[str]:
        """Retrieves the cached voice ID for a given ped ID."""
        ped_key = str(ped_id)
        if self._connected and self.client:
            try:
                voice_id = self.client.get(self._voice_key(ped_key))
                if voice_id:
                    return voice_id
            except Exception as e:
                print(f"[PED MEMORY ERROR] Failed to get voice_id from Redis: {e}")

        return self._in_memory_voices.get(ped_key)

    def set_voice_id(self, ped_id: str | int, voice_id: str):
        """Caches the voice ID for a given ped ID."""
        ped_key = str(ped_id)
        self._in_memory_voices[ped_key] = voice_id

        if self._connected and self.client:
            try:
                k = self._voice_key(ped_key)
                self.client.set(k, voice_id, ex=self.default_ttl)
            except Exception as e:
                print(f"[PED MEMORY ERROR] Failed to set voice_id in Redis: {e}")

    def get_or_set_voice_id(
        self,
        ped_id: str | int,
        is_male: bool = True,
        occupation: str = "",
        voice_selector_fn: Optional[Callable[[bool, str], str]] = None
    ) -> str:
        """Retrieves existing cached voice ID or selects and stores a new one consistently."""
        existing_voice = self.get_voice_id(ped_id)
        if existing_voice:
            return existing_voice

        if voice_selector_fn:
            new_voice = voice_selector_fn(is_male, occupation)
        else:
            new_voice = "726d5ae5-055f-4c3d-8355-d9677de68937" if is_male else "996a8b96-4804-46f0-8e05-3fd4ef1a87cd"

        self.set_voice_id(ped_id, new_voice)
        return new_voice

    # --- Dialogue History ---
    def get_history(self, ped_id: str | int, max_turns: int = 10) -> List[Dict[str, Any]]:
        """Retrieves the last max_turns conversation turns for this ped."""
        ped_key = str(ped_id)
        if self._connected and self.client:
            try:
                k = self._history_key(ped_key)
                raw_items = self.client.lrange(k, -max_turns, -1)
                if raw_items:
                    turns = []
                    for item in raw_items:
                        try:
                            turns.append(json.loads(item))
                        except Exception:
                            continue
                    return turns
            except Exception as e:
                print(f"[PED MEMORY ERROR] Failed to get history from Redis: {e}")

        history = self._in_memory_history.get(ped_key, [])
        return history[-max_turns:]

    def add_turn(
        self,
        ped_id: str | int,
        user_text: str,
        npc_speaker: str,
        npc_text: str,
        max_history_len: int = 20
    ):
        """Appends a conversation turn to the ped's history list."""
        ped_key = str(ped_id)
        turn_data = {
            "user": user_text,
            "speaker": npc_speaker,
            "assistant": npc_text,
            "timestamp": time.time()
        }

        # Update in-memory fallback
        if ped_key not in self._in_memory_history:
            self._in_memory_history[ped_key] = []
        self._in_memory_history[ped_key].append(turn_data)
        if len(self._in_memory_history[ped_key]) > max_history_len:
            self._in_memory_history[ped_key] = self._in_memory_history[ped_key][-max_history_len:]

        # Update Redis
        if self._connected and self.client:
            try:
                hk = self._history_key(ped_key)
                payload = json.dumps(turn_data)

                pipe = self.client.pipeline()
                pipe.rpush(hk, payload)
                pipe.ltrim(hk, -max_history_len, -1)
                pipe.expire(hk, self.default_ttl)
                pipe.execute()
            except Exception as e:
                print(f"[PED MEMORY ERROR] Failed to record turn in Redis: {e}")

    def clear_ped(self, ped_id: str | int):
        """Clears all stored Redis memory and cached voice for a specific ped."""
        ped_key = str(ped_id)
        self._in_memory_voices.pop(ped_key, None)
        self._in_memory_history.pop(ped_key, None)

        if self._connected and self.client:
            try:
                self.client.delete(
                    self._voice_key(ped_key),
                    self._history_key(ped_key)
                )
            except Exception as e:
                print(f"[PED MEMORY ERROR] Failed to clear ped memory in Redis: {e}")
