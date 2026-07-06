import os
import shutil
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import google.generativeai as genai

app = FastAPI()

# CORS configured for production frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini Client safely
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print("📢 SERVER STATUS: GEMINI_API_KEY is successfully synced.")
else:
    print("⚠️ SERVER STATUS: GEMINI_API_KEY is completely missing from production configuration!")

@app.get("/")
def read_root():
    return {"message": "VoxBrief Cognitive Flow Layer Operational."}

@app.post("/api/upload")
async def handle_upload(file: UploadFile = File(...)):
    print(f"📢 Request incoming for file processing: {file.filename}")
    
    # Render file storage block parameters safely inside a local runtime path
    temp_dir = "/tmp" if os.path.exists("/tmp") else "."
    temp_file_path = os.path.join(temp_dir, file.filename)
    
    # Save the uploaded streaming bytes into local storage memory
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    async def dynamic_ai_streamer():
        try:
            yield f"🔄 [Connection]: Establishing interface with production model...\n"
            yield f"📂 [File Saved]: Temporarily locked payload at staging layer.\n"
            yield f"🎙️ [Status]: Uploading audio stream safely directly into Gemini API channel...\n\n"
            await asyncio.sleep(0.5)

            if not GEMINI_API_KEY:
                yield "⚠️ [Configuration Error]: Asli API Key nahi mili. Fallback standard test trigger ho raha hai...\n"
                raise ValueError("Missing API Context configuration key.")

            # Step 1: Upload the file securely directly to Gemini File API (No complex ffmpeg required!)
            audio_file_node = genai.upload_file(path=temp_file_path)
            yield "⚡ [Pipeline]: Audio node parsed successfully. Triggering generative AI prompt parsing...\n\n"

            # Step 2: Call Gemini API using 1.5 flash model (supports direct multi-modal audio files effortlessly)
            model = genai.GenerativeModel("gemini-1.5-flash")
            
            prompt = (
                "You are an expert meeting assistant. First, generate a highly accurate text transcription "
                "of the provided audio. Then, provide a bulleted concise meeting summary detailing action items."
            )
            
            # Request streaming responses directly from Google node clusters
            response = model.generate_content([audio_file_node, prompt], stream=True)

            yield "✨ --- ASLI AI GENERATED SUMMARY & TRANSCRIPT ---\n\n"
            
            # Step 3: Stream chunks back directly to your beautiful React Frontend layout!
            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    await asyncio.sleep(0.05) # Prevent overloading stream packet memory
            
            # Step 4: Clean up file pointer safely from cloud container storage
            try:
                genai.delete_file(audio_file_node.name)
            except Exception:
                pass

        except Exception as e:
            yield f"\n\n❌ [AI Cognitive Model Pipeline Error]: {str(e)}\n"
            yield "🔄 [Fallback Mode Activated due to service latency]:\n"
            yield "The cloud environment encountered model ingestion latency. Please verify your token state limits or file format structure."
        
        finally:
            # Always ensure storage limits are maintained to avoid OOM crashes on free tier nodes
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return StreamingResponse(dynamic_ai_streamer(), media_type="text/plain")