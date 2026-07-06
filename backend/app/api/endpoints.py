import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import google.generativeai as genai

router = APIRouter()

# Gemini Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

@router.post("/upload")
async def process_audio(file: UploadFile = File(...)):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API Key is not configured on the server.")
    
    # 1. Temporary local file save karna (Gemini API ko path dene ke liye)
    temp_file_path = f"/tmp/{file.filename}"
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"📦 File locally saved at: {temp_file_path}")

        # 2. Direct Gemini API par file upload karna (No FFmpeg Needed!)
        print("🚀 Uploading file directly to Gemini API...")
        gemini_file = genai.upload_file(path=temp_file_path)
        print(f"✅ Gemini upload success! File URI: {gemini_file.uri}")

        # 3. Model initialized karna (Gemini 1.5 Flash video/audio dono handle karta hai)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = (
            "You are an expert meeting assistant. Analyze the provided audio/video file carefully. "
            "First, generate a comprehensive, well-structured transcript of the entire conversation. "
            "Then, provide a detailed summary, highlighting key action items, important decisions, and next steps."
        )

        # 4. Response ko stream karna taaki UI par real-time text dikhe
        async def response_generator():
            try:
                response_stream = model.generate_content([gemini_file, prompt], stream=True)
                for chunk in response_stream:
                    if chunk.text:
                        yield chunk.text
                
                # Processing ke baad Gemini cloud se file delete karna (Clean up)
                genai.delete_file(gemini_file.name)
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    
            except Exception as stream_err:
                print("🔴 Streaming Error:", str(stream_err))
                yield f"\n[Streaming Error: {str(stream_err)}]"

        return StreamingResponse(response_generator(), media_type="text/plain")

    except Exception as e:
        print("🔴 ASLI ERROR YAHAN HAI NEW METHOD MEIN:", str(e))
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"New Method Processing Error: {str(e)}")