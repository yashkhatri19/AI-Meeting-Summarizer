import os
import httpx
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

# Chatbot ko validation history dene ke liye global runtime memory data
GLOBAL_CONTEXT = {
    "latest_transcript": "No lecture content loaded yet. Please upload a video file."
}

GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

@app.get("/")
def check_server():
    return {"status": "online", "mode": "Groq Realtime Audio Ingestion Core"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    if not GROQ_KEY:
        return StreamingResponse(iter(["Error: GROQ_API_KEY environment token missing on Render."]), media_type="text/plain")

    # Direct local file upload stream (No pydub processing, zero dependency crash)
    temp_file_path = f"/tmp/{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        buffer.write(await file.read())

    async def native_groq_streamer():
        try:
            # 1. Direct Whisper Transcription Layer
            with open(temp_file_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3"
                )
            raw_hindi_text = transcription.text

            if not raw_hindi_text:
                yield "Error: System could not extract audio data tracks from the file."
                return

            # 2. Llama 3.1 Translation layer to force output strictly into English
            translation_node = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert academic translator. Translate the given text completely into fluent, professional English prose. Do not include notes or explanations. Return ONLY the English text."
                    },
                    {"role": "user", "content": raw_hindi_text}
                ],
                temperature=0.1
            )
            
            english_translation = translation_node.choices[0].message.content.strip()
            GLOBAL_CONTEXT["latest_transcript"] = english_translation
            yield english_translation

        except Exception as e:
            yield f"Pipeline Core Exception: {str(e)}"
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(native_groq_streamer(), media_type="text/plain")

@app.post("/api/chat")
async def chat_agent(payload: dict = Body(...)):
    """Handles right-side chatbot execution contextual nodes purely in English"""
    user_query = payload.get("query", "")
    active_lecture_text = GLOBAL_CONTEXT["latest_transcript"]

    try:
        chat_node = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": f"You are a helpful classroom AI assistant. Answer the user's questions clearly, concisely, and using ONLY English, based exactly on this transcript context:\n\n{active_lecture_text}"
                },
                {"role": "user", "content": user_query}
            ],
            temperature=0.3
        )
        return {"reply": chat_node.choices[0].message.content.strip()}
    except Exception as e:
        return {"reply": f"Chat tracking error: {str(e)}"}