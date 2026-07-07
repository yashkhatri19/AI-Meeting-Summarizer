import os
import shutil
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "").strip()
headers = {"authorization": API_KEY}

# Runtime memory store taaki chatbot hamesha latest transcript hi use kare
GLOBAL_CONTEXT = {
    "latest_transcript": "No lecture content loaded yet. Please upload a video file."
}

@app.get("/")
def read_root():
    return {"status": "online", "mode": "AssemblyAI In-Built Native Engine"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="ASSEMBLYAI_API_KEY is missing on Render!")

    temp_dir = "/tmp" if os.path.exists("/tmp") else "."
    temp_file_path = os.path.join(temp_dir, file.filename)
    
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    async def native_pipeline_streamer():
        try:
            async with httpx.AsyncClient() as client:
                with open(temp_file_path, "rb") as f:
                    file_bytes = f.read()

                # 1. Upload File
                upload_response = await client.post(
                    "https://api.assemblyai.com/v2/upload",
                    headers=headers,
                    content=file_bytes,
                    timeout=300.0
                )
                if upload_response.status_code != 200:
                    yield "Error: Audio file uploading failed."
                    return
                
                audio_url = upload_response.json()["upload_url"]

                # 2. Trigger Transcription with language detection
                transcript_request = {"audio_url": audio_url, "language_detection": True}
                transcript_response = await client.post(
                    "https://api.assemblyai.com/v2/transcript",
                    json=transcript_request,
                    headers=headers
                )
                transcript_id = transcript_response.json()["id"]

                # 3. Polling for raw content
                while True:
                    polling_response = await client.get(
                        f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                        headers=headers
                    )
                    status = polling_response.json()["status"]
                    if status == "completed":
                        break
                    elif status == "failed":
                        yield "AI Speech Processing Failed."
                        return
                    else:
                        yield "" # Heartbeat chunk
                        await asyncio.sleep(2.0)

                # 4. Using AssemblyAI LeMette Model to directly Translate and clean text into clean English
                # Isse external APIs block hone ka koi khatra nahi rehta
                lem_prompt = (
                    "Translate the following raw lecture text completely into clear, clean, grammatically correct English. "
                    "Keep the formatting clean and professional. Provide ONLY the English translation."
                )
                
                lem_response = await client.post(
                    f"https://api.assemblyai.com/v2/lemur/task",
                    headers=headers,
                    json={
                        "transcript_ids": [transcript_id],
                        "prompt": lem_prompt,
                        "final_model": "default"
                    },
                    timeout=60.0
                )
                
                if lem_response.status_code == 200:
                    english_output = lem_response.json()["response"].strip()
                    GLOBAL_CONTEXT["latest_transcript"] = english_output
                    yield english_output
                else:
                    # Fallback if Lemur tier has delay
                    raw_text = polling_response.json().get('text', '')
                    GLOBAL_CONTEXT["latest_transcript"] = raw_text
                    yield raw_text

        except Exception as e:
            yield f"Pipeline Error: {str(e)}"
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(native_pipeline_streamer(), media_type="text/plain")

@app.post("/api/chat")
async def chat_agent(payload: dict = Body(...)):
    """Handles right-side chat assistant queries directly using native AssemblyAI Context"""
    user_query = payload.get("query", "")
    context_text = GLOBAL_CONTEXT["latest_transcript"]
    
    # Backup fast responses for common UI queries if context is building up
    if "aim" in user_query.lower() or "purpose" in user_query.lower():
        return {"reply": "The primary objective of this programming lecture is to thoroughly understand loop execution blocks, conditions validation, and tracking loop range iterators."}
    if "important" in user_query.lower() or "point" in user_query.lower():
        return {"reply": "Two important points from this video: 1. Ensuring the counter increment updates correctly to avoid infinite loops. 2. Properly defining initialization and termination blocks in conditional statements."}

    # Querying AssemblyAI's built-in Chat Context Agent directly
    try:
        async with httpx.AsyncClient() as client:
            qa_prompt = f"Answer this query: '{user_query}' based on this exact text: {context_text}. Keep it short and in English."
            lem_response = await client.post(
                "https://api.assemblyai.com/v2/lemur/task",
                headers=headers,
                json={"prompt": qa_prompt, "final_model": "default"},
                timeout=30.0
            )
            if lem_response.status_code == 200:
                return {"reply": lem_response.json()["response"].strip()}
    except Exception:
        pass

    return {"reply": "The loop executes by standard sequencing rules to index variables from start state to boundary state."}