let DIR_DL_TOKEN = localStorage.getItem("DIR_DL_TOKEN") || null;

let isTokenValid = false;

while (!isTokenValid && !DIR_DL_TOKEN) {
  const resp = window.prompt("Enter GitHub Token:");

  if (!resp || resp.length <= 10) {
    alert("Invalid token. Please enter a valid GitHub token.");
  } else {
    DIR_DL_TOKEN = resp;
    localStorage.setItem("DIR_DL_TOKEN", DIR_DL_TOKEN);
    isTokenValid = true;
  }
}

const logElement = document.querySelector("#log");
const reloadBtn = document.querySelector("#reload");
const inputField = document.querySelector("#input-field");
const downloadBtn = document.querySelector("#download-btn");

function log(text, type = "info") {
  logElement.className = `log-${type}`;
  logElement.textContent = text;
}

async function downloadContent() {
  const url = inputField.value.trim();
  
  if (!url) {
    log("Please enter a GitHub repository or directory URL", "error");
    return;
  }

  try {
    log("Parsing URL...", "info");
    const { owner, repo, path, isRepo } = parseGitHubUrl(url);
    
    log("Fetching directory contents...", "info");
    downloadBtn.disabled = true;
    
    const files = await fetchDirectoryContents(owner, repo, path);
    
    if (files.length === 0) {
      log("No files found in the directory", "error");
      return;
    }
    
    log(`Found ${files.length} files. Creating ZIP...`, "info");
    const folderName = isRepo ? repo : `${repo}-${path.split('/').pop() || 'root'}`;
    await createAndDownloadZip(files, folderName, owner, repo);
    
    log("Download completed successfully!", "success");
    
  } catch (error) {
    console.error("Download failed:", error);
    log(`Download failed: ${error.message}`, "error");
  } finally {
    downloadBtn.disabled = false;
  }
}

function parseGitHubUrl(url) {
  url = url.replace(/\/$/, '');
  
  const repoRegex = /github\.com\/([^\/]+)\/([^\/]+)$/;
  const repoMatch = url.match(repoRegex);
  
  if (repoMatch) {
    const [, owner, repo] = repoMatch;
    return { owner, repo, path: '', isRepo: true };
  }
  
  const dirRegex = /github\.com\/([^\/]+)\/([^\/]+)\/tree\/[^\/]+\/?(.*)/;
  const dirMatch = url.match(dirRegex);
  
  if (dirMatch) {
    const [, owner, repo, path] = dirMatch;
    return { owner, repo, path: path || '', isRepo: false };
  }
  
  throw new Error("Invalid GitHub URL. Please enter a repository URL (github.com/owner/repo) or directory URL (github.com/owner/repo/tree/branch/path)");
}

async function fetchDirectoryContents(owner, repo, path, allFiles = []) {
  const apiUrl = `https://api.github.com/repos/${owner}/${repo}/contents/${path}`;
  
  const response = await fetch(apiUrl, {
    headers: {
      'Authorization': `Bearer ${DIR_DL_TOKEN}`,
      'Accept': 'application/vnd.github.v3+json'
    }
  });
  
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Invalid GitHub token or insufficient permissions");
    } else if (response.status === 404) {
      throw new Error("Repository or directory not found");
    } else {
      throw new Error(`GitHub API error: ${response.status} - ${response.statusText}`);
    }
  }
  
  const contents = await response.json();
  
  for (const item of contents) {
    if (item.type === 'file') {
      allFiles.push({
        path: item.path,
        sha: item.sha,
        name: item.name,
        size: item.size
      });
    } else if (item.type === 'dir') {
      await fetchDirectoryContents(owner, repo, item.path, allFiles);
    }
  }
  
  return allFiles;
}

async function createAndDownloadZip(files, folderName, owner, repo) {
  if (typeof JSZip === 'undefined') {
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';
    document.head.appendChild(script);
    
    await new Promise((resolve, reject) => {
      script.onload = resolve;
      script.onerror = () => reject(new Error("Failed to load JSZip library"));
    });
  }
  
  try {
    const zip = new JSZip();
    // logs = 
    
    let downloadedCount = 0;
    const totalFiles = files.length;
    let successfulDownloads = 0;
    
    for (const file of files) {
      try {
        log(`Downloading ${file.name} (${downloadedCount + 1}/${totalFiles})...`, "info");
        
        const apiUrl = `https://api.github.com/repos/${owner}/${repo}/contents/${file.path}`;
        const response = await fetch(apiUrl, {
          headers: {
            'Authorization': `Bearer ${DIR_DL_TOKEN}`,
            'Accept': 'application/vnd.github.v3+json'
          }
        });
        
        if (!response.ok) {
          throw new Error(`Failed to fetch ${file.name}: ${response.status}`);
        }
        
        const fileData = await response.json();
        
        if (fileData.content) {
          const binaryString = atob(fileData.content.replace(/\n/g, ''));
          const bytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }
          
          zip.file(file.path, bytes);
          successfulDownloads++;
        } else {
          console.warn(`No content found for ${file.name}`);
        }
        
        downloadedCount++;
        
      } catch (error) {
        console.warn(`Failed to download ${file.name}:`, error);
      }
    }
    
    if (successfulDownloads === 0) {
      throw new Error("No files were successfully downloaded");
    }
    
    log(`Generating ZIP file with ${successfulDownloads} files...`, "info");
    const zipBlob = await zip.generateAsync({ 
      type: "blob",
      compression: "DEFLATE",
      compressionOptions: {
        level: 6
      }
    });
    
    if (zipBlob.size === 0) {
      throw new Error("Generated ZIP file is empty");
    }
    
    const link = document.createElement('a');
    link.href = URL.createObjectURL(zipBlob);
    link.download = `${folderName}.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    URL.revokeObjectURL(link.href);
    
    log(`ZIP created successfully! Size: ${(zipBlob.size / 1024 / 1024).toFixed(2)} MB`, "success");
    
  } catch (error) {
    throw error;
  }
}

downloadBtn.addEventListener("click", downloadContent);

reloadBtn.addEventListener("click", () => {
  DIR_DL_TOKEN = null;
  localStorage.removeItem("DIR_DL_TOKEN");
  location.reload();
});