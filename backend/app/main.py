from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router

app = FastAPI(title="VoxBrief AI API", version="1.0.0")

# Sabhi frontend errors aur CORS policy blocks ko bypass karne ke liye single clean middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production mein '*' karne se Vercel ke saare links bina kisi restriction ke chalenge
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Explicitly '/api' prefix set kiya hai taaki frontend ki '/api/upload' request kaam kare
app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "project": "VoxBrief AI Meeting Summarizer",
        "message": "Welcome to the backend server!"
    }