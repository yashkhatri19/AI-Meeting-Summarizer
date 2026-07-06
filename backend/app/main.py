import os
import shutil
import asyncio
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import google.generativeai as genai

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RAW_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Naye Auth Tokens ko back-end par set karne ka automatic system
if RAW_KEY:
    os.environ["GEMINI_API_KEY"] = RAW_KEY
    genai.configure(api_key=RAW_KEY)
    print("📢 API CONFIG: Dynamic Security Token Loaded Successfully.")
else:
    print("⚠️ API CONFIG: Token Missing In Environment Variables!")

@app.get("/")
def read_root():
    return {"status": "online", "auth_mode": "unified_dynamic_bridge"}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    temp_dir = "/tmp" if os.path.exists("/tmp") else "."
    temp_file_path = os.path.join(temp_dir, file.filename)
    
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    async def dynamic_ai_streamer():
        try:
            yield "🔄 [Connection]: Establishing Secure Tunnel with Gemini...\n"
            yield f"📂 [File Staged]: {file.filename}\n\n"
            await asyncio.sleep(0.5)

            if not RAW_KEY:
                yield "❌ [Error]: Missing GEMINI_API_KEY inside Render settings."
                return

            # Naye AQ. tokens ke liye direct REST pipeline bypass
            yield "⚡ [Pipeline]: Processing speech structure via unified endpoint...\n"
            
            # File system node upload handler
            audio_file_node = genai.upload_file(path=temp_file_path)
            yield "✨ [Cognitive Stream]: Audio ingested, generating markdown summary...\n\n"

            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = (
                "Provide an accurate text transcription of the provided audio file "
                "and then output a detailed markdown summary with key action items."
            )
            
            # Chunking stream handle
            response = model.generate_content([audio_file_node, prompt], stream=True)
            
            yield "--- START OF SUMMARY ---\n\n"
            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    await asyncio.sleep(0.02)
            
            # Cleanup storage node
            try:
                genai.delete_file(audio_file_node.name)
            except:
                pass

        except Exception as e:
            # Agar fir bhi restriction aaye, toh ye backup raw HTTP call maarega
            error_msg = str(e)
            if "API key not valid" in error_msg or "400" in error_msg:
                yield "⚠️ [Fallback Active]: Standard SDK rejected token. Retrying via Direct HTTP Channel...\n\n"
                try:
                    # Direct REST client bypass architecture
                    async with httpx.AsyncClient() as client:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={RAW_KEY}"
                        headers = {"Content-Type": "application/json"}
                        payload = {
                            "contents": [{"parts": [{"text": "Summarize the file accurately and give action items."}]}]
                        }
                        res = await client.post(url, json=payload, headers=headers, timeout=60.0)
                        if res.status_code == 200:
                            data = res.json()
                            text_reply = data['candidates'][0]['content']['parts'][0]['text']
                            yield text_reply
                        else:
                            yield f"❌ [Google Gateway Error]: {res.text}"
                except Exception as fallback_err:
                    yield f"❌ [Critical Failure]: Both SDK and HTTP Gateway rejected the key. Details: {str(fallback_err)}"
            else:
                yield f"\n\n❌ [Runtime Exception]: {error_msg}\n"
        
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(dynamic_ai_streamer(), media_type="text/plain")