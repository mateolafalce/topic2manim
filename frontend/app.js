// API Configuration
const API_BASE_URL = window.location.origin;

// DOM Elements
const videoForm = document.getElementById('video-form');
const topicInput = document.getElementById('topic-input');
const llmSelect = document.getElementById('llm-select');
const ttsToggle = document.getElementById('tts-toggle');
const generateBtn = document.getElementById('generate-btn');
const progressSection = document.getElementById('progress-section');
const resultSection = document.getElementById('result-section');
const progressFill = document.getElementById('progress-fill');
const progressLog = document.getElementById('progress-log');
const resultVideo = document.getElementById('result-video');
const downloadBtn = document.getElementById('download-btn');

// Progress steps
const steps = {
    script: document.getElementById('step-script'),
    tts: document.getElementById('step-tts'),
    code: document.getElementById('step-code'),
    video: document.getElementById('step-video')
};

// State
let currentJobId = null;
let progressInterval = null;

// Form submission
videoForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const topic = topicInput.value.trim();
    if (!topic) return;

    // Reset UI
    progressSection.classList.remove('hidden');
    resultSection.classList.add('hidden');
    resetProgress();

    // Disable form
    generateBtn.disabled = true;
    generateBtn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 6v6l4 2"/>
        </svg>
        Generating...
    `;

    try {
        // Start video generation
        const response = await fetch(`${API_BASE_URL}/api/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                topic: topic,
                llm_provider: llmSelect.value,
                enable_tts: ttsToggle.checked
            })
        });

        if (!response.ok) {
            throw new Error('Failed to start video generation');
        }

        const data = await response.json();
        currentJobId = data.job_id;

        addLog(`✓ Job started: ${currentJobId}`);
        addLog(`→ Topic: ${topic}`);

        // Start polling for progress
        startProgressPolling();

    } catch (error) {
        console.error('Error:', error);
        addLog(`✗ Error: ${error.message}`, 'error');
        resetForm();
    }
});

// Progress polling
function startProgressPolling() {
    progressInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/progress/${currentJobId}`);

            if (!response.ok) {
                throw new Error('Failed to fetch progress');
            }

            const data = await response.json();
            updateProgress(data);

            // Check if completed
            if (data.status === 'completed') {
                stopProgressPolling();
                showResult(data.video_url);
            } else if (data.status === 'failed') {
                stopProgressPolling();
                addLog(`✗ Generation failed: ${data.error}`, 'error');
                resetForm();
            }

        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 2000); // Poll every 2 seconds
}

function stopProgressPolling() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
}

// Update progress UI
function updateProgress(data) {
    const { progress, current_step, message } = data;

    // Update progress bar
    updateProgressBar(progress);

    // Update steps
    updateSteps(current_step);

    // Add log message
    if (message) {
        addLog(message);
    }
}

function updateProgressBar(progress) {
    progressFill.style.width = `${progress}%`;
    document.querySelector('.progress-percentage').textContent = `${Math.round(progress)}%`;
}

function updateSteps(currentStep) {
    const stepOrder = ['script', 'tts', 'code', 'video'];
    const currentIndex = stepOrder.indexOf(currentStep);

    stepOrder.forEach((stepName, index) => {
        const stepElement = steps[stepName];
        if (!stepElement) return;

        stepElement.classList.remove('active', 'completed');

        if (index < currentIndex) {
            stepElement.classList.add('completed');
        } else if (index === currentIndex) {
            stepElement.classList.add('active');
        }
    });
}

function addLog(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = document.createElement('div');
    logEntry.textContent = `[${timestamp}] ${message}`;

    if (type === 'error') {
        logEntry.style.color = 'var(--error)';
    } else if (type === 'success') {
        logEntry.style.color = 'var(--success)';
    }

    progressLog.appendChild(logEntry);
    progressLog.scrollTop = progressLog.scrollHeight;
}

function resetProgress() {
    updateProgressBar(0);
    Object.values(steps).forEach(step => {
        step.classList.remove('active', 'completed');
    });
    progressLog.innerHTML = '';
}

function resetForm() {
    generateBtn.disabled = false;
    generateBtn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
        Generate Video
    `;
}

// Show result
function showResult(videoUrl) {
    addLog('✓ Video generation completed!', 'success');

    // Update progress to 100%
    updateProgressBar(100);
    Object.values(steps).forEach(step => {
        step.classList.add('completed');
        step.classList.remove('active');
    });

    // Show result section
    setTimeout(() => {
        resultSection.classList.remove('hidden');
        resultVideo.src = videoUrl;
        downloadBtn.href = videoUrl;

        // Scroll to result
        resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        resetForm();
    }, 1000);
}

// Smooth scroll for navigation
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
        }
    });
});

// Add spinning animation for loading state
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    .spinning {
        animation: spin 1s linear infinite;
    }
`;
document.head.appendChild(style);

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    stopProgressPolling();
});
