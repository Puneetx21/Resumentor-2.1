let timerInterval = null;
let elapsed = 0;
let interviewActive = false;
let questionStartTs = null;

let recognition = null;
let isListening = false;

// Text-to-Speech variables
let synth = window.speechSynthesis;
let isSpeaking = false;
let currentQuestionText = '';

function formatTime(sec) {
    const m = String(Math.floor(sec / 60)).padStart(2, '0');
    const s = String(sec % 60).padStart(2, '0');
    return `${m}:${s}`;
}

function startTimer() {
    elapsed = 0;
    document.getElementById('timer').textContent = '00:00';
    timerInterval = setInterval(() => {
        elapsed += 1;
        document.getElementById('timer').textContent = formatTime(elapsed);
    }, 1000);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

function appendTranscript(speaker, text) {
    const block = document.createElement('div');
    block.style.marginBottom = '0.6rem';
    block.innerHTML = `
        <div style="font-size:0.78rem; color: var(--text-secondary); margin-bottom:0.15rem;">${speaker}</div>
        <div style="padding:0.55rem 0.7rem; border-radius: 10px; background:${speaker === 'Interviewer' ? 'rgba(59,130,246,0.12)' : 'rgba(16,185,129,0.12)'}; border-left:3px solid ${speaker === 'Interviewer' ? '#3b82f6' : '#10b981'};">${text}</div>
    `;
    const container = document.getElementById('transcript');
    container.appendChild(block);
    container.scrollTop = container.scrollHeight;
}

function speakQuestion(text) {
    if (!synth) return;
    
    // Cancel any ongoing speech
    synth.cancel();
    
    currentQuestionText = text;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.95; // Slightly slower for clarity
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    
    utterance.onstart = () => {
        isSpeaking = true;
        document.getElementById('speakBtn').disabled = true;
        document.getElementById('speakBtn').style.display = 'none';
        document.getElementById('stopSpeakBtn').style.display = 'inline-block';
        document.getElementById('stopSpeakBtn').disabled = false;
    };
    
    utterance.onend = () => {
        isSpeaking = false;
        document.getElementById('speakBtn').disabled = false;
        document.getElementById('speakBtn').style.display = 'inline-block';
        document.getElementById('stopSpeakBtn').style.display = 'none';
        document.getElementById('stopSpeakBtn').disabled = true;
    };
    
    utterance.onerror = () => {
        isSpeaking = false;
        document.getElementById('speakBtn').disabled = false;
        document.getElementById('speakBtn').style.display = 'inline-block';
        document.getElementById('stopSpeakBtn').style.display = 'none';
        document.getElementById('stopSpeakBtn').disabled = true;
    };
    
    synth.speak(utterance);
}

function stopSpeaking() {
    if (synth && isSpeaking) {
        synth.cancel();
        isSpeaking = false;
        document.getElementById('speakBtn').disabled = false;
        document.getElementById('speakBtn').style.display = 'inline-block';
        document.getElementById('stopSpeakBtn').style.display = 'none';
        document.getElementById('stopSpeakBtn').disabled = true;
    }
}

function setCurrentQuestion(question) {
    document.getElementById('questionBox').textContent = question.text;
    document.getElementById('questionRound').textContent = question.round_label;
    document.getElementById('questionMeta').textContent = `Question ${question.index}/${question.total}`;
    appendTranscript('Interviewer', question.text);
    questionStartTs = Date.now();
    
    // Auto-speak the question when it appears
    if (interviewActive) {
        setTimeout(() => speakQuestion(question.text), 300);
    }
}

async function callApi(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };
    if (body) options.body = JSON.stringify(body);
    const res = await fetch(url, options);
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.error || 'Request failed');
    }
    return data;
}

function selectedMode() {
    const node = document.querySelector('input[name="answerMode"]:checked');
    return node ? node.value : 'text';
}

function updateModeUi() {
    const mode = selectedMode();
    document.getElementById('recordBtn').disabled = (mode !== 'oral') || !interviewActive;
}

function initSpeech() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        return;
    }

    recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.continuous = false;

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript || '';
        const box = document.getElementById('answerInput');
        box.value = box.value ? `${box.value} ${transcript}` : transcript;
    };

    recognition.onend = () => {
        isListening = false;
        document.getElementById('recordBtn').innerHTML = '<i class="fas fa-microphone"></i> Speak';
    };
}

document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('startBtn');
    const endBtn = document.getElementById('endBtn');
    const nextBtn = document.getElementById('nextBtn');
    const answerInput = document.getElementById('answerInput');
    const roleSelect = document.getElementById('jobRole');
    const recordBtn = document.getElementById('recordBtn');
    const speakBtn = document.getElementById('speakBtn');
    const stopSpeakBtn = document.getElementById('stopSpeakBtn');
    const feedbackBox = document.getElementById('lastFeedback');

    initSpeech();

    speakBtn.addEventListener('click', () => {
        if (currentQuestionText) {
            speakQuestion(currentQuestionText);
        }
    });

    stopSpeakBtn.addEventListener('click', stopSpeaking);

    document.querySelectorAll('input[name="answerMode"]').forEach((node) => {
        node.addEventListener('change', updateModeUi);
    });

    recordBtn.addEventListener('click', () => {
        if (!recognition) {
            alert('Oral mode is not supported in this browser. Please type your answer.');
            return;
        }
        if (!interviewActive) return;

        if (isListening) {
            recognition.stop();
            return;
        }

        isListening = true;
        recordBtn.innerHTML = '<i class="fas fa-circle"></i> Listening';
        recognition.start();
    });

    startBtn.addEventListener('click', async () => {
        try {
            const role = roleSelect.value;
            const data = await callApi('/api/interview/start', 'POST', { job_role: role });

            interviewActive = true;
            startBtn.disabled = true;
            endBtn.disabled = false;
            nextBtn.disabled = false;
            roleSelect.disabled = true;
            answerInput.value = '';
            feedbackBox.style.display = 'none';
            document.getElementById('transcript').innerHTML = '';

            setCurrentQuestion(data.question);
            startTimer();
            updateModeUi();

            const hint = data.resume_context_used
                ? 'Resume analysis was found for this role and used as context for evaluation.'
                : 'No prior resume analysis found for this role. Interview is running in standalone mode.';
            document.getElementById('contextHint').textContent = hint;
        } catch (err) {
            alert(err.message);
        }
    });

    nextBtn.addEventListener('click', async () => {
        const answer = answerInput.value.trim();
        if (!answer) {
            alert('Please answer the question before moving next.');
            return;
        }

        const mode = selectedMode();
        const responseSeconds = questionStartTs ? Math.max(0, Math.round((Date.now() - questionStartTs) / 1000)) : 0;

        try {
            appendTranscript('You', answer);
            const data = await callApi('/api/interview/answer', 'POST', {
                answer,
                answer_mode: mode,
                response_seconds: responseSeconds,
            });

            answerInput.value = '';

            if (data.complete) {
                stopTimer();
                interviewActive = false;
                startBtn.disabled = false;
                endBtn.disabled = true;
                nextBtn.disabled = true;
                roleSelect.disabled = false;
                updateModeUi();
                window.location.href = data.redirect_url;
                return;
            }

            if (data.last_feedback) {
                feedbackBox.style.display = 'block';
                feedbackBox.textContent = `Feedback: ${data.last_feedback} (Score: ${data.last_score}/100)`;
            }

            setCurrentQuestion(data.question);
            answerInput.focus();
        } catch (err) {
            alert(err.message);
        }
    });

    endBtn.addEventListener('click', async () => {
        if (!interviewActive) return;

        try {
            const data = await callApi('/api/interview/end', 'POST');
            stopTimer();
            interviewActive = false;
            startBtn.disabled = false;
            endBtn.disabled = true;
            nextBtn.disabled = true;
            roleSelect.disabled = false;
            updateModeUi();
            window.location.href = data.redirect_url;
        } catch (err) {
            alert(err.message);
        }
    });
});
