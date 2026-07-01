import json
import httpx
from groq import Groq
from app.core.config import settings

class LLMService:
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY, http_client=httpx.Client())

    def analyze_transcript(self, transcript_text: str) -> dict:
        prompt = (
            "You are an expert meeting assistant. Analyze the following meeting transcript. "
            "You must return the response strictly as a valid JSON object matching this schema:\n"
            "{\n"
            "  \"summary\": \"A short high-level overview of the meeting\",\n"
            "  \"key_takeaways\": [\"point 1\", \"point 2\"],\n"
            "  \"action_items\": [\n"
            "    {\"task\": \"task description\", \"owner\": \"person name or Unassigned\", \"deadline\": \"date/time or TBD\"}\n"
            "  ]\n"
            "}\n"
            "Do not include any prose, markdown block, introduction, or conversation before or after the JSON. "
            f"Transcript:\n{transcript_text}"
        )

        response = self.client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"},
            temperature=0.2
        )

        raw_content = response.choices[0].message.content
        return json.loads(raw_content)
    
    def ask_question(self, transcript_text: str, question: str) -> str:
        # Upgraded Analytical Prompt Setup
        prompt = (
            "You are VoxBrief AI, an advanced cognitive meeting analyst helping a user with a meeting transcript.\n\n"
            f"Here is the context channel (Meeting Transcript):\n###\n{transcript_text}\n###\n\n"
            "Behavioral Guidelines for Answering:\n"
            "1. Analyze the text carefully. If the user asks quantitative or analytical queries "
            "(e.g., 'how many times was a word used?', 'count of a specific word', presence of a phrase), "
            "manually calculate or count the occurrence within the transcript and provide a precise response.\n"
            "2. If the requested word or topic is explicitly mentioned or can be directly deduced from the text, answer it confidently based on the context.\n"
            "3. Strictly state 'I cannot find the answer in the provided transcript.' ONLY if the topic, word, or context is completely non-existent or impossible to infer from the text. Do not make up facts.\n"
            "4. Keep the output straightforward, helpful, and concise.\n\n"
            f"Question: {question}"
        )

        response = self.client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.3
        )

        return response.choices[0].message.content