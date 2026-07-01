import os
import shutil
from fastapi import UploadFile

class FileHandler:
    @staticmethod
    def save_temp_file(upload_file: UploadFile, target_dir: str) -> str:
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, upload_file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
            
        return file_path

    @staticmethod
    def delete_file(file_path: str):
        if os.path.exists(file_path):
            os.remove(file_path)