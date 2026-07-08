import os
import httpx
from fastapi import FastAPI, UploadFile, File, Body, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared memory layout to track aggregated session pieces
CHUNK_STORAGE = {}
GLOBAL_CONTEXT = {
    "latest_transcript": "No lecture content loaded yet. Please upload a media file."
}

GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()

@app.get("/")
def check_server():
    return {"status": "online", "mode": "Production Frontend-Chunking Aggregator"}

@app.post("/api/upload-chunk")
async def handle_chunk_upload(
    file: UploadFile = File(...),
    chunkIndex: int = Form(...),
    totalChunks: int = Form(...),
    fileId: str = Form(...)
):
    if not GROQ_KEY:
        return JSONResponse(status_code=500, content={"error": "GROQ_API_KEY missing on Render."})

    # Ensure a session track directory exists
    session_dir = f"/tmp/{fileId}"
    os.makedirs(session_dir, exist_ok=True)
    
    chunk_path = f"{session_dir}/part_{chunkIndex}.mp4"
    
    # Save the current small independent blob chunk
    with open(chunk_path, "wb") as buffer:
        buffer.write(await file.read())

    # Check if all chunks have successfully landed
    all_chunks_received = len(os.listdir(session_dir)) == totalChunks

    if not all_chunks_received:
        return {"status": "processing", "message": f"Chunk {chunkIndex + 1}/{totalChunks} saved."}

    # Pipeline Processing Trigger once all blocks exist
    try:
        timeout_setting = httpx.Timeout(None, connect=120.0)
        aggregated_raw_text = []

        async with httpx.AsyncClient(timeout=timeout_setting) as client:
            # Process each chunk sequentially in correct order
            for i in range(totalChunks):
                target_chunk_path = f"{session_dir}/part_{i}.mp4"
                
                with open(target_chunk_path, "rb") as target_file:
                    whisper_response = await client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {GROQ_KEY}"},
                        files={"file": (f"segment_{i}.mp4", target_file, "video/mp4")},
                        data={"model": "whisper-large-v3"}
                    )
                
                res_data = whisper_response.json()
                if "text" in res_data and res_data["text"].strip():
                    aggregated_raw_text.append(res_data["text"])

        final_combined_text = " ".join(aggregated_raw_text).strip()

        if not final_combined_text:
            return JSONResponse(status_code=400, content={"error": "Could not extract text from any video chunks."})

        # Final Academic English Alignment Layer
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
            
        english_output = translation_response.json()["choices"][0]["message"]["content"].strip()
        GLOBAL_CONTEXT["latest_transcript"] = english_output

        return {"status": "completed", "transcript": english_output}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Aggregation processing broken: {str(e)}"})
    finally:
        # Cleanup session folder
        if os.path.exists(session_dir):
            for f in os.listdir(session_dir):
                os.remove(os.path.join(session_dir, f))
            os.rmdir(session_dir)

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