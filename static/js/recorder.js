// ---------------------------------------------------------------------------
// Audio recording (MediaRecorder)
// ---------------------------------------------------------------------------

import { state, dom, API, authHeaders, setStatus } from './app.js';
import { appendMsg, sendToRainViaWS, resetRecordBtn } from './chat.js';

async function initAudio() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }
        });

        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : MediaRecorder.isTypeSupported('audio/webm')
                ? 'audio/webm'
                : MediaRecorder.isTypeSupported('audio/mp4')
                    ? 'audio/mp4'
                    : '';

        const options = mimeType ? { mimeType } : {};
        state.mediaRecorder = new MediaRecorder(stream, options);

        state.mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) state.audioChunks.push(e.data);
        };

        state.mediaRecorder.onstop = async () => {
            const blob = new Blob(state.audioChunks, { type: state.mediaRecorder.mimeType });
            state.audioChunks = [];
            if (blob.size < 3000) {
                setStatus('ready', 'Recording too short');
                resetRecordBtn();
                return;
            }
            await sendAudio(blob);
        };

        dom.recordBtn.disabled = false;
    } catch (err) {
        console.error('Audio init error:', err);
        dom.recordBtn.textContent = 'Mic unavailable';
        dom.recordBtn.disabled = true;
    }
}

function startRecording() {
    if (state.isRecording || state.isProcessing || !state.mediaRecorder) return;
    state.audioChunks = [];
    state.mediaRecorder.start(100);
    state.isRecording = true;
    dom.recordBtn.textContent = 'Recording... Release to Send';
    dom.recordBtn.classList.add('recording');
}

function stopRecording() {
    if (!state.isRecording || !state.mediaRecorder) return;
    state.mediaRecorder.stop();
    state.isRecording = false;
    dom.recordBtn.textContent = 'Transcribing...';
    dom.recordBtn.classList.remove('recording');
    dom.recordBtn.classList.add('processing');
    dom.recordBtn.disabled = true;
}

async function sendAudio(blob) {
    setStatus('connected', 'Transcribing...');
    const fd = new FormData();
    fd.append('audio', blob, 'recording.webm');

    try {
        const res = await fetch(`${API}/upload-audio`, { method: 'POST', body: fd, headers: authHeaders() });
        const data = await res.json();

        if (data.text && data.text.trim()) {
            appendMsg('user', data.text.trim());
            sendToRainViaWS(data.text.trim());
        } else {
            setStatus('ready', 'No speech detected');
            resetRecordBtn();
        }
    } catch {
        setStatus('error', 'Transcription failed');
        resetRecordBtn();
    }
}

export function initRecorder() {
    dom.recordBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); }, { passive: false });
    dom.recordBtn.addEventListener('touchend', (e) => { e.preventDefault(); stopRecording(); }, { passive: false });
    dom.recordBtn.addEventListener('mousedown', startRecording);
    dom.recordBtn.addEventListener('mouseup', stopRecording);
    dom.recordBtn.addEventListener('mouseleave', () => { if (state.isRecording) stopRecording(); });

    initAudio();
}
