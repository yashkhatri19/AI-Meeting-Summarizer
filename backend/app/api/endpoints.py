import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.llm_service import LLMService
from app.schemas.meeting import QuestionRequest
import google.generativeai as genai

router = APIRouter()
llm_service = LLMService()

# API Key config jo aapne Render par set ki hai
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".webm", ".mp4", ".mpeg", ".opus"}

@router.post("/upload")
async def process_audio(file: UploadFile = File(...)):
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid audio or video format")

    # Render safe temporary path
    temp_dir = "/tmp/voxbrief_storage"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, file.filename)
    
    try:
        # File save karein
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Heavy local Whisper ke bajay direct Gemini multimodal API use karein (Super Fast & Free)
        print("Uploading file to Gemini Flash...")
        audio_file = genai.upload_file(path=temp_file_path)
        
        print("Processing with Gemini...")
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Ek hi shot mein transcription aur summary dono nikal jayegi
        response = model.generate_content([
            audio_file, 
            "Please provide a highly accurate word-for-word transcript first, followed by a clean summary of this meeting."
        ])
        
        full_output = response.text
        
        return {
            "status": "success",
            "transcript": full_output,
            "analysis": "Processed successfully via Gemini Flash Free Tier."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cloud Processing Error: {str(e)}")
    
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@router.post("/ask-question")
async def ask_question_about_transcript(payload: QuestionRequest):
    try:
        if not payload.transcript.strip() or not payload.question.strip():
            raise HTTPException(status_code=400, detail="Fields cannot be empty")
        answer = llm_service.ask_question(payload.transcript, payload.question)
        return {"status": "success", "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))