import os
import httpx
import math
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
    return {"status": "online", "mode": "100MB Chunk Splitting Core"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    if not GROQ_KEY:
        return StreamingResponse(iter(["Error: GROQ_API_KEY missing on Render."]), media_type="text/plain")

    temp_file_path = f"/tmp/{file.filename}"
    
    # Save the huge file locally in chunks to avoid memory crash
    with open(temp_file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)

    async def chunked_upload_pipeline():
        try:
            file_size = os.path.getsize(temp_file_path)
            # Groq's max limit is 25MB (24 * 1024 * 1024 bytes for safety buffer)
            max_chunk_size = 24 * 1024 * 1024 
            
            timeout_setting = httpx.Timeout(None, connect=120.0)
            full_raw_text = ""

            async with httpx.AsyncClient(timeout=timeout_setting) as client:
                # If file is smaller than 24MB, send it directly
                if file_size <= max_chunk_size:
                    with open(temp_file_path, "rb") as media_file:
                        whisper_response = await client.post(
                            "https://api.groq.com/openai/v1/audio/transcriptions",
                            headers={"Authorization": f"Bearer {GROQ_KEY}"},
                            files={"file": (file.filename, media_file, "video/mp4")},
                            data={"model": "whisper-large-v3"}
                        )
                    full_raw_text = whisper_response.json().get("text", "")
                else:
                    # Badi file handling: Split binary file into 24MB sequential blocks
                    total_chunks = math.ceil(file_size / max_chunk_size)
                    with open(temp_file_path, "rb") as master_file:
                        for i in range(total_chunks):
                            chunk_data = master_file.read(max_chunk_size)
                            chunk_filename = f"part_{i}_{file.filename}"
                            
                            whisper_response = await client.post(
                                "https://api.groq.com/openai/v1/audio/transcriptions",
                                headers={"Authorization": f"Bearer {GROQ_KEY}"},
                                files={"file": (chunk_filename, chunk_data, "video/mp4")},
                                data={"model": "whisper-large-v3"}
                            )
                            
                            chunk_text = whisper_response.json().get("text", "")
                            if chunk_text:
                                full_raw_text += " " + chunk_text

                if not full_raw_text.strip():
                    yield "Error: Groq API could not extract text from any file block."
                    return

                # 2. Strict Academic Translation to English
                translation_payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system",
                            "content": "CRITICAL: You are an expert academic translator. Translate the given text completely into fluent, professional English prose. If the input language is Hindi or Hinglish, convert it entirely to fluent English. Output ONLY the final clean English text. Do not include notes or preamble statements."
                        },
                        {"role": "user", "content": full_raw_text.strip()}
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
            yield f"Server Pipeline Processing Error: {str(e)}"
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(chunked_upload_pipeline(), media_type="text/plain")

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