import os
import shutil
import zipfile
import tempfile
from hashlib import sha256
from pydantic import BaseModel
from dotenv import load_dotenv
from github_downloder import GitHubDownloader
from fastapi.responses import HTMLResponse, FileResponse
from fastapi import FastAPI, HTTPException, BackgroundTasks


load_dotenv()

app = FastAPI(title="GitHub Directory Downloader", version="1.0.0")

class DownloadRequest(BaseModel):
    url: str
    token: str = None

def cleanup_file(file_path: str):
    """Background task to clean up temporary files"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        print(f"Error cleaning up file {file_path}: {e}")

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    with open("./static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
    
@app.get("/404", response_class=HTMLResponse)
async def serve_frontend():
    with open("./static/404.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/download")
async def download_github_directory(request: DownloadRequest, background_tasks: BackgroundTasks):
    """Download GitHub directory and return as zip file"""
    try:
        github_token_env = os.getenv("GITHUB_TOKEN")
        
        if not github_token_env:
            raise HTTPException(status_code=500, detail="GitHub token not configured on server")
        
        # If token is provided, validate it
        if request.token:
            github_token_hash = sha256(github_token_env.encode('utf-8')).hexdigest()
            if github_token_hash != request.token:
                raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        if not request.url or not request.url.strip():
            raise HTTPException(status_code=400, detail="URL is required")
        
        # Create temporary directory for download
        temp_download_dir = tempfile.mkdtemp()
        download_path = os.path.join(temp_download_dir, "download")
        
        try:
            # Use the actual token for GitHub API
            downloader = GitHubDownloader(github_token_env)
            
            try:
                owner, repo, branch, path = downloader.parse_github_url(request.url)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid GitHub URL: {str(e)}")
            
            print(f"Downloading: {owner}/{repo} (branch: {branch}, path: {path})")
            
            success = downloader.download_directory(owner, repo, path, download_path, branch)
            
            if not success:
                raise HTTPException(status_code=500, detail="Failed to download repository content")
            
            # Check if any files were downloaded
            if not os.path.exists(download_path) or not os.listdir(download_path):
                raise HTTPException(status_code=404, detail="No files found or directory is empty")
            
            # Create zip file in system temp directory
            zip_filename = f"{owner}_{repo}_{path.replace('/', '_') if path else 'root'}.zip"
            zip_path = os.path.join(tempfile.gettempdir(), f"github_dl_{hash(request.url)}_{zip_filename}")
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(download_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, download_path)
                        zipf.write(file_path, arcname)
            
            # Clean up download directory immediately
            shutil.rmtree(temp_download_dir, ignore_errors=True)
            
            # Schedule cleanup of zip file after response is sent
            background_tasks.add_task(cleanup_file, zip_path)
            
            return FileResponse(
                path=zip_path,
                filename=zip_filename,
                media_type='application/zip'
            )
            
        except HTTPException:
            # Clean up on error
            shutil.rmtree(temp_download_dir, ignore_errors=True)
            raise
        except Exception as e:
            # Clean up on error
            shutil.rmtree(temp_download_dir, ignore_errors=True)
            print(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)