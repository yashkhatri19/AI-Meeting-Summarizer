import os
import jwt
import time
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

GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
TEMP_DIR = "./temp_chunks"
executor = ThreadPoolExecutor(max_workers=4)

def get_db_connection():
    conn = sqlite3.connect("users.db", timeout=30.0)
    # Enforce database configurations every time a connection opens
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def execute_write_query(query, params=()):
    """
    Executes structural SQL statements with an improved recursive retry 
    backoff pattern to entirely prevent "database is locked" crashes.
    """
    retries = 10
    delay = 0.1
    while retries > 0:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            conn.close()
            return 
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                retries -= 1
                time.sleep(delay)
                delay *= 1.5
            else:
                raise e
    raise HTTPException(status_code=503, detail="Database busy. Please submit transaction again.")

def init_db():
    conn = get_db_connection() 
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS upload_history (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_size TEXT NOT NULL,
            transcript TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

def sync_extract_audio(final_video_path, final_audio_path):
    try:
        video_clip = VideoFileClip(final_video_path)
        if video_clip.audio is not None:
            video_clip.audio.write_audiofile(final_audio_path, logger=None)
            video_clip.close()
            if os.path.exists(final_audio_path) and os.path.getsize(final_audio_path) > 0:
                return final_audio_path
        if video_clip:
            video_clip.close()
    except Exception as e:
        print(f"[Audio Extraction Exception Warning]: {str(e)}")
    
    return final_video_path

@app.post("/api/auth/register")
async def register(payload: dict = Body(...)):
    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")
    
    hashed_pwd = pwd_context.hash(password)
    try:
        execute_write_query("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_pwd))
        return {"message": "Registration successful!"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="This email is already registered.")

@app.post("/api/auth/login")
async def login(payload: dict = Body(...)):
    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or not pwd_context.verify(password, row[0]):
        raise HTTPException(status_code=401, detail="Please do Register or check your credentials.")
        
    expire = datetime.utcnow() + timedelta(hours=24)
    token = jwt.encode({"sub": email, "exp": expire}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"token": token, "email": email}

@app.get("/api/history")
async def get_history(email: str):
    email_clean = email.strip().lower()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, file_name, file_size, transcript, timestamp 
            FROM upload_history WHERE email = ? ORDER BY timestamp DESC
        """, (email_clean,))
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": r[0],
                "fileName": r[1],
                "fileSize": r[2],
                "transcript": r[3],
                "messages": [{"sender": "ai", "text": "✨ Ask Anything about your Video Content!"}],
                "timestamp": r[4]
            } for r in rows
        ]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.delete("/api/history/{session_id}")
async def delete_history(session_id: str, email: str):
    try:
        execute_write_query("DELETE FROM upload_history WHERE id = ? AND email = ?", (session_id, email.strip().lower()))
        return {"status": "deleted"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/upload-chunk")
async def upload_chunk(
    file: UploadFile = File(...),
    chunkIndex: int = Form(...),
    totalChunks: int = Form(...),
    fileId: str = Form(...)
):
    try:
        session_dir = os.path.join(TEMP_DIR, fileId)
        os.makedirs(session_dir, exist_ok=True)
        
        chunk_path = os.path.join(session_dir, f"part_{chunkIndex}.tmp")
        with open(chunk_path, "wb") as f:
            f.write(await file.read())
            
        return {"status": "processing", "message": f"Chunk {chunkIndex + 1}/{totalChunks} saved."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Chunk upload failed: {str(e)}"})

@app.post("/api/assemble-file")
async def assemble_file(payload: dict = Body(...)):
    fileId = payload.get("fileId")
    totalChunks = payload.get("totalChunks")
    fileName = payload.get("fileName", "video.mp4")
    email = payload.get("email", "anonymous").lower().strip()

    if not fileId or totalChunks is None:
        raise HTTPException(status_code=400, detail="Missing required assembly parameters.")

    session_dir = os.path.join(TEMP_DIR, fileId)
    final_video_path = os.path.join(session_dir, f"{fileId}_final.mp4")
    final_audio_path = os.path.join(session_dir, f"{fileId}_final.mp3")

    try:
        # Reassemble components sequentially
        with open(final_video_path, "wb") as final_file:
            for i in range(totalChunks):
                c_path = os.path.join(session_dir, f"part_{i}.tmp")
                if not os.path.exists(c_path):
                    raise HTTPException(status_code=400, detail=f"Missing chunk file part_{i}")
                with open(c_path, "rb") as source_chunk:
                    final_file.write(source_chunk.read())

        # Thread isolation for MoviePy processing
        loop = asyncio.get_running_loop()
        target_transcription_file = await loop.run_in_executor(
            executor, sync_extract_audio, final_video_path, final_audio_path
        )

        # Groq Whisper Engine Transcription Step
        timeout_setting = httpx.Timeout(None, connect=120.0, read=120.0)
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
            
            if whisper_response.status_code != 200:
                return JSONResponse(
                    status_code=whisper_response.status_code, 
                    content={"error": f"Groq Whisper rejected payload: {whisper_response.text}"}
                )
                
            res_data = whisper_response.json()
            final_combined_text = res_data.get("text", "").strip()

        if not final_combined_text or len(final_combined_text) < 3:
            return JSONResponse(status_code=400, content={"error": "Could not extract text. Audio stream might be empty or silent."})

        # Prose formatting clean up
        async with httpx.AsyncClient(timeout=timeout_setting) as client:
            translation_response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": "You are a professional assistant. Clean up this speech transcript text into readable, cohesive paragraphs. Keep the output strictly in English. Do not add any meta-commentary like 'Here is the transcript' or conversational replies. Output ONLY the polished text."},
                        {"role": "user", "content": final_combined_text}
                    ],
                    "temperature": 0.2
                }
            )
            
            if translation_response.status_code != 200:
                english_output = final_combined_text
            else:
                english_output = translation_response.json()["choices"][0]["message"]["content"].strip()
            
        size_calculated = f"{(os.path.getsize(final_video_path)/(1024*1024)):.2f} MB"
        current_time_str = datetime.now().strftime("%I:%M %p")
        
        # Safe non-blocking DB transaction
        execute_write_query("""
            INSERT INTO upload_history (id, email, file_name, file_size, transcript, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (fileId, email, fileName, size_calculated, english_output, current_time_str))

        # Safely clear temp storage only after successful completion
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)

        return {"status": "completed", "transcript": english_output}
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Assembly workflow crashed: {str(e)}"})

@app.post("/api/chat")
async def chat_agent(payload: dict = Body(...)):
    user_query = payload.get("query", "")
    email = payload.get("email", "anonymous").lower().strip()
    file_id = payload.get("fileId", "")
    
    active_context = "No contextual lecture transcript found."
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT transcript FROM upload_history WHERE id = ? AND email = ?", (file_id, email))
        row = cursor.fetchone()
        if row:
            active_context = row[0]
        conn.close()
    except Exception:
        pass

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