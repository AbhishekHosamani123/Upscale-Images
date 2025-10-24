// Global variables
let currentFile = null;
let currentFileId = null;

// DOM elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const uploadSection = document.getElementById('uploadSection');
const settingsSection = document.getElementById('settingsSection');
const processingSection = document.getElementById('processingSection');
const resultsSection = document.getElementById('resultsSection');

// Settings elements
const scaleFactor = document.getElementById('scaleFactor');
const scaleFactorValue = document.getElementById('scaleFactorValue');
const interpolation = document.getElementById('interpolation');
const quality = document.getElementById('quality');
const qualityValue = document.getElementById('qualityValue');

// Buttons
const backBtn = document.getElementById('backBtn');
const upscaleBtn = document.getElementById('upscaleBtn');
const downloadBtn = document.getElementById('downloadBtn');
const newImageBtn = document.getElementById('newImageBtn');

// Modal elements
const errorModal = document.getElementById('errorModal');
const errorMessage = document.getElementById('errorMessage');
const closeErrorModal = document.getElementById('closeErrorModal');
const closeErrorBtn = document.getElementById('closeErrorBtn');

// Initialize event listeners
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    initializePresetButtons();
});

function initializeEventListeners() {
    // Upload area events
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
    
    // File input change
    fileInput.addEventListener('change', handleFileSelect);
    
    // Range inputs
    scaleFactor.addEventListener('input', updateScaleFactorValue);
    quality.addEventListener('input', updateQualityValue);
    
    // Button events
    backBtn.addEventListener('click', goBack);
    upscaleBtn.addEventListener('click', startUpscaling);
    downloadBtn.addEventListener('click', downloadImage);
    newImageBtn.addEventListener('click', resetApp);
    
    // Modal events
    closeErrorModal.addEventListener('click', hideErrorModal);
    closeErrorBtn.addEventListener('click', hideErrorModal);
    errorModal.addEventListener('click', (e) => {
        if (e.target === errorModal) hideErrorModal();
    });
}

function initializePresetButtons() {
    // Scale factor presets
    document.querySelectorAll('.preset-buttons .preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const scale = parseFloat(btn.dataset.scale);
            scaleFactor.value = scale;
            updateScaleFactorValue();
            updatePresetButtons(btn);
        });
    });
}

function handleDragOver(e) {
    e.preventDefault();
    uploadArea.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        handleFile(file);
    }
}

function handleFile(file) {
    // Validate file type
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/bmp', 'image/tiff', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
        showError('Please select a valid image file (PNG, JPG, JPEG, BMP, TIFF, WebP)');
        return;
    }
    
    // Validate file size (50MB max)
    if (file.size > 50 * 1024 * 1024) {
        showError('File size must be less than 50MB');
        return;
    }
    
    currentFile = file;
    showSettings();
}

function showSettings() {
    uploadSection.style.display = 'none';
    settingsSection.style.display = 'block';
    
    // Reset form
    scaleFactor.value = 2;
    interpolation.value = 'ai_enhanced';
    quality.value = 95;
    
    updateScaleFactorValue();
    updateQualityValue();
    updatePresetButtons();
}

function updateScaleFactorValue() {
    const value = parseFloat(scaleFactor.value);
    scaleFactorValue.textContent = value.toFixed(1) + 'x';
}

function updateQualityValue() {
    const value = parseInt(quality.value);
    qualityValue.textContent = value + '%';
}

function updatePresetButtons(activeBtn = null) {
    // Clear all active states
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Set active state
    if (activeBtn) {
        activeBtn.classList.add('active');
    }
}

function goBack() {
    settingsSection.style.display = 'none';
    uploadSection.style.display = 'block';
    currentFile = null;
    fileInput.value = '';
}

function startUpscaling() {
    if (!currentFile) {
        showError('Please select a file first');
        return;
    }
    
    showProcessing();
    uploadFile();
}

function showProcessing() {
    settingsSection.style.display = 'none';
    processingSection.style.display = 'block';
    
    // Animate progress bar
    const progressFill = document.getElementById('progressFill');
    progressFill.style.width = '100%';
}

function uploadFile() {
    const formData = new FormData();
    formData.append('file', currentFile);
    formData.append('scale_factor', scaleFactor.value);
    formData.append('interpolation', interpolation.value);
    formData.append('quality', quality.value);
    
    // Add timeout handling
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
    
    fetch('/upload', {
        method: 'POST',
        body: formData,
        signal: controller.signal
    })
    .then(response => {
        clearTimeout(timeoutId);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            currentFileId = data.file_id;
            showResults(data);
        } else {
            showError(data.error || 'Upscaling failed');
        }
    })
    .catch(error => {
        clearTimeout(timeoutId);
        console.error('Error:', error);
        if (error.name === 'AbortError') {
            showError('Upscaling timed out. Please try with a smaller image or different settings.');
        } else {
            showError('Network error occurred. Please try again.');
        }
    });
}

function showResults(data) {
    processingSection.style.display = 'none';
    resultsSection.style.display = 'block';
    
    // Show original image
    const originalImg = document.getElementById('originalImage');
    const originalInfo = document.getElementById('originalInfo');
    
    const reader = new FileReader();
    reader.onload = function(e) {
        originalImg.src = e.target.result;
        
        // Get image dimensions
        const img = new Image();
        img.onload = function() {
            originalInfo.textContent = `${img.width} × ${img.height} pixels`;
        };
        img.src = e.target.result;
    };
    reader.readAsDataURL(currentFile);
    
    // Show upscaled image
    const upscaledImg = document.getElementById('upscaledImage');
    const upscaledInfo = document.getElementById('upscaledInfo');
    
    // Handle base64 data from Vercel
    if (data.output_data) {
        upscaledImg.src = `data:image/png;base64,${data.output_data}`;
        upscaledImg.onload = function() {
            upscaledInfo.textContent = `${this.naturalWidth} × ${this.naturalHeight} pixels`;
        };
    } else {
        // Fallback for local deployment
        upscaledImg.src = `/preview/${data.file_id}`;
        upscaledImg.onload = function() {
            upscaledInfo.textContent = `${this.naturalWidth} × ${this.naturalHeight} pixels`;
        };
    }
    
    // Set download URL
    downloadBtn.onclick = () => {
        window.open(`/download/${data.file_id}`, '_blank');
    };
}

function downloadImage() {
    // This function is now handled in showResults()
    // The download button is set up there
}

function resetApp() {
    // Reset state
    currentFile = null;
    currentFileId = null;
    fileInput.value = '';
    
    // Show upload section
    resultsSection.style.display = 'none';
    uploadSection.style.display = 'block';
}

function showError(message) {
    errorMessage.textContent = message;
    errorModal.style.display = 'block';
    
    // Hide processing if showing
    processingSection.style.display = 'none';
    settingsSection.style.display = 'block';
}

function hideErrorModal() {
    errorModal.style.display = 'none';
}
