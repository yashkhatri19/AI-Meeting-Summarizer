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
    return {"status": "online", "mode": "100MB Forced Content-Type Engine"}

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    if not GROQ_KEY:
        return StreamingResponse(iter(["Error: GROQ_API_KEY environment token missing on Render."]), media_type="text/plain")

    temp_file_path = f"/tmp/{file.filename}"
    
    # 50MB - 100MB chunked buffering layer
    with open(temp_file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB buffer chunks
            buffer.write(chunk)

    async def massive_file_pipeline():
        try:
            # 100MB processing triggers long connection hold times -> No Timeout Limits
            timeout_setting = httpx.Timeout(None, connect=120.0)
            
            # Forcing content-type mapping so Groq never rejects binary data flags
            forced_content_type = file.content_type
            if not forced_content_type or forced_content_type == "application/octet-stream":
                if file.filename.lower().endswith(".mp4"):
                    forced_content_type = "video/mp4"
                elif file.filename.lower().endswith((".mp3", ".mpeg")):
                    forced_content_type = "audio/mpeg"
                else:
                    forced_content_type = "video/mp4" # Standard fallback block

            async with httpx.AsyncClient(timeout=timeout_setting) as client:
                # 1. Sending Multi-part Form Stream with Forced Content-Type Header
                with open(temp_file_path, "rb") as media_bytes:
                    whisper_response = await client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {GROQ_KEY}"},
                        files={"file": (file.filename, media_bytes, forced_content_type)},
                        data={"model": "whisper-large-v3"}
                    )
                
                whisper_data = whisper_response.json()
                raw_text = whisper_data.get("text", "")

                if not raw_text:
                    api_error_log = whisper_data.get("error", {}).get("message", "Unknown Payload Rejection.")
                    yield f"Error from Groq API: {api_error_log}"
                    return

                # 2. Complete academic translation node to enforce English output
                translation_payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system",
                            "content": "CRITICAL: You are an expert academic translator. Translate the given text completely into fluent, professional English prose. If the input language is Hindi or Hinglish, convert it entirely to fluent English. Output ONLY the final clean English text. Do not include notes, logs, or preamble."
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
                    json=translation_payload
                )
                
                translation_data = translation_response.json()
                english_translation = translation_data["choices"][0]["message"]["content"].strip()
                
                GLOBAL_CONTEXT["latest_transcript"] = english_translation
                yield english_translation

        except Exception as e:
            yield f"Server Exception Core: {str(e)}"
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(massive_file_pipeline(), media_type="text/plain")

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
        return {"reply": f"Chat tracking error: {str(e)}"}