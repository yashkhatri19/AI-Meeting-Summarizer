import os
import shutil
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException
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

@app.get("/")
def read_root():
    return {"status": "online", "provider": "AssemblyAI Free Tier Fixed"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="AssemblyAI API Key is missing on Render!")

    temp_dir = "/tmp" if os.path.exists("/tmp") else "."
    temp_file_path = os.path.join(temp_dir, file.filename)
    
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    async def assembly_ai_streamer():
        try:
            yield "🔄 [Connection]: Connected to AssemblyAI Pipeline...\n"
            yield f"📂 [File Staged]: {file.filename}\n"
            await asyncio.sleep(0.2)

            async with httpx.AsyncClient() as client:
                yield "⚡ [Pipeline]: Uploading audio stream to secure repository...\n"
                
                # FIX: File data ko pehle read karke bytes mein convert kar diya taaki async clash na ho
                with open(temp_file_path, "rb") as f:
                    file_bytes = f.read()

                upload_response = await client.post(
                    "https://api.assemblyai.com/v2/upload",
                    headers=headers,
                    content=file_bytes,
                    timeout=300.0
                )
                
                if upload_response.status_code != 200:
                    yield f"❌ [Upload Error]: {upload_response.text}\n"
                    return
                
                audio_url = upload_response.json()["upload_url"]
                yield "🚀 [Pipeline]: Upload complete. Initializing AI transcription & summary...\n"

                # 2. Transcription aur Summary request trigger karna
                transcript_request = {
                    "audio_url": audio_url,
                    "summarization": True,
                    "summary_model": "informative",
                    "summary_type": "bullets"
                }
                
                transcript_response = await client.post(
                    "https://api.assemblyai.com/v2/transcript",
                    json=transcript_request,
                    headers=headers
                )
                
                transcript_id = transcript_response.json()["id"]

                # 3. Polling (Check karna jab tak AI process na kar le)
                while True:
                    polling_response = await client.get(
                        f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                        headers=headers
                    )
                    status = polling_response.json()["status"]
                    
                    if status == "completed":
                        yield "\n✨ --- AUDIO ANALYSIS COMPLETE ---\n\n"
                        result_data = polling_response.json()
                        
                        yield "### 📝 Transcription Text:\n"
                        yield f"{result_data.get('text', 'No transcription available.')}\n\n"
                        yield "---\n"
                        yield "### 🎯 AI Summary & Action Items:\n"
                        yield f"{result_data.get('summary', 'No summary available.')}\n"
                        break
                    elif status == "failed":
                        yield f"❌ [AI Processing Failed]: {polling_response.json().get('error', 'Unknown Error')}\n"
                        break
                    else:
                        yield "⏳ [AI Thinking]: Analyzing speech nodes, extracting key actions...\n"
                        await asyncio.sleep(4.0)

        except Exception as e:
            yield f"\n❌ [Runtime Error]: {str(e)}\n"
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(assembly_ai_streamer(), media_type="text/plain")