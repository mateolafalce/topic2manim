// API Configuration
const API_BASE_URL = window.location.origin;

// DOM Elements
const videoForm = document.getElementById('video-form');
const topicInput = document.getElementById('topic-input');
const llmSelect = document.getElementById('llm-select');
const llmModelSelect = document.getElementById('llm-model-select');
const llmModelInput = document.getElementById('llm-model-input');
const llmModelHint = document.getElementById('llm-model-hint');
const ttsSelect = document.getElementById('tts-select');
const ttsVoiceSelect = document.getElementById('tts-voice-select');
const ttsVoiceHint = document.getElementById('tts-voice-hint');
const ttsToggle = document.getElementById('tts-toggle');
const videoLengthSelect = document.getElementById('video-length');
const videoStyleSelect = document.getElementById('video-style');
const videoQualitySelect = document.getElementById('video-quality');
const reviewScriptToggle = document.getElementById('review-script-toggle');
const transitionDurationInput = document.getElementById('transition-duration');
const transitionTypeSelect = document.getElementById('transition-type');
const criticMinScoreInput = document.getElementById('critic-min-score');
const criticMaxRetriesInput = document.getElementById('critic-max-retries');
const audioFadeDurationInput = document.getElementById('audio-fade-duration');
const titleCardDurationInput = document.getElementById('title-card-duration');
const endScreenDurationInput = document.getElementById('end-screen-duration');
const enableTitleCardToggle = document.getElementById('enable-title-card');
const enableEndScreenToggle = document.getElementById('enable-end-screen');
const captionsToggle = document.getElementById('captions-toggle');
const musicToggle = document.getElementById('music-toggle');
const musicVolumeRow = document.getElementById('music-volume-row');
const musicVolumeInput = document.getElementById('music-volume');
const musicVolumeHint = document.getElementById('music-volume-hint');
const sfxToggle = document.getElementById('sfx-toggle');
const thumbnailsToggle = document.getElementById('thumbnails-toggle');
const metricsPanel = document.getElementById('metrics-panel');
const metricsGrid = document.getElementById('metrics-grid');
const metricsSuggestions = document.getElementById('metrics-suggestions');
const thumbnailsPanel = document.getElementById('thumbnails-panel');
const thumbnailsGrid = document.getElementById('thumbnails-grid');
const timelineImage = document.getElementById('timeline-image');
const linterPanel = document.getElementById('script-linter-panel');
const linterMetrics = document.getElementById('linter-metrics');
const linterSuggestions = document.getElementById('linter-suggestions');
const providerHealthEl = document.getElementById('provider-health');
const setupBannerEl = document.getElementById('setup-banner');
const scriptReviewSection = document.getElementById('script-review-section');
const scriptScenesEl = document.getElementById('script-scenes');
const approveScriptBtn = document.getElementById('approve-script-btn');
const previewSceneBtn = document.getElementById('preview-scene-btn');
const addSceneBtn = document.getElementById('add-scene-btn');
const generateBtn = document.getElementById('generate-btn');
const progressSection = document.getElementById('progress-section');
const resultSection = document.getElementById('result-section');
const progressFill = document.getElementById('progress-fill');
const progressLog = document.getElementById('progress-log');
const resultVideo = document.getElementById('result-video');
const downloadBtn = document.getElementById('download-btn');
const htmlPlayerBtn = document.getElementById('html-player-btn');
const inputModeTabs = document.querySelectorAll('.input-mode-tab');
const topicModePanel = document.getElementById('topic-mode-panel');
const importModePanel = document.getElementById('import-mode-panel');
const batchModePanel = document.getElementById('batch-mode-panel');
const batchInput = document.getElementById('batch-input');
const batchProgressSection = document.getElementById('batch-progress-section');
const batchProgressCount = document.getElementById('batch-progress-count');
const batchProgressFill = document.getElementById('batch-progress-fill');
const batchJobsList = document.getElementById('batch-jobs-list');
const importTitleInput = document.getElementById('import-title-input');
const importScriptInput = document.getElementById('import-script-input');
const importFormatSelect = document.getElementById('import-format');
const enrichAnimationsToggle = document.getElementById('enrich-animations-toggle');
const parseScriptBtn = document.getElementById('parse-script-btn');
const parseResultBadge = document.getElementById('parse-result-badge');
const parseWarningsEl = document.getElementById('parse-warnings');
const parsePreviewBreakdown = document.getElementById('parse-preview-breakdown');
const parsePreviewScenes = document.getElementById('parse-preview-scenes');
const parsePreviewTitle = document.getElementById('parse-preview-title');
const parseOpenEditorBtn = document.getElementById('parse-open-editor-btn');
const copyPromptBtn = document.getElementById('copy-prompt-btn');
const resumeSection = document.getElementById('resume-section');
const resumeJobBtn = document.getElementById('resume-job-btn');
const cancelJobBtn = document.getElementById('cancel-job-btn');
const progressActions = document.getElementById('progress-actions');
const recentJobsList = document.getElementById('recent-jobs-list');
const lengthHint = document.getElementById('length-hint');
const videoLengthRow = document.getElementById('video-length')?.closest('.form-row');

// Progress steps
const steps = {
    review: document.getElementById('step-review'),
    script: document.getElementById('step-script'),
    tts: document.getElementById('step-tts'),
    code: document.getElementById('step-code'),
    video: document.getElementById('step-video')
};

// State
let currentJobId = null;
let progressInterval = null;
let serverConfig = null;
let lastLoggedMessage = '';
let healthCheckTimer = null;
let renderStarted = false;
let inputMode = 'topic';
let parsedImportPreview = null;

function populateLengthSelect(selectElement, groups, defaultValue) {
    selectElement.innerHTML = '';
    (groups || []).forEach((group) => {
        const optgroup = document.createElement('optgroup');
        optgroup.label = group.label;
        (group.lengths || []).forEach((option) => {
            const el = document.createElement('option');
            el.value = option.id;
            el.textContent = option.label;
            el.dataset.sceneCount = option.scene_count || '';
            optgroup.appendChild(el);
        });
        selectElement.appendChild(optgroup);
    });
    if (defaultValue) {
        selectElement.value = defaultValue;
    }
    updateLengthHint();
}

function updateLengthHint() {
    if (!lengthHint || !serverConfig) return;
    const selected = videoLengthSelect.selectedOptions[0];
    const groups = serverConfig.video_settings_options?.length_groups || [];
    let meta = null;
    groups.forEach((g) => {
        (g.lengths || []).forEach((l) => {
            if (l.id === videoLengthSelect.value) meta = l;
        });
    });
    if (meta?.scene_count) {
        lengthHint.textContent = `~${meta.scene_count} scenes at ~12s narration each`;
    } else if (selected?.dataset.sceneCount) {
        lengthHint.textContent = `~${selected.dataset.sceneCount} scenes`;
    } else {
        lengthHint.textContent = '';
    }
}

function populateSelect(selectElement, options, defaultValue) {
    selectElement.innerHTML = '';
    options.forEach((option) => {
        const el = document.createElement('option');
        el.value = option.id;
        el.textContent = option.label;
        selectElement.appendChild(el);
    });
    if (defaultValue) {
        selectElement.value = defaultValue;
    }
}

function getVideoSettings() {
    return {
        length: videoLengthSelect.value,
        style: videoStyleSelect.value,
        quality: videoQualitySelect.value,
        review_script: reviewScriptToggle.checked,
        transition_duration: parseFloat(transitionDurationInput.value) || 0.3,
        transition_type: transitionTypeSelect.value || 'crossfade',
        critic_min_score: parseFloat(criticMinScoreInput.value) || 8.0,
        critic_max_retries: parseInt(criticMaxRetriesInput.value, 10) || 2,
        audio_fade_duration: parseFloat(audioFadeDurationInput.value) || 0.5,
        title_card_duration: parseFloat(titleCardDurationInput.value) || 2.5,
        end_screen_duration: parseFloat(endScreenDurationInput.value) || 3.0,
        enable_title_card: enableTitleCardToggle.checked,
        enable_end_screen: enableEndScreenToggle.checked,
        captions_enabled: captionsToggle.checked,
        music_enabled: musicToggle.checked,
        music_volume_db: musicToggle.checked ? (parseInt(musicVolumeInput.value, 10) || -22) : undefined,
        sfx_enabled: sfxToggle.checked,
        thumbnails_enabled: thumbnailsToggle.checked,
        quality_metrics_enabled: true,
    };
}

function getEffectiveTtsProvider() {
    if (ttsSelect.value !== 'auto') {
        return ttsSelect.value;
    }
    if (!serverConfig) {
        return null;
    }
    const defaultProvider = serverConfig.defaults?.tts_provider;
    if (defaultProvider && defaultProvider !== 'auto') {
        return defaultProvider;
    }
    return (serverConfig.configured_tts_providers || [])[0] || null;
}

let importDraftMode = false;

function isLikelyTestVoice(name) {
    const cleaned = String(name || '').trim();
    if (cleaned.length < 2) return true;
    const letters = cleaned.replace(/[^A-Za-z]/g, '');
    if (letters.length >= 6 && letters === letters.toUpperCase() && !cleaned.includes(' ')) {
        const vowels = (letters.match(/[aeiouAEIOU]/g) || []).length;
        if (vowels / letters.length < 0.2) return true;
    }
    return false;
}

function filterDisplayVoices(voices) {
    return (voices || []).filter((voice) => !isLikelyTestVoice(voice.name));
}

function formatVoiceLabel(voice) {
    const parts = [voice.name];
    const labels = voice.labels || {};
    const meta = [labels.gender, labels.accent, labels.descriptive].filter(Boolean);
    if (meta.length) {
        parts.push(`(${meta.join(', ')})`);
    }
    return parts.join(' ');
}

function populateVoiceSelect(voices, defaultVoice) {
    ttsVoiceSelect.innerHTML = '';
    voices.forEach((voice) => {
        const option = document.createElement('option');
        option.value = voice.voice_id;
        option.textContent = formatVoiceLabel(voice);
        if (voice.preview_url) {
            option.dataset.previewUrl = voice.preview_url;
        }
        ttsVoiceSelect.appendChild(option);
    });

    if (defaultVoice && voices.some((voice) => voice.voice_id === defaultVoice)) {
        ttsVoiceSelect.value = defaultVoice;
    } else if (voices.length) {
        ttsVoiceSelect.value = voices[0].voice_id;
    }
}

async function refreshTtsVoiceControls() {
    ttsVoiceSelect.classList.add('hidden');
    ttsVoiceHint.classList.add('hidden');

    if (!ttsToggle.checked) {
        ttsVoiceHint.textContent = 'Enable TTS to choose a voice';
        ttsVoiceHint.classList.remove('hidden');
        return;
    }

    const provider = getEffectiveTtsProvider();
    if (!provider) {
        ttsVoiceHint.textContent = 'No TTS provider configured';
        ttsVoiceHint.classList.remove('hidden');
        return;
    }

    ttsVoiceSelect.classList.remove('hidden');
    ttsVoiceSelect.disabled = true;
    ttsVoiceSelect.innerHTML = '<option>Loading voices...</option>';

    try {
        const response = await fetch(`${API_BASE_URL}/api/tts/voices?provider=${provider}`);
        const data = await response.json();
        const defaultVoice = serverConfig?.defaults?.tts_voices?.[provider] || data.default_voice;
        populateVoiceSelect(filterDisplayVoices(data.voices || []), defaultVoice);
        ttsVoiceSelect.disabled = false;
    } catch (error) {
        console.warn('Could not load TTS voices:', error);
        ttsVoiceHint.textContent = 'Could not load voices';
        ttsVoiceHint.classList.remove('hidden');
    }
}

function getSelectedTtsVoice() {
    if (!ttsToggle.checked || ttsVoiceSelect.classList.contains('hidden')) {
        return null;
    }
    return ttsVoiceSelect.value || null;
}

function scriptReviewHasScenes() {
    return !scriptReviewSection.classList.contains('hidden')
        && scriptScenesEl.querySelectorAll('.scene-card').length > 0;
}

function scriptToLooseFormat(scenes) {
    return scenes.map((scene, index) => {
        const title = scene.title ? `: ${scene.title}` : '';
        return [
            `Scene ${index + 1}${title}`,
            `Narration: ${scene.text || ''}`,
            `Visual: ${scene.animation || ''}`,
        ].join('\n');
    }).join('\n\n');
}

function syncEditorToTextarea() {
    if (!scriptReviewHasScenes()) return;
    importScriptInput.value = scriptToLooseFormat(collectScriptFromEditor());
}

function updateGenerateButtonHint() {
    if (inputMode !== 'import') {
        generateBtn.title = '';
        return;
    }
    if (scriptReviewHasScenes()) {
        generateBtn.title = 'Uses the script from the Review editor below (not the raw paste box)';
    } else {
        generateBtn.title = '';
    }
}

function getGeneratePayload(topic) {
    const payload = {
        topic,
        llm_provider: llmSelect.value,
        llm_model: getSelectedLlmModel(),
        tts_provider: ttsSelect.value,
        tts_voice: getSelectedTtsVoice(),
        enable_tts: ttsToggle.checked,
        video_settings: getVideoSettings(),
        input_mode: inputMode,
    };

    if (inputMode === 'import') {
        payload.import_script = importScriptInput.value.trim();
        payload.import_format = importFormatSelect.value;
        payload.enrich_animations = enrichAnimationsToggle.checked;
        if (importTitleInput.value.trim()) {
            payload.topic = importTitleInput.value.trim();
        }
    }

    return payload;
}

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function showCodePreviewModal(videoUrl, className) {
    const modal = document.getElementById('code-preview-modal');
    const video = document.getElementById('code-preview-video');
    if (!modal || !video) return;
    video.src = videoUrl;
    video.load();
    modal.classList.remove('hidden');
}

function hideCodePreviewModal() {
    const modal = document.getElementById('code-preview-modal');
    const video = document.getElementById('code-preview-video');
    if (!modal) return;
    modal.classList.add('hidden');
    if (video) {
        video.pause();
        video.src = '';
    }
}

const codePreviewCloseBtn = document.getElementById('code-preview-close');
if (codePreviewCloseBtn) {
    codePreviewCloseBtn.addEventListener('click', hideCodePreviewModal);
}
document.getElementById('code-preview-modal')?.addEventListener('click', (e) => {
    if (e.target.classList.contains('code-preview-backdrop')) {
        hideCodePreviewModal();
    }
});

function setInputMode(mode) {
    inputMode = mode;
    inputModeTabs.forEach((tab) => {
        tab.classList.toggle('active', tab.dataset.mode === mode);
    });
    topicModePanel.classList.toggle('hidden', mode !== 'topic');
    importModePanel.classList.toggle('hidden', mode !== 'import');
    batchModePanel?.classList.toggle('hidden', mode !== 'batch');
    resetForm();
    parsedImportPreview = null;
    importDraftMode = false;
    parseResultBadge.classList.add('hidden');
    parseWarningsEl.classList.add('hidden');
    parsePreviewBreakdown?.classList.add('hidden');
    scriptReviewSection.classList.add('hidden');
    batchProgressSection?.classList.add('hidden');
    updateGenerateButtonHint();
}

inputModeTabs.forEach((tab) => {
    tab.addEventListener('click', () => setInputMode(tab.dataset.mode));
});

function snippet(text, max = 120) {
    const value = String(text || '').trim();
    if (value.length <= max) return value;
    return `${value.slice(0, max)}…`;
}

function renderParsePreview(data) {
    if (!parsePreviewBreakdown || !parsePreviewScenes) return;
    const scenes = data.scenes || [];
    if (!scenes.length) {
        parsePreviewBreakdown.classList.add('hidden');
        return;
    }

    const formatLabel = data.format === 'json' ? 'JSON' : 'Loose scene format';
    if (parsePreviewTitle) {
        parsePreviewTitle.textContent = `${data.scene_count} scenes parsed (${formatLabel})`;
    }

    parsePreviewScenes.innerHTML = scenes.map((scene, index) => {
        const title = scene.title ? `: ${escapeHtml(scene.title)}` : '';
        return `
            <button type="button" class="parse-scene-chip" data-scene-index="${index}">
                <span class="parse-scene-chip-title">Scene ${index + 1}${title}</span>
                <span class="parse-scene-chip-narration">${escapeHtml(snippet(scene.text))}</span>
                <span class="parse-scene-chip-visual">${escapeHtml(snippet(scene.animation, 90))}</span>
            </button>`;
    }).join('');

    parsePreviewScenes.querySelectorAll('.parse-scene-chip').forEach((chip) => {
        chip.addEventListener('click', () => {
            showImportScriptReview(data.scenes, data);
            const card = scriptScenesEl.querySelectorAll('.scene-card')[Number(chip.dataset.sceneIndex)];
            card?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
    });

    parsePreviewBreakdown.classList.remove('hidden');
}

function showImportScriptReview(scenes, meta = {}) {
    importDraftMode = !currentJobId;
    parsedImportPreview = meta;
    progressSection.classList.remove('hidden');
    scriptReviewSection.classList.remove('hidden');
    renderScriptEditor(scenes);
    updateGenerateButtonHint();
    scriptReviewSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

if (parseOpenEditorBtn) {
    parseOpenEditorBtn.addEventListener('click', () => {
        if (parsedImportPreview?.scenes?.length) {
            showImportScriptReview(parsedImportPreview.scenes, parsedImportPreview);
        }
    });
}

async function previewParseScript() {
    const importScript = importScriptInput.value.trim();
    if (!importScript) {
        alert('Paste a script first.');
        return;
    }

    parseScriptBtn.disabled = true;
    parseScriptBtn.textContent = 'Parsing...';

    try {
        const response = await fetch(`${API_BASE_URL}/api/script/parse`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                import_script: importScript,
                import_format: importFormatSelect.value,
                topic: importTitleInput.value.trim() || undefined,
            }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Parse failed');
        }

        parsedImportPreview = data;
        parseResultBadge.textContent = `${data.scene_count} scenes${data.chapters?.length ? ` · ${data.chapters.length} chapters` : ''} — click to review`;
        parseResultBadge.classList.remove('hidden');
        parseResultBadge.onclick = () => showImportScriptReview(data.scenes, data);

        if (data.title && !importTitleInput.value.trim()) {
            importTitleInput.value = data.title;
        }

        if (data.warnings?.length) {
            parseWarningsEl.innerHTML = data.warnings.map((w) => `<div>• ${escapeHtml(w)}</div>`).join('');
            parseWarningsEl.classList.remove('hidden');
        } else {
            parseWarningsEl.classList.add('hidden');
        }

        renderParsePreview(data);
        showImportScriptReview(data.scenes, data);
    } catch (error) {
        parseResultBadge.classList.add('hidden');
        parsePreviewBreakdown?.classList.add('hidden');
        parseWarningsEl.innerHTML = `<div>✗ ${escapeHtml(error.message)}</div>`;
        parseWarningsEl.classList.remove('hidden');
        parsedImportPreview = null;
    } finally {
        parseScriptBtn.disabled = false;
        parseScriptBtn.textContent = 'Preview Parse';
    }
}

parseScriptBtn.addEventListener('click', previewParseScript);

async function copyPromptTemplate() {
    const topic = importTitleInput.value.trim() || topicInput.value.trim();
    const params = new URLSearchParams({
        topic,
        length: videoLengthSelect.value,
        style: videoStyleSelect.value,
    });
    try {
        const response = await fetch(`${API_BASE_URL}/api/script/prompt-template?${params}`);
        const data = await response.json();
        await navigator.clipboard.writeText(data.prompt || '');
        copyPromptBtn.textContent = 'Copied!';
        setTimeout(() => { copyPromptBtn.textContent = 'Copy ChatGPT/Claude Prompt'; }, 2000);
    } catch (error) {
        alert(`Could not copy prompt: ${error.message}`);
    }
}

if (copyPromptBtn) {
    copyPromptBtn.addEventListener('click', copyPromptTemplate);
}

function renderSetupBanner(config) {
    if (!setupBannerEl) {
        return;
    }
    const llmReady = (config.configured_llm_providers || []).length > 0;
    const ttsNeeded = ttsToggle.checked;
    const ttsReady = !ttsNeeded || (config.configured_tts_providers || []).length > 0;

    if (llmReady && ttsReady) {
        setupBannerEl.classList.add('hidden');
        setupBannerEl.innerHTML = '';
        return;
    }

    const lines = [];
    if (!config.env_file_found) {
        lines.push(
            'No .env file found. Restart the server after creating one from .env.example in the project root.',
        );
    } else if (!llmReady) {
        lines.push(
            'Open .env in the project root and set at least one LLM API key (e.g. OPENAI_API_KEY or OLLAMA_API_KEY). Restart the server when done.',
        );
    }
    if (ttsNeeded && !ttsReady) {
        lines.push(
            'TTS is enabled but no TTS provider is configured. Add ELEVENLABS_API_KEY or OpenAI credentials, or turn off Enable TTS.',
        );
    }

    setupBannerEl.classList.remove('hidden');
    setupBannerEl.innerHTML = [
        '<strong>Setup required</strong>',
        ...lines.map((line) => `<p>${escapeHtml(line)}</p>`),
    ].join('');
}

async function checkProviderHealth() {
    clearTimeout(healthCheckTimer);
    healthCheckTimer = setTimeout(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/providers/health`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(getGeneratePayload('health-check')),
            });
            const data = await response.json();
            renderProviderHealth(data);
        } catch (error) {
            providerHealthEl.classList.add('hidden');
        }
    }, 400);
}

function renderProviderHealth(data) {
    providerHealthEl.classList.remove('hidden', 'error');
    const items = [];

    // ISS-0001: escape server data before innerHTML to prevent XSS
    Object.entries(data.llm || {}).forEach(([provider, status]) => {
        items.push(`<div class="provider-health-item"><span class="${status.ok ? 'health-ok' : 'health-fail'}">${status.ok ? '✓' : '✗'}</span><span><strong>${escapeHtml(provider)}</strong>: ${escapeHtml(status.message)}</span></div>`);
    });

    if (data.tts) {
        items.push(`<div class="provider-health-item"><span class="${data.tts.ok ? 'health-ok' : 'health-fail'}">${data.tts.ok ? '✓' : '✗'}</span><span><strong>TTS</strong>: ${escapeHtml(data.tts.message)}</span></div>`);
    }

    providerHealthEl.innerHTML = items.join('');
    if (!data.ready) {
        providerHealthEl.classList.add('error');
    }
}

function hideModelControls() {
    llmModelSelect.classList.add('hidden');
    llmModelInput.classList.add('hidden');
    llmModelHint.classList.add('hidden');
}

function populateModelSelect(models, defaultModel) {
    llmModelSelect.innerHTML = '';

    models.forEach((model) => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        llmModelSelect.appendChild(option);
    });

    const customOption = document.createElement('option');
    customOption.value = '__custom__';
    customOption.textContent = 'Custom model...';
    llmModelSelect.appendChild(customOption);

    if (defaultModel && models.includes(defaultModel)) {
        llmModelSelect.value = defaultModel;
    } else if (models.length) {
        llmModelSelect.value = models[0];
    }
}

async function refreshModelControls() {
    const provider = llmSelect.value;
    hideModelControls();

    if (provider === 'auto') {
        llmModelHint.textContent = 'Auto uses each provider\'s default model from .env';
        llmModelHint.classList.remove('hidden');
        return;
    }

    const defaultModel = serverConfig?.defaults?.llm_models?.[provider] || '';

    if (provider === 'ollama') {
        llmModelSelect.classList.remove('hidden');
        llmModelSelect.disabled = true;
        llmModelSelect.innerHTML = '<option>Loading Ollama models...</option>';

        try {
            const response = await fetch(`${API_BASE_URL}/api/llm/models?provider=ollama`);
            const data = await response.json();
            populateModelSelect(data.models || [], data.default_model || defaultModel);
            llmModelSelect.disabled = false;
        } catch (error) {
            llmModelSelect.innerHTML = `<option value="${defaultModel}">${defaultModel}</option>`;
            llmModelSelect.disabled = false;
            console.warn('Could not load Ollama models:', error);
        }
        return;
    }

    llmModelInput.classList.remove('hidden');
    llmModelInput.value = defaultModel;
    llmModelInput.placeholder = `Model for ${provider} (default: ${defaultModel})`;
}

function getSelectedLlmModel() {
    const provider = llmSelect.value;
    if (provider === 'auto') {
        return null;
    }

    if (provider === 'ollama') {
        if (llmModelSelect.value === '__custom__') {
            return llmModelInput.value.trim() || null;
        }
        return llmModelSelect.value || null;
    }

    const value = llmModelInput.value.trim();
    return value || null;
}

function markProviderOptions(selectElement, configuredProviders) {
    Array.from(selectElement.options).forEach((option) => {
        option.disabled = false;

        if (option.value === 'auto') {
            option.textContent = option.dataset.defaultLabel || option.textContent;
            option.title = 'Uses the first configured provider';
            return;
        }

        const isConfigured = configuredProviders.includes(option.value);
        const baseLabel = option.dataset.defaultLabel || option.textContent.replace(' (not configured)', '');
        option.dataset.defaultLabel = baseLabel;
        option.textContent = isConfigured ? baseLabel : `${baseLabel} (not configured)`;
        option.title = isConfigured
            ? 'Ready to use'
            : 'Add the required API keys in .env before generating';
    });
}

async function loadServerConfig() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/config`);
        if (!response.ok) {
            return;
        }

        const config = await response.json();
        serverConfig = config;
        renderSetupBanner(config);
        markProviderOptions(llmSelect, config.configured_llm_providers || []);
        markProviderOptions(ttsSelect, config.configured_tts_providers || []);

        if (config.defaults?.llm_provider && config.defaults.llm_provider !== 'auto') {
            llmSelect.value = config.defaults.llm_provider;
        }
        if (config.defaults?.tts_provider && config.defaults.tts_provider !== 'auto') {
            ttsSelect.value = config.defaults.tts_provider;
        }

        const vs = config.video_settings_options || {};
        const vd = config.defaults?.video_settings || {};
        if (vs.length_groups?.length) {
            populateLengthSelect(videoLengthSelect, vs.length_groups, vd.length || 'min_5');
        } else {
            populateSelect(videoLengthSelect, vs.lengths || [], vd.length || 'min_5');
        }
        populateSelect(videoStyleSelect, vs.styles || [], vd.style || 'balanced');
        populateSelect(videoQualitySelect, vs.qualities || [], vd.quality || 'standard');
        reviewScriptToggle.checked = vd.review_script !== false;

        const prod = config.production_settings || {};
        if (prod.transition_duration && transitionDurationInput) {
            transitionDurationInput.value = vd.transition_duration ?? prod.transition_duration.default ?? 0.3;
        }
        if (transitionTypeSelect) {
            transitionTypeSelect.value = vd.transition_type ?? 'crossfade';
        }
        if (prod.critic_min_score && criticMinScoreInput) {
            criticMinScoreInput.value = vd.critic_min_score ?? prod.critic_min_score.default ?? 8.0;
        }
        if (prod.critic_max_retries && criticMaxRetriesInput) {
            criticMaxRetriesInput.value = vd.critic_max_retries ?? prod.critic_max_retries.default ?? 2;
        }
        if (audioFadeDurationInput) {
            audioFadeDurationInput.value = vd.audio_fade_duration ?? prod.audio_fade_duration?.default ?? 0.5;
        }
        if (titleCardDurationInput) {
            titleCardDurationInput.value = vd.title_card_duration ?? prod.title_card_duration?.default ?? 2.5;
        }
        if (endScreenDurationInput) {
            endScreenDurationInput.value = vd.end_screen_duration ?? prod.end_screen_duration?.default ?? 3.0;
        }
        if (enableTitleCardToggle) {
            enableTitleCardToggle.checked = vd.enable_title_card !== false;
        }
        if (enableEndScreenToggle) {
            enableEndScreenToggle.checked = vd.enable_end_screen !== false;
        }

        await refreshModelControls();
        await refreshTtsVoiceControls();
        checkProviderHealth();
        loadRecentJobs();
    } catch (error) {
        console.warn('Could not load server config:', error);
    }
}

function syncTtsControls() {
    ttsSelect.disabled = !ttsToggle.checked;
    if (!serverConfig) return;
    refreshTtsVoiceControls();
}

ttsToggle.addEventListener('change', () => {
    if (serverConfig) {
        renderSetupBanner(serverConfig);
    }
    syncTtsControls();
    checkProviderHealth();
});
musicToggle.addEventListener('change', () => {
    musicVolumeRow.classList.toggle('hidden', !musicToggle.checked);
});
if (musicVolumeInput) {
    musicVolumeInput.addEventListener('input', () => {
        if (musicVolumeHint) musicVolumeHint.textContent = `${musicVolumeInput.value} dB`;
    });
}
llmSelect.addEventListener('change', () => {
    refreshModelControls();
    checkProviderHealth();
});
ttsSelect.addEventListener('change', () => {
    refreshTtsVoiceControls();
    checkProviderHealth();
});
ttsVoiceSelect.addEventListener('change', checkProviderHealth);
llmModelSelect.addEventListener('change', () => {
    if (llmModelSelect.value === '__custom__') {
        llmModelInput.classList.remove('hidden');
        llmModelInput.focus();
    } else {
        llmModelInput.classList.add('hidden');
    }
    checkProviderHealth();
});
llmModelInput.addEventListener('input', checkProviderHealth);
videoLengthSelect.addEventListener('change', updateLengthHint);

async function loadRecentJobs() {
    if (!recentJobsList) return;
    try {
        const response = await fetch(`${API_BASE_URL}/api/jobs?limit=10`);
        const data = await response.json();
        renderRecentJobs(data.jobs || []);
    } catch (error) {
        recentJobsList.innerHTML = '<p class="form-hint">Could not load recent jobs.</p>';
    }
}

function formatJobStatus(status) {
    const labels = {
        completed: 'Completed',
        failed: 'Failed',
        interrupted: 'Interrupted',
        cancelled: 'Cancelled',
        running: 'Rendering',
        awaiting_review: 'Awaiting review',
        queued: 'Queued',
    };
    return labels[status] || status;
}

function jobStatusClass(status) {
    if (status === 'completed') return 'job-status-completed';
    if (status === 'failed' || status === 'cancelled') return 'job-status-failed';
    if (status === 'interrupted') return 'job-status-interrupted';
    if (status === 'running' || status === 'awaiting_review') return 'job-status-active';
    return 'job-status-default';
}

function renderJobCard(job) {
    const progress = job.scenes_total
        ? `${job.scenes_done || job.scenes_rendered || 0}/${job.scenes_total} scenes`
        : `${job.progress || 0}%`;
    const canResume = Boolean(job.can_resume);
    const failureHint = job.error || job.message || '';
    const statusLabel = formatJobStatus(job.status);
    return `
        <div class="recent-job-card" title="${escapeHtml(failureHint)}">
            <div class="recent-job-meta">
                <strong>${escapeHtml(job.topic || 'Untitled video')}</strong>
                <span class="recent-job-status ${jobStatusClass(job.status)}">${escapeHtml(statusLabel)} · ${progress}</span>
                ${failureHint && (job.status === 'failed' || job.status === 'cancelled') ? `<span class="recent-job-error">${escapeHtml(snippet(failureHint, 80))}</span>` : ''}
            </div>
            <div class="recent-job-actions">
                ${canResume ? `<button type="button" data-action="resume" data-id="${job.job_id}">Resume</button>` : ''}
                ${job.video_url ? `<button type="button" data-action="view" data-url="${job.video_url}">View</button>` : ''}
                <button type="button" data-action="attach" data-id="${job.job_id}">Open</button>
            </div>
        </div>`;
}

function renderRecentJobs(jobs) {
    if (!jobs.length) {
        recentJobsList.innerHTML = '<p class="form-hint">No recent jobs yet.</p>';
        return;
    }

    const priority = (job) => {
        if (job.status === 'completed') return 0;
        if (job.status === 'running' || job.status === 'awaiting_review') return 1;
        if (job.status === 'interrupted') return 2;
        if (job.status === 'queued') return 3;
        return 4;
    };

    const sorted = [...jobs].sort((a, b) => priority(a) - priority(b));
    const primary = sorted.filter((job) => job.status !== 'failed' && job.status !== 'cancelled');
    const failed = sorted.filter((job) => job.status === 'failed' || job.status === 'cancelled');

    let html = primary.map(renderJobCard).join('');
    if (failed.length) {
        html += `
            <details class="recent-jobs-failed">
                <summary>${failed.length} failed or cancelled job${failed.length === 1 ? '' : 's'}</summary>
                <div class="recent-jobs-failed-list">${failed.map(renderJobCard).join('')}</div>
            </details>`;
    }

    recentJobsList.innerHTML = html;

    recentJobsList.querySelectorAll('button').forEach((btn) => {
        btn.addEventListener('click', () => {
            const action = btn.dataset.action;
            if (action === 'resume') {
                attachToJob(btn.dataset.id);
            } else if (action === 'attach') {
                attachToJob(btn.dataset.id);
            } else if (action === 'view') {
                resultSection.classList.remove('hidden');
                resultVideo.src = btn.dataset.url;
                downloadBtn.href = btn.dataset.url;
            }
        });
    });
}

async function attachToJob(jobId) {
    currentJobId = jobId;
    localStorage.setItem('t2m_current_job', jobId);
    progressSection.classList.remove('hidden');
    try {
        const response = await fetch(`${API_BASE_URL}/api/progress/${jobId}`);
        const data = await response.json();
        updateProgress(data);
        if (data.status === 'awaiting_review') {
            showScriptReview(data.script || []);
        } else if (data.status === 'completed' && data.video_url) {
            showResult(data.video_url, { htmlUrl: data.html_url });
            if (data.script?.length) {
                scriptReviewSection.classList.remove('hidden');
                renderScriptEditor(data.script, true);
            }
        } else if (data.can_resume) {
            showResumeOption(data);
        } else if (data.resumable || data.status === 'interrupted') {
            addLog(data.message || 'This job cannot be resumed — no render checkpoint saved.', 'error');
            resumeSection.classList.add('hidden');
            if (!data.script?.length) {
                localStorage.removeItem('t2m_current_job');
            }
        } else if (data.status === 'running') {
            renderStarted = true;
            progressActions?.classList.remove('hidden');
            startProgressPolling();
        } else if (data.status === 'failed') {
            addLog(data.error || data.message || 'Job failed.', 'error');
            resumeSection.classList.add('hidden');
        }
    } catch (error) {
        addLog(`Could not load job: ${error.message}`, 'error');
    }
}

async function cancelCurrentJob() {
    if (!currentJobId) return;
    cancelJobBtn.disabled = true;
    try {
        const response = await fetch(`${API_BASE_URL}/api/jobs/${currentJobId}/cancel`, { method: 'POST' });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || 'Cancel failed');
        }
        addLog('Cancel requested — stopping after current scene...', 'error');
    } catch (error) {
        addLog(`✗ ${error.message}`, 'error');
    } finally {
        cancelJobBtn.disabled = false;
    }
}

if (cancelJobBtn) {
    cancelJobBtn.addEventListener('click', cancelCurrentJob);
}

loadServerConfig().then(() => {
    syncTtsControls();
    setInputMode('topic');
    const savedJobId = localStorage.getItem('t2m_current_job');
    if (savedJobId) {
        attachToJob(savedJobId);
    }
});

// Form submission
async function submitVideoGeneration(options = {}) {
    let { scriptOverride, skipReview = false, topicOverride } = options;

    let topic;
    if (inputMode === 'import') {
        if (scriptReviewHasScenes() && !scriptOverride) {
            scriptOverride = collectScriptFromEditor();
            syncEditorToTextarea();
            skipReview = true;
        } else if (!scriptOverride) {
            const importScript = importScriptInput.value.trim();
            if (!importScript) {
                alert('Paste your script in the Import Script tab.');
                return;
            }
        }
        topic = topicOverride || importTitleInput.value.trim() || parsedImportPreview?.title || 'Imported Video';
    } else {
        topic = topicOverride || topicInput.value.trim();
        if (!topic) return;
    }

    progressSection.classList.remove('hidden');
    resultSection.classList.add('hidden');
    scriptReviewSection.classList.add('hidden');
    resumeSection.classList.add('hidden');
    progressActions?.classList.add('hidden');
    renderStarted = false;
    resetProgress();

    generateBtn.disabled = true;
    generateBtn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 6v6l4 2"/>
        </svg>
        Generating...
    `;

    try {
        const payload = getGeneratePayload(topic);
        if (scriptOverride) {
            payload.script = scriptOverride;
            delete payload.import_script;
        }
        if (skipReview) {
            payload.video_settings = { ...payload.video_settings, review_script: false };
        }

        const response = await fetch(`${API_BASE_URL}/api/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || 'Failed to start video generation');
        }

        const data = await response.json();
        currentJobId = data.job_id;
        importDraftMode = false;
        localStorage.setItem('t2m_current_job', currentJobId);
        progressActions?.classList.remove('hidden');

        addLog(`✓ Job started: ${currentJobId}`);
        addLog(`→ ${inputMode === 'import' ? 'Import' : 'Topic'}: ${topic}`);
        const model = getSelectedLlmModel();
        if (model) {
            addLog(`→ Model: ${model}`);
        }
        const voice = getSelectedTtsVoice();
        if (voice && ttsToggle.checked) {
            const voiceLabel = ttsVoiceSelect.selectedOptions[0]?.textContent || voice;
            addLog(`→ Voice: ${voiceLabel}`);
        }

        startProgressPolling();
    } catch (error) {
        console.error('Error:', error);
        addLog(`✗ Error: ${error.message}`, 'error');
        resetForm();
    }
}

async function submitBatch() {
    const raw = batchInput?.value.trim();
    if (!raw) {
        alert('Enter at least one topic in the Batch tab.');
        return;
    }
    const topics = raw.split('\n').map(t => t.trim()).filter(Boolean);
    if (topics.length === 0) {
        alert('Enter at least one topic.');
        return;
    }
    if (topics.length > 50) {
        alert('Max 50 topics per batch.');
        return;
    }

    progressSection.classList.remove('hidden');
    resultSection.classList.add('hidden');
    scriptReviewSection.classList.add('hidden');
    resumeSection.classList.add('hidden');
    progressActions?.classList.add('hidden');
    resetProgress();
    generateBtn.disabled = true;
    generateBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg> Starting batch…`;

    try {
        const payload = {
            items: topics.map(t => ({ topic: t, video_settings: getVideoSettings() })),
            llm_provider: llmSelect.value,
            llm_model: getSelectedLlmModel(),
            tts_provider: ttsSelect.value,
            tts_voice: getSelectedTtsVoice(),
            enable_tts: ttsToggle.checked,
        };
        const response = await fetch(`${API_BASE_URL}/api/batch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || 'Failed to start batch');
        }
        const data = await response.json();
        addLog(`✓ Batch started: ${data.batch_id} (${data.total} videos)`);
        startBatchPolling(data.batch_id);
    } catch (error) {
        console.error('Batch error:', error);
        addLog(`✗ Batch error: ${error.message}`, 'error');
        resetForm();
    }
}

let batchInterval = null;

function startBatchPolling(batchId) {
    batchProgressSection?.classList.remove('hidden');
    batchInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/batch/${batchId}`);
            if (!response.ok) return;
            const data = await response.json();
            renderBatchProgress(data);
            if (data.status === 'completed' || data.status === 'partial') {
                clearInterval(batchInterval);
                batchInterval = null;
                addLog(`✓ Batch ${data.status}: ${data.completed}/${data.total} done`);
                resetForm();
                loadRecentJobs();
            }
        } catch (err) {
            console.error('Batch polling error:', err);
        }
    }, 3000);
}

function renderBatchProgress(data) {
    const total = data.total || 1;
    const completed = data.completed || 0;
    const pct = Math.round((completed / total) * 100);
    if (batchProgressCount) batchProgressCount.textContent = `${completed} / ${total} completed`;
    if (batchProgressFill) batchProgressFill.style.width = `${pct}%`;
    if (!batchJobsList) return;
    batchJobsList.innerHTML = (data.jobs || []).map(job => {
        const statusClass = job.status === 'completed' ? 'completed' : job.status === 'failed' ? 'failed' : 'running';
        return `<div class="batch-job-item ${statusClass}">
            <span class="batch-job-topic">${escapeHtml(job.topic || 'Untitled')}</span>
            <span class="batch-job-status ${statusClass}">${job.status} ${job.progress || 0}%</span>
        </div>`;
    }).join('');
}

videoForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (inputMode === 'batch') {
        await submitBatch();
    } else {
        await submitVideoGeneration();
    }
});

// Progress polling
let pollingOptions = {};

function startProgressPolling(options = {}) {
    pollingOptions = options;
    progressInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/progress/${currentJobId}`);

            if (!response.ok) {
                throw new Error('Failed to fetch progress');
            }

            const data = await response.json();
            updateProgress(data);

            const isPreview = pollingOptions.preview || data.job_type === 'scene_preview';

            // Check if completed
            if (data.status === 'completed') {
                stopProgressPolling();
                progressActions?.classList.add('hidden');
                if (!isPreview) {
                    scriptReviewSection.classList.add('hidden');
                }
                showResult(data.video_url, { preview: isPreview, htmlUrl: data.html_url });
                loadRecentJobs();
            } else if (data.status === 'failed' || data.status === 'interrupted' || data.status === 'cancelled') {
                stopProgressPolling();
                progressActions?.classList.add('hidden');
                if (isPreview) {
                    addLog(`✗ Preview failed: ${data.error || data.message}`, 'error');
                } else if (data.resumable || data.status === 'interrupted' || data.status === 'cancelled') {
                    showResumeOption(data);
                } else {
                    addLog(`✗ Generation failed: ${data.error || data.message}`, 'error');
                    resetForm();
                }
                loadRecentJobs();
            } else if (data.status === 'running') {
                progressActions?.classList.remove('hidden');
            } else if (data.status === 'awaiting_review' && !renderStarted) {
                stopProgressPolling();
                showScriptReview(data.script || [], data.recovered);
            } else if (data.status === 'running' && renderStarted) {
                updateProgress(data);
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
    const { progress, current_step, message, scenes_done, scenes_total } = data;

    updateProgressBar(progress);
    updateSteps(current_step);

    let logMessage = message;
    if (scenes_total && current_step === 'code') {
        logMessage = `${message} (${scenes_done || 0}/${scenes_total} scenes)`;
    }

    if (logMessage && logMessage !== lastLoggedMessage) {
        addLog(logMessage);
        lastLoggedMessage = logMessage;
    }

    const latestResults = data.scene_results || [];
    const lastResult = latestResults[latestResults.length - 1];
    if (lastResult?.critic?.score != null) {
        const criticKey = `critic-${lastResult.index}-${lastResult.critic.score}`;
        if (criticKey !== lastLoggedMessage) {
            const issues = (lastResult.critic.issues || []).slice(0, 2).join('; ');
            addLog(`Scene ${lastResult.index} visual score: ${lastResult.critic.score}/10${issues ? ` — ${issues}` : ''}`);
        }
    }
}

function updateProgressBar(progress) {
    progressFill.style.width = `${progress}%`;
    document.querySelector('.progress-percentage').textContent = `${Math.round(progress)}%`;
}

function updateSteps(currentStep) {
    const stepOrder = ['script', 'review', 'tts', 'code', 'video'];
    let currentIndex = stepOrder.indexOf(currentStep);
    if (currentStep === 'review') {
        currentIndex = stepOrder.indexOf('review');
    }

    stepOrder.forEach((stepName, index) => {
        const stepElement = steps[stepName];
        if (!stepElement) return;

        stepElement.classList.remove('active', 'completed');

        if (currentStep === 'review' && stepName === 'script') {
            stepElement.classList.add('completed');
        } else if (index < currentIndex) {
            stepElement.classList.add('completed');
        } else if (index === currentIndex) {
            stepElement.classList.add('active');
        }
    });
}

function showResumeOption(data) {
    progressSection.classList.remove('hidden');
    resumeSection.classList.remove('hidden');
    addLog(data.message || 'Job interrupted — you can resume rendering.', 'error');
    if (data.scenes_done != null && data.scenes_total) {
        addLog(`→ ${data.scenes_done}/${data.scenes_total} scenes completed before interruption`);
    }
    resetForm();
}

async function resumeCurrentJob() {
    if (!currentJobId) return;
    resumeJobBtn.disabled = true;
    try {
        const statusResponse = await fetch(`${API_BASE_URL}/api/progress/${currentJobId}`);
        const statusData = await statusResponse.json();
        if (!statusData.can_resume) {
            throw new Error(statusData.error || statusData.message || 'This job cannot be resumed.');
        }
    } catch (error) {
        addLog(`✗ ${error.message}`, 'error');
        resumeSection.classList.remove('hidden');
        resumeJobBtn.disabled = false;
        return;
    }

    resumeSection.classList.add('hidden');
    renderStarted = true;
    progressSection.classList.remove('hidden');
    generateBtn.disabled = true;
    addLog('Resuming render from checkpoint...', 'success');
    try {
        const response = await fetch(`${API_BASE_URL}/api/jobs/${currentJobId}/resume`, { method: 'POST' });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || 'Resume failed');
        }
        startProgressPolling();
    } catch (error) {
        addLog(`✗ ${error.message}`, 'error');
        resumeSection.classList.remove('hidden');
    } finally {
        resumeJobBtn.disabled = false;
    }
}

if (resumeJobBtn) {
    resumeJobBtn.addEventListener('click', resumeCurrentJob);
}

function collectScriptFromEditor() {
    return Array.from(scriptScenesEl.querySelectorAll('.scene-card')).map((card) => {
        const scene = {
            text: card.querySelector('.scene-text').value.trim(),
            animation: card.querySelector('.scene-animation').value.trim(),
        };
        const chapterInput = card.querySelector('.scene-chapter-input');
        const titleInput = card.querySelector('.scene-title-input');
        if (chapterInput && chapterInput.value.trim()) {
            scene.chapter = chapterInput.value.trim();
        }
        if (titleInput && titleInput.value.trim()) {
            scene.title = titleInput.value.trim();
        }
        const codeInput = card.querySelector('.scene-code-area');
        const classInput = card.querySelector('.scene-code-class');
        if (codeInput && codeInput.value.trim()) {
            scene.code = codeInput.value.trim();
        }
        if (classInput && classInput.value.trim()) {
            scene.code_class = classInput.value.trim();
        }
        const events = (card.dataset.visualEvents || '').split(',').map((e) => e.trim()).filter(Boolean);
        if (events.length) scene.visual_events = events;
        // Style overrides
        const palette = card.querySelector('.scene-style-palette')?.value;
        const speed = card.querySelector('.scene-style-speed')?.value;
        const fontSize = card.querySelector('.scene-style-font-size')?.value;
        if (palette || speed || fontSize) {
            scene.style = {};
            if (palette) scene.style.palette = palette;
            if (speed) scene.style.speed = speed;
            if (fontSize) scene.style.font_size = parseInt(fontSize, 10);
        }
        return scene;
    });
}

function buildVisualEventsEditor(selectedEvents = []) {
    const catalog = serverConfig?.visual_events || [];
    const selected = new Set(selectedEvents);
    const container = document.createElement('div');
    container.className = 'scene-events-editor';
    catalog.forEach((item) => {
        const chip = document.createElement('span');
        chip.className = `scene-event-chip${selected.has(item.id) ? ' selected' : ''}`;
        chip.textContent = item.id.replace(/_/g, ' ');
        chip.title = item.description;
        chip.dataset.eventId = item.id;
        chip.addEventListener('click', () => {
            chip.classList.toggle('selected');
            const card = chip.closest('.scene-card');
            if (card) {
                const ids = Array.from(card.querySelectorAll('.scene-event-chip.selected'))
                    .map((el) => el.dataset.eventId);
                card.dataset.visualEvents = ids.join(',');
            }
        });
        container.appendChild(chip);
    });
    return container;
}

function renderScriptEditor(script, allowSceneRetry = false) {
    scriptScenesEl.innerHTML = '';
    let lastChapter = null;
    script.forEach((scene, index) => {
        const chapter = scene.chapter || null;
        if (chapter && chapter !== lastChapter) {
            const header = document.createElement('div');
            header.className = 'chapter-header';
            header.textContent = chapter;
            scriptScenesEl.appendChild(header);
            lastChapter = chapter;
        }
        addSceneCard(scene, index + 1, allowSceneRetry);
    });
}

function addSceneCard(scene = { text: '', animation: '' }, sceneNumber = null, allowSceneRetry = false) {
    const index = sceneNumber || scriptScenesEl.querySelectorAll('.scene-card').length + 1;
    const events = scene.visual_events || [];
    const card = document.createElement('div');
    card.className = 'scene-card';
    card.dataset.visualEvents = events.join(',');
    card.innerHTML = `
        <div class="scene-card-header">
            <strong>Scene ${index}${scene.title ? `: ${escapeHtml(scene.title)}` : ''}</strong>
            <div>
                ${allowSceneRetry ? `<button type="button" class="scene-retry-btn" data-scene="${index}">Re-render</button>` : ''}
                <button type="button" class="scene-remove-btn">Remove</button>
            </div>
        </div>
        <div class="scene-events-wrap"></div>
        <label>Chapter (optional)</label>
        <input type="text" class="scene-chapter-input" placeholder="e.g., Introduction" value="${escapeHtml(scene.chapter)}" />
        <label>Scene title (optional)</label>
        <input type="text" class="scene-title-input" placeholder="e.g., The derivative" value="${escapeHtml(scene.title)}" />
        <label>Narration</label>
        <textarea class="scene-text" placeholder="What the narrator says...">${escapeHtml(scene.text)}</textarea>
        <label>Animation</label>
        <textarea class="scene-animation" placeholder="What appears on screen...">${escapeHtml(scene.animation)}</textarea>
        <div class="scene-style-section">
            <button type="button" class="scene-style-toggle" data-expanded="false">Style Overrides ▼</button>
            <div class="scene-style-panel hidden">
                <div class="form-row" style="grid-template-columns: 1fr 1fr; gap: 10px;">
                    <div class="form-group">
                        <label style="font-size:11px;">Color Palette</label>
                        <select class="scene-style-palette form-select" style="font-size:12px; padding:6px;">
                            <option value="">Default</option>
                            <option value="warm">Warm (oranges/reds)</option>
                            <option value="cool">Cool (blues/greens)</option>
                            <option value="monochrome">Monochrome (grays)</option>
                            <option value="vibrant">Vibrant (high contrast)</option>
                            <option value="pastel">Pastel (soft tones)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label style="font-size:11px;">Animation Speed</label>
                        <select class="scene-style-speed form-select" style="font-size:12px; padding:6px;">
                            <option value="">Default</option>
                            <option value="slow">Slow (2× duration)</option>
                            <option value="normal">Normal</option>
                            <option value="fast">Fast (0.5× duration)</option>
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label style="font-size:11px;">Font Size Override (px)</label>
                    <input type="number" class="scene-style-font-size topic-input" style="font-size:12px; padding:6px;" placeholder="e.g., 36" min="12" max="72" value="${escapeHtml(scene.style?.font_size || '')}" />
                </div>
            </div>
        </div>
        <div class="scene-code-section">
            <button type="button" class="scene-code-toggle" data-expanded="false">Manim Code ▼</button>
            <div class="scene-code-panel hidden">
                <label>Class Name</label>
                <input type="text" class="scene-code-class" placeholder="MyScene" value="${escapeHtml(scene.code_class || '')}" />
                <label>Manim Python Code</label>
                <textarea class="scene-code-area" placeholder="from manim import *\n\nclass MyScene(Scene):\n    def construct(self):\n        ...">${escapeHtml(scene.code || '')}</textarea>
                <div class="scene-code-actions">
                    <button type="button" class="scene-preview-btn">▶ Preview</button>
                    <span class="scene-code-status"></span>
                </div>
            </div>
        </div>
    `;
    const eventsWrap = card.querySelector('.scene-events-wrap');
    eventsWrap.innerHTML = '<label>Visual events (click to toggle)</label>';
    eventsWrap.appendChild(buildVisualEventsEditor(events));
    card.querySelector('.scene-remove-btn').addEventListener('click', () => {
        if (scriptScenesEl.querySelectorAll('.scene-card').length <= 2) {
            alert('Keep at least 2 scenes.');
            return;
        }
        card.remove();
        Array.from(scriptScenesEl.querySelectorAll('.scene-card')).forEach((el, i) => {
            const strong = el.querySelector('strong');
            const titleInput = el.querySelector('.scene-title-input');
            const titleSuffix = titleInput?.value.trim() ? `: ${titleInput.value.trim()}` : '';
            strong.textContent = `Scene ${i + 1}${titleSuffix}`;
        });
    });
    const retryBtn = card.querySelector('.scene-retry-btn');
    if (retryBtn) {
        retryBtn.addEventListener('click', async () => {
            if (!currentJobId) return;
            retryBtn.disabled = true;
            try {
                const response = await fetch(
                    `${API_BASE_URL}/api/jobs/${currentJobId}/scenes/${index}/retry`,
                    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }
                );
                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.error || 'Retry failed');
                }
                progressSection.classList.remove('hidden');
                renderStarted = true;
                startProgressPolling();
            } catch (error) {
                alert(error.message);
            } finally {
                retryBtn.disabled = false;
            }
        });
    }

    // Style overrides toggle
    const styleToggle = card.querySelector('.scene-style-toggle');
    const stylePanel = card.querySelector('.scene-style-panel');
    if (styleToggle && stylePanel) {
        styleToggle.addEventListener('click', () => {
            const expanded = styleToggle.dataset.expanded === 'true';
            styleToggle.dataset.expanded = String(!expanded);
            stylePanel.classList.toggle('hidden');
            styleToggle.textContent = expanded ? 'Style Overrides ▼' : 'Style Overrides ▲';
        });
    }

    // Manim code toggle
    const codeToggle = card.querySelector('.scene-code-toggle');
    const codePanel = card.querySelector('.scene-code-panel');
    if (codeToggle && codePanel) {
        codeToggle.addEventListener('click', () => {
            const expanded = codeToggle.dataset.expanded === 'true';
            codeToggle.dataset.expanded = String(!expanded);
            codePanel.classList.toggle('hidden');
            codeToggle.textContent = expanded ? 'Manim Code ▼' : 'Manim Code ▲';
        });
    }

    // Preview code button
    const previewBtn = card.querySelector('.scene-preview-btn');
    const codeStatus = card.querySelector('.scene-code-status');
    if (previewBtn) {
        previewBtn.addEventListener('click', async () => {
            const code = card.querySelector('.scene-code-area')?.value.trim();
            const className = card.querySelector('.scene-code-class')?.value.trim();
            if (!code) {
                codeStatus.textContent = 'Paste Manim code first';
                return;
            }
            if (!className) {
                codeStatus.textContent = 'Enter class name';
                return;
            }
            previewBtn.disabled = true;
            codeStatus.textContent = 'Compiling…';
            try {
                const topic = importTitleInput.value.trim() || topicInput.value.trim() || 'Preview';
                const response = await fetch(`${API_BASE_URL}/api/preview-code`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code, class_name: className, topic, quality: 'preview' }),
                });
                const data = await response.json().catch(() => ({}));
                if (!response.ok) {
                    throw new Error(data.error || `Compilation failed (${response.status})`);
                }
                if (data.video_url) {
                    showCodePreviewModal(data.video_url, className);
                    codeStatus.textContent = '';
                } else {
                    throw new Error('No video returned');
                }
            } catch (err) {
                codeStatus.textContent = err.message;
            } finally {
                previewBtn.disabled = false;
            }
        });
    }

    scriptScenesEl.appendChild(card);
}

function showScriptReview(script, recovered = false) {
    importDraftMode = false;
    updateProgressBar(25);
    updateSteps('review');
    if (recovered) {
        addLog('Recovered script after server restart — review before approving.', 'error');
    } else {
        addLog('Script ready for review — edit scenes below, then approve.', 'success');
    }
    renderScriptEditor(script);
    scriptReviewSection.classList.remove('hidden');
    updateGenerateButtonHint();
    scriptReviewSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    resetForm();
    debouncedLintScript();
}

async function previewSceneOne(sceneIndex = 1) {
    const script = collectScriptFromEditor();
    if (!script.length) {
        alert('Add at least one scene first.');
        return;
    }
    if (sceneIndex < 1 || sceneIndex > script.length) {
        alert(`Scene ${sceneIndex} does not exist.`);
        return;
    }
    const scene = script[sceneIndex - 1];
    if (!scene.text?.trim() || !scene.animation?.trim()) {
        alert(`Scene ${sceneIndex} needs both narration and visual instructions.`);
        return;
    }

    syncEditorToTextarea();
    previewSceneBtn.disabled = true;
    previewSceneBtn.textContent = 'Rendering preview...';
    progressSection.classList.remove('hidden');
    resultSection.classList.add('hidden');
    resetProgress();
    addLog(`→ Starting fast preview for scene ${sceneIndex}...`, 'info');

    try {
        const topic = importTitleInput.value.trim() || topicInput.value.trim() || parsedImportPreview?.title || 'Scene Preview';
        const response = await fetch(`${API_BASE_URL}/api/preview-scene`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic,
                script,
                scene_index: sceneIndex,
                llm_provider: llmSelect.value,
                llm_model: getSelectedLlmModel(),
                tts_provider: ttsSelect.value,
                tts_voice: getSelectedTtsVoice(),
                enable_tts: ttsToggle.checked,
                video_settings: getVideoSettings(),
            }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Preview failed to start');
        }

        currentJobId = data.job_id;
        localStorage.setItem('t2m_current_job', currentJobId);
        renderStarted = true;
        startProgressPolling({ preview: true });
    } catch (error) {
        addLog(`✗ ${error.message}`, 'error');
    } finally {
        previewSceneBtn.disabled = false;
        previewSceneBtn.textContent = 'Preview Scene 1';
    }
}

if (previewSceneBtn) {
    previewSceneBtn.addEventListener('click', () => previewSceneOne(1));
}

scriptScenesEl.addEventListener('input', () => {
    syncEditorToTextarea();
    updateGenerateButtonHint();
    debouncedLintScript();
});

let lintTimeout = null;
async function lintScript() {
    if (!linterPanel || !linterMetrics) return;
    const script = collectScriptFromEditor();
    if (!script.length) return;
    try {
        const response = await fetch(`${API_BASE_URL}/api/metrics/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scenes: script, topic: topicInput.value.trim() || importTitleInput.value.trim() || '' }),
        });
        if (!response.ok) return;
        const data = await response.json();
        if (data.error) return;

        const retention = data.retention_prediction?.predicted_retention_pct ?? 0;
        const wpm = data.overall_wpm ?? 0;
        const wordCount = data.total_words ?? 0;
        const sceneCount = data.scene_count ?? 0;
        const readability = data.readability?.flesch_reading_ease ?? 0;

        const retentionClass = retention >= 60 ? 'good' : retention >= 45 ? 'warn' : 'bad';
        const wpmClass = wpm >= 120 && wpm <= 160 ? 'good' : wpm >= 100 && wpm <= 200 ? 'warn' : 'bad';
        const readClass = readability >= 60 ? 'good' : readability >= 40 ? 'warn' : 'bad';

        linterMetrics.innerHTML = `
            <div class="linter-metric">
                <span class="linter-metric-value ${retentionClass}">${retention}%</span>
                <span class="linter-metric-label">Retention</span>
            </div>
            <div class="linter-metric">
                <span class="linter-metric-value ${wpmClass}">${Math.round(wpm)}</span>
                <span class="linter-metric-label">WPM</span>
            </div>
            <div class="linter-metric">
                <span class="linter-metric-value ${readClass}">${Math.round(readability)}</span>
                <span class="linter-metric-label">Readability</span>
            </div>
            <div class="linter-metric">
                <span class="linter-metric-value">${wordCount}</span>
                <span class="linter-metric-label">Words</span>
            </div>
            <div class="linter-metric">
                <span class="linter-metric-value">${sceneCount}</span>
                <span class="linter-metric-label">Scenes</span>
            </div>
        `;

        const suggestions = data.suggestions || [];
        if (suggestions.length) {
            linterSuggestions.innerHTML = suggestions.slice(0, 3).map(s => `<div class="linter-suggestion">${escapeHtml(s)}</div>`).join('');
            linterSuggestions.classList.remove('hidden');
        } else {
            linterSuggestions.classList.add('hidden');
        }
        linterPanel.classList.remove('hidden');
    } catch (err) {
        // Silently fail — linter is advisory
    }
}
function debouncedLintScript() {
    clearTimeout(lintTimeout);
    lintTimeout = setTimeout(lintScript, 800);
}

addSceneBtn.addEventListener('click', () => addSceneCard());

approveScriptBtn.addEventListener('click', async () => {
    const script = collectScriptFromEditor();

    for (let i = 0; i < script.length; i++) {
        if (!script[i].text || !script[i].animation) {
            addLog(`✗ Scene ${i + 1} is missing narration or animation text`, 'error');
            return;
        }
    }
    if (script.length < 2) {
        addLog('✗ Script must have at least 2 scenes', 'error');
        return;
    }

    approveScriptBtn.disabled = true;
    approveScriptBtn.textContent = 'Starting render...';

    try {
        if (importDraftMode && !currentJobId) {
            await submitVideoGeneration({ scriptOverride: script, skipReview: true });
            return;
        }

        const response = await fetch(`${API_BASE_URL}/api/jobs/${currentJobId}/continue`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ script }),
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || 'Failed to continue generation');
        }

        scriptReviewSection.classList.add('hidden');
        generateBtn.disabled = true;
        renderStarted = true;
        lastLoggedMessage = '';
        addLog('Script approved — rendering video...', 'success');
        startProgressPolling();
    } catch (error) {
        addLog(`✗ ${error.message}`, 'error');
    } finally {
        approveScriptBtn.disabled = false;
        approveScriptBtn.textContent = 'Approve & Render Video';
    }
});

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
    lastLoggedMessage = '';
    Object.values(steps).forEach(step => {
        if (step) step.classList.remove('active', 'completed');
    });
    progressLog.innerHTML = '';
}

function resetForm() {
    generateBtn.disabled = false;
    const label = inputMode === 'import' ? 'Generate from Script' : 'Generate Video';
    generateBtn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
        ${label}
    `;
}

// Fetch and display quality metrics
async function fetchAndShowMetrics(jobId) {
    if (!metricsPanel || !metricsGrid) return;
    try {
        const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/metrics`);
        if (!response.ok) return;
        const data = await response.json();
        if (data.error) return;

        const retention = data.retention_prediction?.predicted_retention_pct ?? 0;
        const readability = data.readability?.flesch_reading_ease ?? 0;
        const wpm = data.overall_wpm ?? 0;
        const wordCount = data.total_words ?? 0;
        const sceneCount = data.scene_count ?? 0;

        const retentionClass = retention >= 60 ? 'good' : retention >= 45 ? 'warn' : 'bad';
        const readabilityClass = readability >= 60 ? 'good' : readability >= 40 ? 'warn' : 'bad';
        const wpmClass = wpm >= 120 && wpm <= 160 ? 'good' : wpm >= 100 && wpm <= 200 ? 'warn' : 'bad';

        metricsGrid.innerHTML = `
            <div class="metric-card ${retentionClass}">
                <div class="metric-value">${retention}%</div>
                <div class="metric-label">Predicted Retention</div>
            </div>
            <div class="metric-card ${readabilityClass}">
                <div class="metric-value">${Math.round(readability)}</div>
                <div class="metric-label">Readability Score</div>
            </div>
            <div class="metric-card ${wpmClass}">
                <div class="metric-value">${Math.round(wpm)}</div>
                <div class="metric-label">Words/Min</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${wordCount}</div>
                <div class="metric-label">Total Words</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${sceneCount}</div>
                <div class="metric-label">Scenes</div>
            </div>
        `;

        const suggestions = data.suggestions || [];
        if (suggestions.length) {
            metricsSuggestions.innerHTML = suggestions.map(s => `<div class="suggestion">${escapeHtml(s)}</div>`).join('');
            metricsSuggestions.classList.remove('hidden');
        } else {
            metricsSuggestions.classList.add('hidden');
        }
        metricsPanel.classList.remove('hidden');
    } catch (err) {
        console.warn('Could not load metrics:', err);
    }
}

// Fetch and display thumbnails
async function fetchAndShowThumbnails(jobId) {
    if (!thumbnailsPanel || !thumbnailsGrid) return;
    try {
        const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/thumbnails`);
        if (!response.ok) return;
        const data = await response.json();
        if (data.timeline) {
            timelineImage.src = data.timeline;
            timelineImage.classList.remove('hidden');
        } else {
            timelineImage.classList.add('hidden');
        }
        if (data.thumbnails?.length) {
            thumbnailsGrid.innerHTML = data.thumbnails.map(url => `
                <div class="thumb-item"><img src="${escapeHtml(url)}" alt="scene thumbnail" loading="lazy"></div>
            `).join('');
            thumbnailsPanel.classList.remove('hidden');
        }
    } catch (err) {
        console.warn('Could not load thumbnails:', err);
    }
}

// Show result
function showResult(videoUrl, options = {}) {
    const isPreview = options.preview;
    const htmlUrl = options.htmlUrl;
    addLog(isPreview ? '✓ Scene preview ready!' : '✓ Video generation completed!', 'success');

    updateProgressBar(100);
    Object.values(steps).forEach(step => {
        step.classList.add('completed');
        step.classList.remove('active');
    });

    setTimeout(() => {
        resultSection.classList.remove('hidden');
        const titleEl = resultSection.querySelector('.result-title');
        if (titleEl) {
            titleEl.textContent = isPreview
                ? 'Scene 1 Preview (fast quality)'
                : '✨ Video Generated Successfully!';
        }
        resultVideo.src = videoUrl;
        downloadBtn.href = videoUrl;
        if (htmlPlayerBtn) {
            if (htmlUrl) {
                htmlPlayerBtn.href = htmlUrl;
                htmlPlayerBtn.classList.remove('hidden');
            } else {
                htmlPlayerBtn.classList.add('hidden');
            }
        }

        // Hide metrics/thumbnails on preview, show on full render
        if (isPreview) {
            metricsPanel?.classList.add('hidden');
            thumbnailsPanel?.classList.add('hidden');
        } else if (currentJobId) {
            fetchAndShowMetrics(currentJobId);
            fetchAndShowThumbnails(currentJobId);
        }

        resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        if (!isPreview) {
            resetForm();
        }
        loadRecentJobs();
    }, isPreview ? 300 : 1000);
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
