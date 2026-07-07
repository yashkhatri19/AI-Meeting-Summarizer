import os
import httpx
import subprocess
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
    return {"status": "online", "mode": "Badi Video Size Fix Engine"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    if not GROQ_KEY:
        return StreamingResponse(iter(["Error: GROQ_API_KEY missing on Render."]), media_type="text/plain")

    temp_video_path = f"/tmp/{file.filename}"
    temp_audio_path = f"/tmp/compressed_{os.path.splitext(file.filename)[0]}.mp3"
    
    # Save incoming big video in chunks
    with open(temp_video_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)

    async def compression_stream_pipeline():
        try:
            # 1. Native OS Level Audio Extraction (Bina pydub/moviepy ke 40MB video ko 2MB audio bana dega)
            # Render has native ffmpeg binary support in basic shell layers
            conversion_command = f"ffmpeg -i '{temp_video_path}' -vn -ar 16000 -ac 1 -b:a 64k -y '{temp_audio_path}'"
            process = subprocess.run(conversion_command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Agar OS extraction work kare toh audio use hoga, nahi toh fallback to native file
            active_file_path = temp_audio_path if os.path.exists(temp_audio_path) and os.path.getsize(temp_audio_path) > 0 else temp_video_path

            # 2. Unlimited Timeout Session setup for Groq Large Payload Ingestion
            timeout_setting = httpx.Timeout(None, connect=60.0)
            
            async with httpx.AsyncClient(timeout=timeout_setting) as client:
                with open(active_file_path, "rb") as audio_file:
                    whisper_response = await client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {GROQ_KEY}"},
                        files={"file": (os.path.basename(active_file_path), audio_file, "audio/mp3" if active_file_path == temp_audio_path else file.content_type)},
                        data={"model": "whisper-large-v3"}
                    )
                
                whisper_data = whisper_response.json()
                raw_text = whisper_data.get("text", "")

                if not raw_text:
                    yield f"Error from Groq API: {whisper_data.get('error', {}).get('message', 'File size over 25MB limit or unreadable format.')}"
                    return

                # 3. Force Translation strictly into professional English prose
                translation_payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system",
                            "content": "CRITICAL: You are an expert academic translator. Translate the given text completely into fluent, professional English prose. If the input is in Hindi or Hinglish, translate it completely to English. Output ONLY the final clean English text. Do not include notes or preamble."
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
            yield f"Server Exception Core Trace: {str(e)}"
        finally:
            # Clean up both temp files safely
            for path in [temp_video_path, temp_audio_path]:
                if os.path.exists(path):
                    os.remove(path)

    return StreamingResponse(compression_stream_pipeline(), media_type="text/plain")

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