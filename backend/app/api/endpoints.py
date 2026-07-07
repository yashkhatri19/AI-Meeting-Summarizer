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
    "latest_transcript": "Abhi tak koi lecture upload nahi hua hai. Kripya video file upload karein."
}

GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()

@app.get("/")
def check_server():
    return {"status": "online", "mode": "Hindi Native Engine"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    if not GROQ_KEY:
        return StreamingResponse(iter(["Error: Render settings mein GROQ_API_KEY missing hai."]), media_type="text/plain")

    temp_file_path = f"/tmp/{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        buffer.write(await file.read())

    async def native_groq_pipeline():
        try:
            async with httpx.AsyncClient() as client:
                # 1. Direct Multipart upload for Whisper (Sending data directly to Groq)
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
                    yield "Error: Video se text extract nahi ho paya. Kripya file format check karein."
                    return

                # Save transcription in global context
                GLOBAL_CONTEXT["latest_transcript"] = raw_text
                yield raw_text

        except Exception as e:
            yield f"Server Exception Error: {str(e)}"
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(native_groq_pipeline(), media_type="text/plain")

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
                    "content": f"Aap ek helpful classroom teaching assistant hain. Diye gaye transcript context ke hisab se student ke sawaal ka jawab bilkul clear bhasha (Hindi/Hinglish) mein dein:\n\n{active_context}"
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