from pydantic import BaseModel
from typing import List

class QuestionRequest(BaseModel):
    transcript: str
    question: str
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