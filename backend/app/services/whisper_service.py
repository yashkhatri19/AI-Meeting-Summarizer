import os
from dotenv import load_dotenv
from pydub import AudioSegment
from pydub.utils import which
from groq import Groq
import httpx
import shutil

# Tell pydub exactly where your newly downloaded ffmpeg executable is located
AudioSegment.converter = r"C:\Users\Nihal\AppData\Local\ffmpegio\ffmpeg-downloader\ffmpeg\bin\ffmpeg.exe"
AudioSegment.ffprobe   = r"C:\Users\Nihal\AppData\Local\ffmpegio\ffmpeg-downloader\ffmpeg\bin\ffprobe.exe"
# Load variables from .env
load_dotenv()

class WhisperService:
    def __init__(self):
        # Setup custom client with a 10-minute timeout for large files
        self.custom_client = httpx.Client(timeout=600.0)
        self.client = Groq(
            api_key=os.getenv("GROQ_API_KEY"), 
            http_client=self.custom_client
        )

if shutil.which("ffmpeg"):
    AudioSegment.converter = "ffmpeg"
    AudioSegment.ffprobe = "ffprobe"
else:
    AudioSegment.converter = os.path.abspath("ffmpeg.exe")
    AudioSegment.ffprobe = os.path.abspath("ffprobe.exe")
    
    def transcribe_audio(self, input_file_path: str) -> str:
        from pathlib import Path
        
        # 1. ALWAYS SET PATHS FIRST BEFORE TRYING TO LOAD THE FILE
        CURRENT_DIR = Path(__file__).parent.resolve()
        AudioSegment.converter = str(CURRENT_DIR / "ffmpeg.exe")
        AudioSegment.ffprobe = str(CURRENT_DIR / "ffprobe.exe")

        compressed_audio_path = "temp_compressed_audio.mp3"
        # Check if the input file exists
        try:
            print("Compressing file to fit under Groq's 25MB limit...")
            # Load the video/audio file
            audio = AudioSegment.from_file(input_file_path)
            
            # Export to low bitrate MP3 (keeps 30 mins under ~15MB)cd
            audio.export(compressed_audio_path, format="mp3", bitrate="64k")
            print("Compression complete. Uploading to Groq...")

            AudioSegment.converter = os.path.abspath("ffmpeg.exe")
            AudioSegment.ffprobe = os.path.abspath("ffprobe.exe")
            
            # Send to Groq for translation
            with open(compressed_audio_path, "rb") as file_to_send:
                response = self.client.audio.transcriptions.create(
                    file=file_to_send,
                    model="whisper-large-v3",
                    language="en"
                )
            return response.text

        except Exception as e:
            print(f"Error inside WhisperService: {str(e)}")
            raise e
            
        finally:
            # Always clean up the temporary file
            if os.path.exists(compressed_audio_path):
                os.remove(compressed_audio_path)