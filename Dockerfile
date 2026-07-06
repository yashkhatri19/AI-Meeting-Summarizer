FROM python:3.10-slim

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ab hum bahar se backend folder ko target karenge
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pura backend ka code copy karein
COPY backend/ .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]