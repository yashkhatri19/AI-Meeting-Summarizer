from pydantic import BaseModel
from typing import List,Optional

class QuestionRequest(BaseModel):
    transcript: str
    question: str
    email: Optional[str] = None  # Optional email field for user context
# Request model for submitting a question about the meeting transcript
class ActionItem(BaseModel):
    task: str
    owner: str
    deadline: str

class MeetingAnalysisResponse(BaseModel):
    id: str
    summary: str
    key_takeaways: List[str]
    action_items: List[ActionItem]
