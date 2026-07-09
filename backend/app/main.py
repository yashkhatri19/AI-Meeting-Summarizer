import os
import jwt
import httpx
import shutil
import sqlite3
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from moviepy.video.io.VideoFileClip import VideoFileClip

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET = os.getenv("JWT_SECRET", "VOX_SUPER_SECRET_KEY_9988")
JWT_ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_bearer = HTTPBearer()

USER_TRANSCRIPT_STORAGE = {}
GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
TEMP_DIR = "./temp_chunks"
executor = ThreadPoolExecutor(max_workers=4)  # For running heavy video conversion safely

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route("/", methods=["GET", "HEAD"])
def check_server():
    return {"status": "online", "mode": "Production Session-Isolated Aggregator"}

# --- AUTH ENDPOINTS ---
@app.post("/api/auth/register")
async def register(payload: dict = Body(...)):
    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")
    
    hashed_pwd = pwd_context.hash(password)
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_pwd))
        conn.commit()
        conn.close()
        return {"message": "Registration successful!"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="This email is already registered.")

@app.post("/api/auth/login")
async def login(payload: dict = Body(...)):
    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")
    
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or not pwd_context.verify(password, row[0]):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
        
    expire = datetime.utcnow() + timedelta(hours=24)
    token = jwt.encode({"sub": email, "exp": expire}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"token": token, "email": email}

# Worker function to safely process MoviePy without freezing the web server loop
def sync_extract_audio(final_video_path, final_audio_path):
    try:
        video_clip = VideoFileClip(final_video_path)
        if video_clip.audio is not None:
            video_clip.audio.write_audiofile(final_audio_path, logger=None)
            video_clip.close()
            return final_audio_path
        video_clip.close()
    except Exception:
        pass
    return final_video_path

@app.post("/api/upload-chunk")
async def upload_chunk(
    file: UploadFile = File(...),
    chunkIndex: int = Form(...),
    totalChunks: int = Form(...),
    fileId: str = Form(...),
    email: str = Form("anonymous")
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
        
        try:
            with open(final_video_path, "wb") as final_file:
                for i in range(totalChunks):
                    c_path = os.path.join(session_dir, f"part_{i}.tmp")
                    if os.path.exists(c_path):
                        with open(c_path, "rb") as source_chunk:
                            final_file.write(source_chunk.read())
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Failed stream assembly: {str(e)}"})

        # Offload video audio extraction safely onto worker thread pool
        loop = asyncio.get_running_loop()
        target_transcription_file = await loop.run_in_executor(
            executor, sync_extract_audio, final_video_path, final_audio_path
        )

        try:
            timeout_setting = httpx.Timeout(None, connect=120.0)
            async with httpx.AsyncClient(timeout=timeout_setting) as client:
                with open(target_transcription_file, "rb") as target_file:
                    file_extension = os.path.splitext(target_transcription_file)[1]
                    mime_type = "audio/mp3" if file_extension == ".mp3" else "video/mp4"
                    
                    whisper_response = await client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {GROQ_KEY}"},
                        files={"file": (f"audio_{fileId}{file_extension}", target_file, mime_type)},
                        data={"model": "whisper-large-v3"}
                    )
                res_data = whisper_response.json()
                final_combined_text = res_data.get("text", "").strip()

            if not final_combined_text:
                return JSONResponse(status_code=400, content={"error": "Could not extract text."})

            async with httpx.AsyncClient(timeout=timeout_setting) as client:
                translation_response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [
                            {"role": "system", "content": "CRITICAL: You are an expert academic translator. Combine transcript pieces into clean cohesive English prose only. Never use any language other than English."},
                            {"role": "user", "content": final_combined_text}
                        ],
                        "temperature": 0.2
                    }
                )
                english_output = translation_response.json()["choices"][0]["message"]["content"].strip()
                
            USER_TRANSCRIPT_STORAGE[email.lower()] = english_output
            USER_TRANSCRIPT_STORAGE[fileId] = english_output
            return {"status": "completed", "transcript": english_output}
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})
        finally:
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)

    return {"status": "processing", "message": f"Chunk {chunkIndex + 1}/{totalChunks} saved."}

@app.post("/api/chat")
async def chat_agent(payload: dict = Body(...)):
    user_query = payload.get("query", "")
    email = payload.get("email", "anonymous").lower()
    file_id = payload.get("fileId", "")
    
    active_context = USER_TRANSCRIPT_STORAGE.get(email) or USER_TRANSCRIPT_STORAGE.get(file_id) or "No contextual lecture transcript found."

    try:
        async with httpx.AsyncClient() as client:
            chat_response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": f"Answer concisely, naturally, and exclusively in English based exactly on this context:\n\n{active_context}"},
                        {"role": "user", "content": user_query}
                    ],
                    "temperature": 0.3
                },
                timeout=30.0
            )
            return {"reply": chat_response.json()["choices"][0]["message"]["content"].strip()}
    except Exception as e:
        return {"reply": f"Chat failed: {str(e)}"}