import os
import time
import shutil
import json
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from PIL import Image
import io

# Configuration
MAX_IMAGE_SIZE = 50 * 1024  # 50KB

# Use Render's tmp directory if available, otherwise default to local directory
if os.environ.get('RENDER'):
    UPLOAD_DIR = "/tmp/uploads"
else:
    UPLOAD_DIR = "uploads"

PENDING_DIR = os.path.join(UPLOAD_DIR, "pending")
PROCESSED_DIR = os.path.join(UPLOAD_DIR, "processed")

# Create directories if they don't exist
os.makedirs(PENDING_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

app = FastAPI(title="ESP32 File Upload Server")

# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

# File metadata model
class FileInfo(BaseModel):
    name: str
    size: int
    path: str
    type: str
    uploaded_at: float
    status: str  # "pending" or "processed"


# In-memory storage for file metadata
file_db = []


# Helper functions
def is_image_file(filename: str) -> bool:
    """Check if file is an image based on extension"""
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
    ext = os.path.splitext(filename)[1].lower()
    return ext in image_extensions


def is_audio_file(filename: str) -> bool:
    """Check if file is an audio file based on extension"""
    audio_extensions = ['.mp3', '.wav', '.ogg', '.aac', '.flac']
    ext = os.path.splitext(filename)[1].lower()
    return ext in audio_extensions


def save_file_info(file_info: FileInfo):
    """Save file info to our in-memory database"""
    file_db.append(file_info)
    # Keep the list from growing too large
    if len(file_db) > 100:
        file_db.pop(0)
        

def convert_to_baseline_jpeg(file_path):
    """Convert any image to a baseline JPEG compatible with ESP32 and resize to 320x480px"""
    try:
        # Open the image
        img = Image.open(file_path)
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize the image to 320x480px
        img = img.resize((320, 480), Image.LANCZOS)
        
        # Create a new file path with standard name
        base_path = os.path.dirname(file_path)
        new_path = os.path.join(base_path, "image.jpg")
        
        # Save as baseline JPEG with settings compatible with ESP32
        img.save(new_path, 
                format="JPEG", 
                quality=85, 
                optimize=False, 
                progressive=False, 
                subsampling=0)  # 4:4:4 chroma subsampling
        
        # If this isn't the original path, remove the original file
        if new_path != file_path:
            os.remove(file_path)
            
        print(f"Converted and resized image saved to {new_path}")
        return new_path
    except Exception as e:
        print(f"Error converting image: {e}")
        return file_path


def mark_as_processed(file_path: str):
    """Mark a file as processed in our DB and move it to processed folder"""
    for file_info in file_db:
        if file_info.path == file_path:
            file_info.status = "processed"
            
            # Move file to processed directory
            filename = os.path.basename(file_path)
            new_path = os.path.join(PROCESSED_DIR, filename)
            if os.path.exists(file_path):
                shutil.move(file_path, new_path)
                file_info.path = new_path
                
                save_file_info(file_info)  # Save updated info
                

def delete_existing_images():
    """Delete all image files from pending and processed directories"""
    # Delete from pending directory
    for filename in os.listdir(PENDING_DIR):
        filepath = os.path.join(PENDING_DIR, filename)
        if os.path.isfile(filepath) and is_image_file(filename):
            try:
                os.remove(filepath)
                print(f"Deleted existing image: {filepath}")
            except Exception as e:
                print(f"Error deleting {filepath}: {e}")
    
    # Delete from processed directory
    for filename in os.listdir(PROCESSED_DIR):
        filepath = os.path.join(PROCESSED_DIR, filename)
        if os.path.isfile(filepath) and is_image_file(filename):
            try:
                os.remove(filepath)
                print(f"Deleted existing image: {filepath}")
            except Exception as e:
                print(f"Error deleting {filepath}: {e}")

def clear_image_metadata():
    """Remove all image files from the metadata database"""
    global file_db
    # Keep only non-image files
    file_db = [f for f in file_db if f.type != "image"]
                
                
def save_file_info(file_info: FileInfo):
    file_db.append(file_info)
    # Keep the list from growing too large
    if len(file_db) > 100:
        file_db.pop(0)
        
    # Persist metadata to a file
    try:
        metadata_path = os.path.join(UPLOAD_DIR, "metadata.json")
        with open(metadata_path, "w") as f:
            # Convert FileInfo objects to dictionaries
            metadata = [
                {
                    "name": item.name,
                    "size": item.size,
                    "path": item.path,  # Include the path
                    "type": item.type,
                    "uploaded_at": item.uploaded_at,
                    "status": item.status
                }
                for item in file_db
            ]
            json.dump(metadata, f)
    except Exception as e:
        print(f"Error persisting metadata: {e}")
        
        
def load_persisted_metadata():
    try:
        metadata_path = os.path.join(UPLOAD_DIR, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
                global file_db
                file_db = [
                    FileInfo(
                        name=item["name"],
                        size=item["size"],
                        path=item['path'],
                        type=item["type"],
                        uploaded_at=item["uploaded_at"],
                        status=item["status"]
                    )
                    for item in metadata
                ]
                print(f"Loaded {len(file_db)} file records from persistent storage")
    except Exception as e:
        print(f"Error loading metadata: {e}")
        # initialize with empty list if we can't load
        file_db = []


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page"""
    with open("static/index.html", "r") as f:
        return f.read()


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Handle file uploads from the web interface"""
    filename = file.filename
    
    # Validate file type
    if not (is_image_file(filename) or is_audio_file(filename)):
        raise HTTPException(status_code=400, detail="File must be an image or audio file")
    
    # Create full file path
    file_path = os.path.join(PENDING_DIR, filename)
    
    # For images, check size limit and delete any existing image files
    if is_image_file(filename):
        contents = await file.read()
        if len(contents) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=400, detail=f"Image size exceeds {MAX_IMAGE_SIZE/1024}KB limit")
        
        # Delete any existing image files
        delete_existing_images()
        
        # Write the file
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Convert to ESP32-compatible format and get new path
        # This always saves as "image.jpg" in the same directory
        file_path = convert_to_baseline_jpeg(file_path)
        filename = os.path.basename(file_path)  # Will always be "image.jpg"
    else:
        # For audio files, stream directly to disk
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    
    file_size = os.path.getsize(file_path)
    file_type = "image" if is_image_file(filename) else "audio"
    
    # Clear existing files from metadata
    if file_type == "image":
        clear_image_metadata()
    
    # Create and save file info
    file_info = FileInfo(
        name=filename,
        size=file_size,
        path=file_path,
        type=file_type,
        uploaded_at=time.time(),
        status="pending"
    )
    save_file_info(file_info)
    
    return {"filename": filename, "size": file_size, "status": "success"}


@app.get("/files")
async def list_files():
    """List all uploaded files with their metadata"""
    # Return only essential info for the frontend
    return [
        {
            "name": f.name,
            "size": f.size,
            "type": f.type,
            "uploaded_at": f.uploaded_at,
            "status": f.status
        }
        for f in file_db
    ]


@app.get("/esp/next-file")
async def get_next_file_for_esp(background_tasks: BackgroundTasks):
    """Endpoint for ESP32 to poll for new files to download"""
    # Find the oldest pending file
    pending_files = [f for f in file_db if f.status == "pending"]
    
    if not pending_files:
        return {"status": "no_files"}
    
    # Sort by upload time (oldest first)
    pending_files.sort(key=lambda x: x.uploaded_at)
    next_file = pending_files[0]
    
    # After ESP32 downloads the file, mark it as processed
    # We use background_tasks so this runs after the response is sent
    background_tasks.add_task(mark_as_processed, next_file.path)
    
    return {
        "status": "file_ready",
        "filename": next_file.name,
        "size": next_file.size,
        "type": next_file.type,
        "download_url": f"/esp/download/{next_file.name}"
    }


@app.get("/esp/download/{filename}")
async def download_file(filename: str):
    """Endpoint for ESP32 to download a specific file"""
    file_path = os.path.join(PENDING_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )
    
    
@app.get("/download/{filename}")
async def download_public_file(filename: str):
    """Public endpoint to download a file by filename"""
    # Check both pending and processed directories
    pending_path = os.path.join(PENDING_DIR, filename)
    processed_path = os.path.join(PROCESSED_DIR, filename)
    
    if os.path.exists(pending_path):
        file_path = pending_path
    elif os.path.exists(processed_path):
        file_path = processed_path
    else:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine content type based on file extension
    content_type = "application/octet-stream"  # Default
    if is_image_file(filename):
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.jpg', '.jpeg']:
            content_type = "image/jpeg"
        elif ext == '.png':
            content_type = "image/png"
        elif ext == '.gif':
            content_type = "image/gif"
        elif ext == '.bmp':
            content_type = "image/bmp"
    elif is_audio_file(filename):
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.mp3':
            content_type = "audio/mpeg"
        elif ext == '.wav':
            content_type = "audio/wav"
        elif ext == '.ogg':
            content_type = "audio/ogg"
        elif ext == '.aac':
            content_type = "audio/aac"
        elif ext == '.flac':
            content_type = "audio/flac"
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=content_type
    )


@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    print(f"Server started. Upload directory: {UPLOAD_DIR}")
    print(f"Maximum image size: {MAX_IMAGE_SIZE/1024}KB")
    # Load persisted metadata if available
    load_persisted_metadata()
    

@app.get("/admin/files-debug")
async def debug_file_system():
    """Endpoint to debug the file system and see what's in the uploads directory"""
    result = {
        "tmp_exists": os.path.exists("/tmp"),
        "upload_dir_exists": os.path.exists(UPLOAD_DIR),
        "pending_dir_exists": os.path.exists(PENDING_DIR),
        "processed_dir_exists": os.path.exists(PROCESSED_DIR),
        "pending_files": [],
        "processed_files": [],
        "metadata_exists": os.path.exists(os.path.join(UPLOAD_DIR, "metadata.json")),
    }
    
    # List files in pending directory
    if os.path.exists(PENDING_DIR):
        result["pending_files"] = os.listdir(PENDING_DIR)
    
    # List files in processed directory
    if os.path.exists(PROCESSED_DIR):
        result["processed_files"] = os.listdir(PROCESSED_DIR)
    
    # Add file sizes
    result["pending_sizes"] = {}
    for file in result["pending_files"]:
        file_path = os.path.join(PENDING_DIR, file)
        if os.path.isfile(file_path):
            result["pending_sizes"][file] = os.path.getsize(file_path)
    
    return result


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)