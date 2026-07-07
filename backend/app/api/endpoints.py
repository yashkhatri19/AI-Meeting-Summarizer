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
    return {"status": "online", "mode": "Pure Fast API Engine"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    if not GROQ_KEY:
        return StreamingResponse(iter(["Error: GROQ_API_KEY missing on Render."]), media_type="text/plain")

    temp_file_path = f"/tmp/{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        buffer.write(await file.read())

    async def streaming_pipeline():
        try:
            async with httpx.AsyncClient() as client:
                # 1. Direct Whisper Transcription
                with open(temp_file_path, "rb") as audio_file:
                    whisper_response = await client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {GROQ_KEY}"},
                        files={"file": (file.filename, audio_file, file.content_type)},
                        data={"model": "whisper-large-v3"},
                        timeout=90.0
                    )
                
                whisper_data = whisper_response.json()
                raw_text = whisper_data.get("text", "")

                if not raw_text:
                    yield "Error: Could not extract speech tracks from file."
                    return

                # 2. Translate Hindi to English (Strict Instruction Layer)
                translation_payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system",
                            "content": "CRITICAL: You are an expert academic translator. Translate the given text completely into fluent, professional English prose. If the input is in Hindi, translate it to English. Output ONLY the final clean English text. Do not include notes or preamble."
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
                    timeout=40.0
                )
                
                translation_data = translation_response.json()
                english_translation = translation_data["choices"][0]["message"]["content"].strip()
                
                GLOBAL_CONTEXT["latest_transcript"] = english_translation
                yield english_translation

        except Exception as e:
            yield f"Server Pipeline Error: {str(e)}"
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(streaming_pipeline(), media_type="text/plain")

@app.post("/api/chat")
async def chat_agent(payload: dict = Body(...)):
    user_query = payload.get("query", "")
    active_context = GLOBAL_CONTEXT["latest_transcript"]

    try:
        chat_payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {
                    "role": "system",
                    "content": f"You are an expert classroom teaching assistant. Answer the user's questions clearly, concisely, and using ONLY English, based exactly on this transcript:\n\n{active_context}"
                },
                {"role": "user", "content": user_query}
            ],
            "temperature": 0.3
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
        return {"reply": f"Chat failed: {str(e)}"}