import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import google.generativeai as genai

router = APIRouter()

# Server start hote hi check karega
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
print(f"📢 SERVER STATUS: GEMINI_API_KEY is {'CONFIGURED' if GEMINI_API_KEY else 'MISSING 🔴'}")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

@router.post("/upload")
async def process_audio(file: UploadFile = File(...)):
    # Agar key nahi hai toh frontend ko 400 error do taaki pata chale
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(status_code=400, detail="Backend error: GEMINI_API_KEY is not set in Render Dashboard Environment Variables!")
    
    temp_file_path = f"/tmp/meeting_{file.filename}"
    try:
        # File save block
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        if not os.path.exists(temp_file_path) or os.path.getsize(temp_file_path) == 0:
            raise HTTPException(status_code=500, detail="Failed to write file to server storage.")

        # Upload to Gemini
        try:
            gemini_file = genai.upload_file(path=temp_file_path)
        except Exception as upload_err:
            raise HTTPException(status_code=500, detail=f"Google API Upload Failed: {str(upload_err)}")

        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = "You are an expert meeting assistant. Provide a detailed summary and actionable items from this file."

        async def response_generator():
            try:
                response_stream = model.generate_content([gemini_file, prompt], stream=True)
                for chunk in response_stream:
                    if chunk.text:
                        yield chunk.text
                
                # Cleanup
                try:
                    genai.delete_file(gemini_file.name)
                except:
                    pass
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except Exception as stream_err:
                yield f"\n[Stream Error: {str(stream_err)}]"

        return StreamingResponse(response_generator(), media_type="text/plain")

    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Server Exception: {str(e)}")