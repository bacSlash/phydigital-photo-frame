// HEARTH ESP32 File Upload System - Enhanced JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize the application
    initApp();
    
    // Fetch file list on page load
    fetchFileList();
    
    // Add event listeners to form
    setupEventListeners();
});

function initApp() {
    // Enhanced file input styling
    const fileInputs = document.querySelectorAll('.file-input');
    
    fileInputs.forEach(input => {
        const container = input.parentElement;
        const fileType = input.accept.includes('image') ? 'image' : 'audio';
        
        // Create custom file upload element
        const customUpload = document.createElement('div');
        customUpload.className = 'custom-file-upload';
        customUpload.innerHTML = `
            <strong>Choose ${fileType} file</strong>
            <span>or drag and drop here</span>
        `;
        
        // Hide the original input but keep it functional
        input.style.opacity = 0;
        input.style.position = 'absolute';
        input.style.top = 0;
        input.style.left = 0;
        input.style.width = '100%';
        input.style.height = '100%';
        input.style.zIndex = 2;
        
        // Add the custom element
        container.style.position = 'relative';
        container.appendChild(customUpload);
        
        // Update custom element text when file is selected
        input.addEventListener('change', function() {
            if (this.files.length > 0) {
                const fileName = this.files[0].name;
                customUpload.innerHTML = `
                    <strong>Selected: ${fileName}</strong>
                    <span>Click to change</span>
                `;
            } else {
                customUpload.innerHTML = `
                    <strong>Choose ${fileType} file</strong>
                    <span>or drag and drop here</span>
                `;
            }
        });
        
        // Add drag and drop functionality
        setupDragAndDrop(container, input, customUpload);
    });
    
    // Try to load the most recent image to the frame
    loadRecentImage();
}

function setupDragAndDrop(container, input, customEl) {
    // Add drag & drop events
    container.addEventListener('dragover', function(e) {
        e.preventDefault();
        e.stopPropagation();
        customEl.style.backgroundColor = '#e9e9e9';
        customEl.style.borderColor = '#999';
    });
    
    container.addEventListener('dragleave', function(e) {
        e.preventDefault();
        e.stopPropagation();
        customEl.style.backgroundColor = '#f5f5f5';
        customEl.style.borderColor = '#ddd';
    });
    
    container.addEventListener('drop', function(e) {
        e.preventDefault();
        e.stopPropagation();
        customEl.style.backgroundColor = '#f5f5f5';
        customEl.style.borderColor = '#ddd';
        
        if (e.dataTransfer.files.length) {
            input.files = e.dataTransfer.files;
            
            // Trigger change event
            const event = new Event('change');
            input.dispatchEvent(event);
        }
    });
}

function setupEventListeners() {
    const uploadForm = document.getElementById('uploadForm');
    
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const imageFile = document.getElementById('imageFile').files[0];
        const soundFile = document.getElementById('soundFile').files[0];
        const uploadStatus = document.getElementById('uploadStatus');
        const uploadProgress = document.getElementById('uploadProgress');
        
        // Check if either file is selected
        if (!imageFile && !soundFile) {
            showStatus('error', 'Please select at least one file to upload.');
            return;
        }
        
        // Check image file size (50KB limit)
        if (imageFile && imageFile.size > 50 * 1024) {
            showStatus('error', 'Image file size exceeds the 50KB limit.');
            return;
        }
        
        // Create FormData
        const formData = new FormData();
        if (imageFile) formData.append('file', imageFile);
        if (soundFile) formData.append('file', soundFile);
        
        // Show progress bar with animation
        uploadProgress.style.display = 'block';
        uploadProgress.value = 0;
        
        try {
            // Upload the file(s)
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/upload');
            
            xhr.upload.onprogress = function(e) {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    uploadProgress.value = percentComplete;
                }
            };
            
            xhr.onload = function() {
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    showStatus('success', 'Files uploaded successfully!');
                    
                    // If an image was uploaded, update the frame
                    if (imageFile) {
                        setTimeout(() => {
                            loadRecentImage();
                        }, 1000); // Give server time to process
                    }
                    
                    // Reset form
                    uploadForm.reset();
                    
                    // Reset custom file upload elements
                    document.querySelectorAll('.custom-file-upload').forEach(el => {
                        const fileType = el.closest('.file-upload').querySelector('input').accept.includes('image') ? 'image' : 'audio';
                        el.innerHTML = `
                            <strong>Choose ${fileType} file</strong>
                            <span>or drag and drop here</span>
                        `;
                    });
                    
                    // Update file list
                    fetchFileList();
                } else {
                    showStatus('error', 'Upload failed: ' + xhr.statusText);
                }
                uploadProgress.style.display = 'none';
            };
            
            xhr.onerror = function() {
                showStatus('error', 'Upload failed. Please try again.');
                uploadProgress.style.display = 'none';
            };
            
            xhr.send(formData);
            
        } catch (error) {
            showStatus('error', 'Upload error: ' + error.message);
            uploadProgress.style.display = 'none';
        }
    });
}

function showStatus(type, message) {
    const uploadStatus = document.getElementById('uploadStatus');
    uploadStatus.className = 'upload-status ' + type;
    uploadStatus.textContent = message;
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            uploadStatus.style.opacity = '0';
            setTimeout(() => {
                uploadStatus.className = 'upload-status';
                uploadStatus.textContent = '';
                uploadStatus.style.opacity = '1';
            }, 500);
        }, 5000);
    }
}

async function fetchFileList() {
    try {
        const response = await fetch('/files');
        if (response.ok) {
            const files = await response.json();
            const fileList = document.getElementById('fileList');
    
            // Clear current list
            fileList.innerHTML = '';
            
            // Add files to list
            if (files.length === 0) {
                fileList.innerHTML = '<li>No files uploaded yet.</li>';
            } else {
                files.forEach(file => {
                    const li = document.createElement('li');
                    
                    // File type icon
                    const fileExtension = file.name.split('.').pop().toLowerCase();
                    let fileIcon = '📄';
                    if (['jpg', 'jpeg', 'png', 'gif'].includes(fileExtension)) {
                        fileIcon = '🖼️';
                    } else if (['mp3', 'wav', 'ogg'].includes(fileExtension)) {
                        fileIcon = '🔊';
                    }
                    
                    // Create info container
                    const infoDiv = document.createElement('div');
                    
                    // Create download link
                    const downloadLink = document.createElement('a');
                    downloadLink.href = `/download/${file.name}`;
                    downloadLink.innerHTML = `${fileIcon} ${file.name}`;
                    downloadLink.target = '_blank';
                    infoDiv.appendChild(downloadLink);
                    
                    // Add file details
                    const detailsSpan = document.createElement('span');
                    
                    // Check if uploaded_at is a valid timestamp
                    let dateDisplay;
                    if (file.uploaded_at && file.uploaded_at > 1000000000) {
                        dateDisplay = new Date(file.uploaded_at * 1000).toLocaleString();
                    } else {
                        dateDisplay = "Unknown date";
                    }   
                    
                    detailsSpan.textContent = ` - ${(file.size / 1024).toFixed(2)} KB - ${dateDisplay}`;
                    infoDiv.appendChild(detailsSpan);
                    
                    // Status badge
                    const statusBadge = document.createElement('span');
                    statusBadge.className = `status-badge ${file.status}`;
                    statusBadge.textContent = file.status || 'Ready';
                    
                    // Add to list item
                    li.appendChild(infoDiv);
                    li.appendChild(statusBadge);
                    
                    fileList.appendChild(li);
                });
            }
        }
    } catch (error) {
        console.error('Error fetching file list:', error);
    }
}

async function loadRecentImage() {
    try {
        const response = await fetch('/files');
        if (response.ok) {
            const files = await response.json();
            
            // Filter for image files
            const imageFiles = files.filter(file => 
                file.name.match(/\.(jpeg|jpg|gif|png)$/i)
            );
            
            if (imageFiles.length > 0) {
                // Sort by upload date, most recent first
                imageFiles.sort((a, b) => b.uploaded_at - a.uploaded_at);
                
                // Update frame content with most recent image
                updateFrameContent(`/download/${imageFiles[0].name}`);
            }
        }
    } catch (error) {
        console.error('Error loading recent image:', error);
    }
}

function updateFrameContent(imageUrl) {
    const frameContent = document.querySelector('.frame-content');
    
    // Create an image element
    const img = document.createElement('img');
    img.src = imageUrl;
    img.style.width = '100%';
    img.style.height = '100%';
    img.style.objectFit = 'cover';
    
    // Clear previous content
    frameContent.innerHTML = '';
    
    // Add the image
    frameContent.appendChild(img);
    
    // Add animation
    frameContent.animate([
        { opacity: 0.5 },
        { opacity: 1 }
    ], {
        duration: 500,
        easing: 'ease-in-out'
    });
}