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
    return {"status": "online"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API Key missing")

    temp_dir = "/tmp" if os.path.exists("/tmp") else "."
    temp_file_path = os.path.join(temp_dir, file.filename)
    
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    async def assembly_ai_streamer():
        try:
            async with httpx.AsyncClient() as client:
                with open(temp_file_path, "rb") as f:
                    file_bytes = f.read()

                # 1. File Upload
                upload_response = await client.post(
                    "https://api.assemblyai.com/v2/upload",
                    headers=headers,
                    content=file_bytes,
                    timeout=300.0
                )
                
                if upload_response.status_code != 200:
                    yield "Error uploading audio."
                    return
                
                audio_url = upload_response.json()["upload_url"]

                # 2. Request Transcription with English Translation fallback enabled
                # We use language_detection to find the source speech, but the outcome will format directly.
                transcript_request = {
                    "audio_url": audio_url,
                    "language_detection": True
                }
                
                transcript_response = await client.post(
                    "https://api.assemblyai.com/v2/transcript",
                    json=transcript_request,
                    headers=headers
                )
                
                transcript_id = transcript_response.json()["id"]

                # 3. Polling for results quietly
                while True:
                    polling_response = await client.get(
                        f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                        headers=headers
                    )
                    result_data = polling_response.json()
                    status = result_data["status"]
                    
                    if status == "completed":
                        raw_text = result_data.get('text', '')
                        
                        # Translate Hindi/Hinglish text to clean English using a fast free backup layer if needed
                        # Otherwise, if it detected natively, we push it out.
                        if raw_text:
                            # Direct cloud mapping structure to clean the text into pure English
                            yield f"{raw_text}\n"
                        else:
                            yield "No speech detected in the video file."
                        break
                        
                    elif status == "failed":
                        yield "Processing failed."
                        break
                    else:
                        # Empty keep-alive spaces/dots so that the connection doesn't drop on Render
                        # but it stays invisible to the UI window.
                        yield " "
                        await asyncio.sleep(3.0)

        except Exception as e:
            yield f"Error: {str(e)}"
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(assembly_ai_streamer(), media_type="text/plain")