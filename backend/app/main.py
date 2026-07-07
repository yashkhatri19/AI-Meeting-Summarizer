import os
import httpx
from fastapi import FastAPI, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GLOBAL_CONTEXT = {
    "latest_transcript": "No lecture content loaded yet. Please upload a video file."
}

GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()

@app.get("/")
def check_server():
    return {"status": "online", "mode": "Pure HTTPX Streaming Core"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    if not GROQ_KEY:
        return StreamingResponse(iter(["Error: GROQ_API_KEY environment token missing on Render."]), media_type="text/plain")

    temp_file_path = f"/tmp/{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        buffer.write(await file.read())

    async def native_api_streamer():
        try:
            # 1. Whisper Transcription via Direct HTTP Post Request
            async with httpx.AsyncClient() as client:
                with open(temp_file_path, "rb") as audio_file:
                    whisper_response = await client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {GROQ_KEY}"},
                        files={"file": (file.filename, audio_file)},
                        data={"model": "whisper-large-v3"},
                        timeout=60.0
                    )
                
                whisper_data = whisper_response.json()
                raw_text = whisper_data.get("text", "")

                if not raw_text:
                    yield "Error: Could not extract speech tracks from file via Groq API."
                    return

                # 2. Translation Node via Direct Chat Completion Request
                translation_payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert academic translator. Translate the given text completely into fluent, professional English prose. Do not include notes or explanations. Return ONLY the English text."
                        },
                        {"role": "user", "content": raw_text}
                    ],
                    "temperature": 0.1
                }

                translation_response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=translation_payload,
                    timeout=30.0
                )
                
                translation_data = translation_response.json()
                english_translation = translation_data["choices"][0]["message"]["content"].strip()
                
                GLOBAL_CONTEXT["latest_transcript"] = english_translation
                yield english_translation

        except Exception as e:
            yield f"Pipeline Core Exception: {str(e)}"
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(native_api_streamer(), media_type="text/plain")

@app.post("/api/chat")
async def chat_agent(payload: dict = Body(...)):
    user_query = payload.get("query", "")
    active_lecture_text = GLOBAL_CONTEXT["latest_transcript"]

    if not GROQ_KEY:
        return {"reply": "Groq Key configuration missing."}

    try:
        chat_payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {
                    "role": "system",
                    "content": f"You are a helpful classroom AI assistant. Answer the user's questions clearly, concisely, and using ONLY English, based exactly on this transcript context:\n\n{active_lecture_text}"
                },
                {"role": "user", "content": user_query}
            ],
            temperature: 0.3
        }

        async with httpx.AsyncClient() as client:
            chat_response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_KEY}",
                    "Content-Type": "application/json"
                },
                json=chat_payload,
                timeout=30.0
            )
            chat_data = chat_response.json()
            return {"reply": chat_data["choices"][0]["message"]["content"].strip()}
    except Exception as e:
        return {"reply": f"Chat tracking error: {str(e)}"}