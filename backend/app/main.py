import os
import shutil
import asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydub import AudioSegment
from groq import Groq
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Runtime Store chatbot query validation ke liye
GLOBAL_CONTEXT = {
    "latest_transcript": "No lecture content loaded yet. Please upload a video file."
}

# FFmpeg Paths Initialization
CURRENT_DIR = Path(__file__).parent.resolve()
if shutil.which("ffmpeg"):
    AudioSegment.converter = "ffmpeg"
    AudioSegment.ffprobe = "ffprobe"
else:
    AudioSegment.converter = str(CURRENT_DIR / "ffmpeg.exe")
    AudioSegment.ffprobe = str(CURRENT_DIR / "ffprobe.exe")


class WhisperService:
    def __init__(self):
        self.custom_client = httpx.Client(timeout=600.0)
        self.groq_key = os.getenv("GROQ_API_KEY", "").strip()
        if not self.groq_key:
            print("WARNING: GROQ_API_KEY missing from system environment variables!")
        self.client = Groq(
            api_key=self.groq_key, 
            http_client=self.custom_client
        )

    def transcribe_audio(self, input_file_path: str) -> str:
        compressed_audio_path = "temp_compressed_audio.mp3"
        try:
            print("Compressing file to fit under Groq's 25MB limit...")
            audio = AudioSegment.from_file(input_file_path)
            audio.export(compressed_audio_path, format="mp3", bitrate="64k")
            print("Compression complete. Uploading to Groq Whisper Core...")

            with open(compressed_audio_path, "rb") as file_to_send:
                response = self.client.audio.transcriptions.create(
                    file=file_to_send,
                    model="whisper-large-v3"
                )
            return response.text
        except Exception as e:
            print(f"Error inside WhisperService: {str(e)}")
            raise e
        finally:
            if os.path.exists(compressed_audio_path):
                os.remove(compressed_audio_path)

    def translate_and_clean_text(self, raw_text: str) -> str:
        """Forces the Hindi transcription to convert into perfect professional English prose"""
        try:
            chat_completion = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",  # Updated & highly active supported version
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert technical translator. Translate the following lecture text completely into clear, clean, grammatically perfect English. Maintain formatting like markdown headings if needed. Output ONLY the English translation."
                    },
                    {
                        "role": "user",
                        "content": raw_text
                    }
                ],
                temperature=0.2
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"Translation Layer Exception: {str(e)}")
            return raw_text # Fallback to original transcript if chat engine times out

    def execute_chat_query(self, user_query: str, context: str) -> str:
        """Executes targeted question answering over the current video's English context"""
        try:
            chat_completion = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a classroom assistant. Answer the user's questions based on this lecture text:\n\n{context}\n\nKeep the answer short, clear, and direct."
                    },
                    {
                        "role": "user",
                        "content": user_query
                    }
                ],
                temperature=0.3
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            return f"Chat Logic Exception: {str(e)}"


# Instantiate service
whisper_engine = WhisperService()

@app.get("/")
def check_status():
    return {"status": "online", "pipeline": "Whisper-v3 + Llama3.1 Realtime Ingestion"}


@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    temp_file_path = os.path.join("/tmp" if os.path.exists("/tmp") else ".", file.filename)
    
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    async def execution_streamer():
        try:
            # Step 1: Transcribe using locally wrapped Whisper engine
            raw_hindi_text = whisper_engine.transcribe_audio(temp_file_path)
            
            if raw_hindi_text:
                # Step 2: Pass text to Llama 3.1 for English transformation
                english_translated_prose = whisper_engine.translate_and_clean_text(raw_hindi_text)
                
                # Save to memory context for chat engine validation
                GLOBAL_CONTEXT["latest_transcript"] = english_translated_prose
                yield english_translated_prose
            else:
                yield "No spoken dialogue tracks detected in the media stream."
                
        except Exception as e:
            yield f"Pipeline Error: {str(e)}"
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(execution_streamer(), media_type="text/plain")


@app.post("/api/chat")
async def chat_agent(payload: dict = Body(...)):
    """Handles right side chatbot node streams dynamically without crashing"""
    user_query = payload.get("query", "")
    active_context = GLOBAL_CONTEXT["latest_transcript"]
    
    reply_output = whisper_engine.execute_chat_query(user_query, active_context)
    return {"reply": reply_output}