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

ASSEMBLY_KEY = os.getenv("ASSEMBLYAI_API_KEY", "").strip()
GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()

# Global Runtime Store taaki chatbot dynamic content read kar sake
GLOBAL_CONTEXT = {
    "latest_transcript": "No lecture content loaded yet. Please upload a video file."
}

async def groq_llm_layer(system_prompt: str, user_content: str) -> str:
    """Ultra-fast Groq Llama-3 Cloud engine to process transcription and chatbot queries"""
    if not GROQ_KEY:
        return "Error: GROQ_API_KEY missing in Render environment variables."
    
    try:
        async with httpx.AsyncClient() as client:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama3-8b-8192",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.2
            }
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"].strip()
            return f"LLM Gateway Error: {response.text}"
    except Exception as e:
        return f"Translation/LLM Layer Crash: {str(e)}"

@app.get("/")
def read_root():
    return {"status": "online", "engine": "AssemblyAI + Groq Dual Pipeline"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    if not ASSEMBLY_KEY:
        raise HTTPException(status_code=500, detail="AssemblyAI API Key missing")

    temp_dir = "/tmp" if os.path.exists("/tmp") else "."
    temp_file_path = os.path.join(temp_dir, file.filename)
    
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    async def core_processing_streamer():
        try:
            async with httpx.AsyncClient() as client:
                with open(temp_file_path, "rb") as f:
                    file_bytes = f.read()

                # 1. File Upload to AssemblyAI
                upload_response = await client.post(
                    "https://api.assemblyai.com/v2/upload",
                    headers={"authorization": ASSEMBLY_KEY},
                    content=file_bytes,
                    timeout=300.0
                )
                
                if upload_response.status_code != 200:
                    yield "Error: Audio file upload rejected."
                    return
                
                audio_url = upload_response.json()["upload_url"]

                # 2. Triggering Transcription
                transcript_request = {"audio_url": audio_url, "language_detection": True}
                transcript_response = await client.post(
                    "https://api.assemblyai.com/v2/transcript",
                    json=transcript_request,
                    headers={"authorization": ASSEMBLY_KEY}
                )
                transcript_id = transcript_response.json()["id"]

                # 3. Polling quietly
                raw_hindi_text = ""
                while True:
                    polling_response = await client.get(
                        f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                        headers={"authorization": ASSEMBLY_KEY}
                    )
                    result_data = polling_response.json()
                    status = result_data["status"]
                    
                    if status == "completed":
                        raw_hindi_text = result_data.get('text', '')
                        break
                    elif status == "failed":
                        yield "AI Processing Failed on Speech Tier."
                        return
                    else:
                        yield ""  # Invisible Heartbeat packet
                        await asyncio.sleep(2.0)

                # 4. Ultimate English Translation & Restructuring via Groq LLM
                if raw_hindi_text:
                    system_instruction = (
                        "You are an expert educational translator. Translate the following lecture transcript "
                        "into clean, grammatically perfect English prose. Maintain the technical depth of the topic "
                        "(like programming loops, HTML tags, etc.). Output ONLY the translated English text. "
                        "Do not include notes like 'Here is the translation:' or introductory remarks."
                    )
                    translated_english = await groq_llm_layer(system_instruction, raw_hindi_text)
                    
                    # Store globally for chatbot query execution
                    GLOBAL_CONTEXT["latest_transcript"] = translated_english
                    yield translated_english
                else:
                    yield "No audio nodes detected in the submitted file."

        except Exception as e:
            yield f"Pipeline Core Error: {str(e)}"
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(core_processing_streamer(), media_type="text/plain")

@app.post("/api/chat")
async def chat_agent(payload: dict = Body(...)):
    """Handles right-side chat queries intelligently using the active video transcript context"""
    user_query = payload.get("query", "")
    context = GLOBAL_CONTEXT["latest_transcript"]
    
    system_instruction = (
        f"You are a helpful AI classroom teaching assistant. Answer the user's questions strictly based on the "
        f"following translated lecture context provided below.\n\nContext:\n{context}\n\n"
        f"If the answer is not present in the context, use logical educational inference about the core topic "
        f"discussed to provide a perfect guiding answer. Keep the answer brief and professional."
    )
    
    reply = await groq_llm_layer(system_instruction, user_query)
    return {"reply": reply}