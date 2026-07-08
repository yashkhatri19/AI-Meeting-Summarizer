import os
import httpx
import shutil
from fastapi import FastAPI, UploadFile, File, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
# Import moviepy to strip audio from video locally
from moviepy.video.io.VideoFileClip import VideoFileClip

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GLOBAL_CONTEXT = {
    "latest_transcript": "No lecture content loaded yet. Please upload a media file."
}

GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
TEMP_DIR = "./temp_chunks"

@app.route("/", methods=["GET", "HEAD"])
def check_server():
    return {"status": "online", "mode": "Production Frontend-Chunking Aggregator with Audio Compression"}

@app.post("/api/upload-chunk")
async def upload_chunk(
    file: UploadFile = File(...),
    chunkIndex: int = Form(...),
    totalChunks: int = Form(...),
    fileId: str = Form(...)
):
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    session_dir = os.path.join(TEMP_DIR, fileId)
    os.makedirs(session_dir, exist_ok=True)
    
    chunk_path = os.path.join(session_dir, f"part_{chunkIndex}.tmp")
    
    with open(chunk_path, "wb") as f:
        f.write(await file.read())
        
    if chunkIndex == totalChunks - 1:
        final_video_path = os.path.join(session_dir, f"{fileId}_final.mp4")
        final_audio_path = os.path.join(session_dir, f"{fileId}_final.mp3")
        
        # 1. Assemble segments into single media file
        try:
            with open(final_video_path, "wb") as final_file:
                for i in range(totalChunks):
                    c_path = os.path.join(session_dir, f"part_{i}.tmp")
                    if os.path.exists(c_path):
                        with open(c_path, "rb") as source_chunk:
                            final_file.write(source_chunk.read())
                    else:
                        return JSONResponse(status_code=400, content={"error": f"Missing chunk part {i}"})
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Failed assembling streams: {str(e)}"})

        # 2. Extract Audio from Video to dramatically compress payload size under 25MB
        try:
            video_clip = VideoFileClip(final_video_path)
            if video_clip.audio is not None:
                video_clip.audio.write_audiofile(final_audio_path, logger=None)
                video_clip.close()
                target_transcription_file = final_audio_path
            else:
                video_clip.close()
                target_transcription_file = final_video_path # Fallback if no audio track exists
        except Exception as e:
            # Fallback securely if moviepy raises format parsing issues
            target_transcription_file = final_video_path

        # 3. Request Transcription from Groq safely
        try:
            timeout_setting = httpx.Timeout(None, connect=120.0)
            final_combined_text = ""

            async with httpx.AsyncClient(timeout=timeout_setting) as client:
                with open(target_transcription_file, "rb") as target_file:
                    # Send compressed file (.mp3 / fallback .mp4)
                    file_extension = os.path.splitext(target_transcription_file)[1]
                    mime_type = "audio/mp3" if file_extension == ".mp3" else "video/mp4"
                    
                    whisper_response = await client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {GROQ_KEY}"},
                        files={"file": (f"audio_{fileId}{file_extension}", target_file, mime_type)},
                        data={"model": "whisper-large-v3"}
                    )
                
                res_data = whisper_response.json()
                
                if whisper_response.status_code != 200:
                    return JSONResponse(status_code=whisper_response.status_code, content={"error": f"Groq Whisper Error: {res_data}"})
                
                final_combined_text = res_data.get("text", "").strip()

            if not final_combined_text:
                return JSONResponse(status_code=400, content={"error": "Could not extract text from any video chunks."})

            # 4. Refinement & Translation Pipeline
            async with httpx.AsyncClient(timeout=timeout_setting) as client:
                translation_payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system",
                            "content": "CRITICAL: You are an expert academic translator. Combine the following lecture transcript pieces into single, cohesive, fluent English prose. If the text is in Hindi/Hinglish, translate it fully to English. Output ONLY the clean English text without any intro or meta-commentary."
                        },
                        {"role": "user", "content": final_combined_text}
                    ],
                    "temperature": 0.2
                }

                translation_response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                    json=translation_payload
                )
                
                translation_data = translation_response.json()
                english_output = translation_data["choices"][0]["message"]["content"].strip()
                
            GLOBAL_CONTEXT["latest_transcript"] = english_output
            return {"status": "completed", "transcript": english_output}

        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Aggregation processing broken: {str(e)}"})
        finally:
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)

    return {"status": "processing", "message": f"Chunk {chunkIndex + 1}/{totalChunks} saved successfully."}

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
                    "content": f"You are an expert classroom assistant. Answer the user's questions clearly, concisely, and using ONLY English, based exactly on this transcript:\n\n{active_context}"
                },
                {"role": "user", "content": user_query}
            ],
            "temperature": 0.3
        }

        async with httpx.AsyncClient() as client:
            chat_response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json=chat_payload,
                timeout=30.0
            )
            return {"reply": chat_response.json()["choices"][0]["message"]["content"].strip()}
    except Exception as e:
        return {"reply": f"Chat failed: {str(e)}"}