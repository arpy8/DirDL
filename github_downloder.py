import os
import sys
import base64
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()


class GitHubDownloader:
    def __init__(self, token):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.av3+json'
        })
    
    def parse_github_url(self, url):
        """Parse GitHub directory URL to extract owner, repo, and path"""
        if 'github.com' in url:
            parts = url.replace('https://github.com/', '').split('/')
            if len(parts) < 2:
                raise ValueError("Invalid GitHub URL format")
            
            owner = parts[0]
            repo = parts[1]
            
            if len(parts) > 2 and parts[2] == 'tree':
                branch = parts[3] if len(parts) > 3 else 'main'
                path = '/'.join(parts[4:]) if len(parts) > 4 else ''
            else:
                branch = 'main'
                path = '/'.join(parts[2:]) if len(parts) > 2 else ''
        else:
            raise ValueError("URL must be a GitHub repository URL")
        
        return owner, repo, branch, path
    
    def download_file(self, file_info, local_path):
        """Download a single file"""
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            if file_info['size'] == 0:
                Path(local_path).touch()
                print(f"Created empty file: {local_path}")
                return True
            
            if 'download_url' not in file_info:
                print(f"Error: No download URL available for {local_path}")
                return False
            
            if file_info['size'] > 1024 * 1024 or 'content' not in file_info:
                response = self.session.get(file_info['download_url'])
                if response.status_code == 200:
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                    print(f"Downloaded: {local_path}")
                    return True
                else:
                    print(f"Error: Failed to download {local_path}, status code: {response.status_code}")
                    return False
            else:
                try:
                    content = base64.b64decode(file_info['content'])
                    with open(local_path, 'wb') as f:
                        f.write(content)
                    print(f"Downloaded: {local_path}")
                    return True
                except Exception as decode_error:
                    print(f"Error decoding content for {local_path}: {str(decode_error)}")
                    response = self.session.get(file_info['download_url'])
                    if response.status_code == 200:
                        with open(local_path, 'wb') as f:
                            f.write(response.content)
                        print(f"Downloaded (fallback): {local_path}")
                        return True
                    return False
            
        except Exception as e:
            print(f"Error downloading {local_path}: {str(e)}")
            return False
    
    def get_directory_contents(self, owner, repo, path, branch='main'):
        """Get contents of a directory from GitHub API"""
        api_url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'
        if branch != 'main':
            api_url += f'?ref={branch}'
        
        try:
            response = self.session.get(api_url)
            
            if response.status_code == 404:
                print(f"Error: Directory not found or no access permissions for path: {path}")
                return None
            elif response.status_code == 403:
                print(f"Error: Rate limit exceeded or insufficient permissions")
                return None
            elif response.status_code != 200:
                print(f"Error: GitHub API returned status {response.status_code}")
                print(f"Response: {response.text}")
                return None
            
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request to GitHub API: {str(e)}")
            return None
    
    def download_directory(self, owner, repo, remote_path, local_path, branch='main'):
        """Recursively download directory contents"""
        contents = self.get_directory_contents(owner, repo, remote_path, branch)
        
        if contents is None:
            return False
        
        if not isinstance(contents, list):
            print(f"Error: Expected directory but got file at {remote_path}")
            return False
        
        success = True
        for item in contents:
            item_name = item['name']
            item_local_path = os.path.join(local_path, item_name)
            
            if item['type'] == 'file':
                if not self.download_file(item, item_local_path):
                    success = False
            elif item['type'] == 'dir':
                item_remote_path = f"{remote_path}/{item_name}" if remote_path else item_name
                if not self.download_directory(owner, repo, item_remote_path, item_local_path, branch):
                    success = False
        
        return success


def main():
    parser = argparse.ArgumentParser(description='Download GitHub directory using API token')
    parser.add_argument('url', help='GitHub directory URL')
    parser.add_argument('-o', '--output', default='./downloaded', 
                       help='Output directory (default: ./downloaded)')
    
    args = parser.parse_args()
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN environment variable not set")
        print("Please set your GitHub token in a .env file or as an environment variable")
        sys.exit(1)
    
    try:
        downloader = GitHubDownloader(GITHUB_TOKEN)
        owner, repo, branch, path = downloader.parse_github_url(args.url)
        
        print(f"Repository: {owner}/{repo}")
        print(f"Branch: {branch}")
        print(f"Path: {path}")
        print(f"Output directory: {args.output}")
        print("-" * 50)
        
        os.makedirs(args.output, exist_ok=True)
        success = downloader.download_directory(owner, repo, path, args.output, branch)
        
        if success:
            print("-" * 50)
            print("Download completed successfully!")
        else:
            print("-" * 50)
            print("Download completed with some errors.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("GitHub Directory Downloader")
        print("Usage: python github_downloader.py <github_url> <token> [-o output_dir]")
        print("\nExample:")
        print("python github_downloader.py https://github.com/owner/repo/tree/main/src ghp_xxxxxxxxxxxx -o ./my_download")
        print("\nOr set your token and URL here:")
        
        GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
        GITHUB_URL = "https://github.com/owner/repo/tree/main/directory"
        OUTPUT_DIR = "./downloaded"
        
        if GITHUB_TOKEN == "your_github_token_here":
            print("Please set your GitHub token and URL in the script or use command line arguments.")
            sys.exit(1)
        
        try:
            downloader = GitHubDownloader(GITHUB_TOKEN)
            owner, repo, branch, path = downloader.parse_github_url(GITHUB_URL)
            
            print(f"Downloading from: {owner}/{repo}/{path}")
            success = downloader.download_directory(owner, repo, path, OUTPUT_DIR, branch)
            
            if success:
                print("Download completed!")
            else:
                print("Download completed with errors.")
        except Exception as e:
            print(f"Error: {str(e)}")
    else:
        main()