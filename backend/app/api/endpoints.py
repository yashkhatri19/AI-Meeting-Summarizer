import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.whisper_service import WhisperService
from app.services.llm_service import LLMService
from app.schemas.meeting import QuestionRequest

router = APIRouter()
whisper_service = WhisperService()
llm_service = LLMService()

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".webm", ".mp4", ".mpeg", ".opus"}
ALLOWED_CONTENT_TYPES = {"audio/", "video/mpeg", "video/mp4"}

@router.post("/process")
async def process_audio(file: UploadFile = File(...)):
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    is_valid_type = any(file.content_type.startswith(t) for t in ALLOWED_CONTENT_TYPES) or file.content_type in ALLOWED_CONTENT_TYPES
    
    if file_ext not in ALLOWED_EXTENSIONS and not is_valid_type:
        raise HTTPException(status_code=400, detail="Invalid audio or video format")

    temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/storage"))
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_file_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        transcript = whisper_service.transcribe_audio(temp_file_path)
        analysis = llm_service.analyze_transcript(transcript)
        
        return {
            "status": "success",
            "transcript": transcript,
            "analysis": analysis
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@router.post("/ask-question")
async def ask_question_about_transcript(payload: QuestionRequest):
    try:
        if not payload.transcript.strip() or not payload.question.strip():
            raise HTTPException(status_code=400, detail="Transcript and question cannot be empty")
            
        answer = llm_service.ask_question(payload.transcript, payload.question)
        return {
            "status": "success",
            "answer": answer
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))