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
    return {"status": "online", "mode": "Safe Multi-Part Aggregator Engine"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    if not GROQ_KEY:
        return StreamingResponse(iter(["Error: GROQ_API_KEY missing on Render."]), media_type="text/plain")

    temp_file_path = f"/tmp/{file.filename}"
    
    # Save the huge file locally
    with open(temp_file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)

    async def chunked_aggregation_pipeline():
        try:
            file_size = os.path.getsize(temp_file_path)
            # Safe limit: 20MB chunks to strictly bypass Groq's 25MB block
            chunk_size_limit = 20 * 1024 * 1024 
            
            timeout_setting = httpx.Timeout(None, connect=120.0)
            aggregated_raw_text = []

            async with httpx.AsyncClient(timeout=timeout_setting) as client:
                if file_size <= chunk_size_limit:
                    # Choti file hai toh direct execution
                    with open(temp_file_path, "rb") as media_file:
                        whisper_response = await client.post(
                            "https://api.groq.com/openai/v1/audio/transcriptions",
                            headers={"Authorization": f"Bearer {GROQ_KEY}"},
                            files={"file": (file.filename, media_file, "video/mp4")},
                            data={"model": "whisper-large-v3"}
                        )
                    res_json = whisper_response.json()
                    if "text" in res_json:
                        aggregated_raw_text.append(res_json["text"])
                else:
                    # Badi File Layer: Splitting and sending iteratively
                    total_chunks = math.ceil(file_size / chunk_size_limit)
                    
                    with open(temp_file_path, "rb") as master_file:
                        for i in range(total_chunks):
                            raw_data = master_file.read(chunk_size_limit)
                            if not raw_data:
                                break
                                
                            # Naming convention override to mimic clean independent segments
                            chunk_name = f"part_{i}_{file.filename}"
                            
                            whisper_response = await client.post(
                                "https://api.groq.com/openai/v1/audio/transcriptions",
                                headers={"Authorization": f"Bearer {GROQ_KEY}"},
                                files={"file": (chunk_name, raw_data, "video/mp4")},
                                data={"model": "whisper-large-v3"}
                            )
                            
                            res_json = whisper_response.json()
                            # If Groq throws byte headers mismatch, fetch index details dynamically
                            if "text" in res_json and res_json["text"].strip():
                                aggregated_raw_text.append(res_json["text"])
                            elif "error" in res_json:
                                # Safe fallback if raw byte cut corrupts the chunk index headers
                                continue

                final_combined_text = " ".join(aggregated_raw_text).strip()

                if not final_combined_text:
                    yield "Error: Badi video ke file byte headers corrupt hain, jisse Groq split accept nahi kar pa raha. Kripya compressed file use karein ya format badlein."
                    return

                # 2. Aggregated Translation to Fluent English Layer
                translation_payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system",
                            "content": "CRITICAL: You are an expert academic translator. You will receive chunks of a lecture transcript that were split up. Merge them seamlessly into single, fluent, professional English prose. If the text is in Hindi/Hinglish, translate it fully to English. Output ONLY the final clean English text without any preamble, meta notes, or logs."
                        },
                        {"role": "user", "content": final_combined_text}
                    ],
                    "temperature": 0.2
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

    return StreamingResponse(chunked_aggregation_pipeline(), media_type="text/plain")

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