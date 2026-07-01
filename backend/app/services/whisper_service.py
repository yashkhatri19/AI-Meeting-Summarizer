import os
import httpx
from groq import Groq
from app.core.config import settings

class WhisperService:
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY, http_client=httpx.Client())

    def transcribe_audio(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError("Audio file not found on server")
        
        with open(file_path, "rb") as audio_file:
            translation = self.client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3",
                response_format="text"
            )
        return translation