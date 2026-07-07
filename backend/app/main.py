import os
import httpx
import asyncio
from fastapi import FastAPI, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from groq import Groq

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global context store to keep chatbot answers tightly pinned to the last video uploaded
GLOBAL_CONTEXT = {
    "latest_transcript": "No lecture content loaded yet. Please upload a file."
}

# Standard direct Groq integration (Zero local processing)
GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

@app.get("/")
def home():
    return {"status": "online", "engine": "Direct Groq Streaming Gateway"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    if not GROQ_KEY or not client:
        return StreamingResponse(iter(["Error: GROQ_API_KEY is missing on Render settings."]), media_type="text/plain")

    # Save incoming file directly to local tmp without processing through pydub
    temp_file_path = f"/tmp/{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        buffer.write(await file.read())

    async def pipeline_streamer():
        try:
            # 1. Directly get raw text from Whisper transcriptions
            with open(temp_file_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3"
                )
            raw_text = transcription.text

            if not raw_text:
                yield "Error: Could not extract any readable speech from the video file."
                return

            # 2. Convert and translate raw text into structured English using updated model name
            translation_completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",  # Fully active version
                messages=[
                    {
                        "role": "system",
                        "content": "Translate the following audio transcript completely into professional, clear English. Provide ONLY the translated English prose text."
                    },
                    {"role": "user", "content": raw_text}
                ],
                temperature=0.2
            )
            
            english_output = translation_completion.choices[0].message.content.strip()
            GLOBAL_CONTEXT["latest_transcript"] = english_output
            yield english_output

        except Exception as e:
            yield f"Server Processing Error: {str(e)}"
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(pipeline_streamer(), media_type="text/plain")

@app.post("/api/chat")
async def chat_agent(payload: dict = Body(...)):
    """Handles chatbot node queries accurately in English"""
    user_query = payload.get("query", "")
    active_context = GLOBAL_CONTEXT["latest_transcript"]

    if not GROQ_KEY or not client:
        return {"reply": "Chat gateway configuration missing."}

    try:
        chat_completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": f"You are a helpful teaching assistant. Answer the user's question using ONLY English, based exactly on this lecture transcript:\n\n{active_context}"
                },
                {"role": "user", "content": user_query}
            ],
            temperature=0.3
        )
        return {"reply": chat_completion.choices[0].message.content.strip()}
    except Exception as e:
        return {"reply": f"Chat failed to compute: {str(e)}"}