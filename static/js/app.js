/* ═══════════════════════════════════════════════════════
   J.A.R.V.I.S. — Frontend Application
   Voice + Text + WebSocket + PWA
   ═══════════════════════════════════════════════════════ */

(() => {
    'use strict';

    // ── DOM Elements ──────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const loginScreen    = $('#login-screen');
    const mainScreen     = $('#main-screen');
    const passwordInput  = $('#password-input');
    const loginBtn       = $('#login-btn');
    const loginError     = $('#login-error');
    const chatArea       = $('#chat-area');
    const textInput      = $('#text-input');
    const sendBtn        = $('#send-btn');
    const orb            = $('#jarvis-orb');
    const orbLabel       = $('#orb-label');
    const clock          = $('#clock');
    const connStatus     = $('#connection-status');
    const toast          = $('#notification-toast');
    const toastTitle     = $('#toast-title');
    const toastBody      = $('#toast-body');

    // ── State ─────────────────────────────────────────
    let ws = null;
    let token = localStorage.getItem('jarvis_token');
    let isListening = false;
    let isProcessing = false;
    let isSpeaking = false;
    let currentAudio = null;
    let recognition = null;

    // ── Clock ─────────────────────────────────────────
    function updateClock() {
        const now = new Date();
        clock.textContent = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
    }
    setInterval(updateClock, 1000);
    updateClock();

    // ═══════════════════════════════════════════════════
    //  AUTH
    // ═══════════════════════════════════════════════════
    async function login(password) {
        try {
            const base = location.origin;
            const res = await fetch(`${base}/api/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            if (!res.ok) {
                loginError.textContent = 'Access denied.';
                return;
            }
            const data = await res.json();
            token = data.token;
            localStorage.setItem('jarvis_token', token);
            showMain();
        } catch (e) {
            loginError.textContent = 'Connection failed. Is the server running?';
        }
    }

    function showMain() {
        loginScreen.classList.remove('active');
        mainScreen.classList.add('active');
        connectWebSocket();
    }

    loginBtn.addEventListener('click', () => login(passwordInput.value));
    passwordInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') login(passwordInput.value);
    });

    // Auto-login if token exists
    if (token) {
        showMain();
    }

    // ═══════════════════════════════════════════════════
    //  WEBSOCKET
    // ═══════════════════════════════════════════════════
    function connectWebSocket() {
        const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
        ws = new WebSocket(`${protocol}://${location.host}/ws`);

        ws.onopen = () => {
            connStatus.classList.add('connected');
            // First message: auth token
            ws.send(JSON.stringify({ token }));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            switch (data.type) {
                case 'response':
                    removeProcessing();
                    addMessage('jarvis', data.text);
                    if (data.audio) playAudio(data.audio);
                    if (data.action) handleAction(data.action);
                    break;

                case 'status':
                    if (data.state === 'processing') {
                        showProcessing();
                        setOrbState('processing');
                    }
                    break;

                case 'notification':
                    showNotification(data.title, data.body);
                    break;

                case 'error':
                    removeProcessing();
                    addMessage('jarvis', data.message || 'Something went wrong, Sir.');
                    break;
            }
        };

        ws.onclose = () => {
            connStatus.classList.remove('connected');
            // Reconnect after 3 seconds
            setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = () => {
            connStatus.classList.remove('connected');
        };
    }

    function sendMessage(text) {
        if (!text.trim() || !ws || ws.readyState !== WebSocket.OPEN) return;
        addMessage('user', text);
        ws.send(JSON.stringify({ type: 'chat', text }));
        setOrbState('processing');
    }

    function sendAction(skill) {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        ws.send(JSON.stringify({ type: 'action', skill }));
        showProcessing();
        setOrbState('processing');
    }

    // ── Handle server actions ─────────────────────────
    function handleAction(action) {
        if (action.type === 'open_url' && action.url) {
            window.open(action.url, '_blank');
        }
        // local_command actions are handled by the local agent, not the browser
    }

    // ═══════════════════════════════════════════════════
    //  CHAT UI
    // ═══════════════════════════════════════════════════
    function addMessage(sender, text) {
        const div = document.createElement('div');
        div.className = `chat-msg ${sender}`;
        const label = sender === 'user' ? 'YOU' : 'JARVIS';
        div.innerHTML = `<div class="msg-label">${label}</div><div>${escapeHtml(text)}</div>`;
        chatArea.appendChild(div);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function showProcessing() {
        const div = document.createElement('div');
        div.className = 'chat-msg jarvis processing-msg';
        div.innerHTML = `<div class="msg-label">JARVIS</div><div class="processing-dots"><span></span><span></span><span></span></div>`;
        chatArea.appendChild(div);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function removeProcessing() {
        const el = chatArea.querySelector('.processing-msg');
        if (el) el.remove();
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ═══════════════════════════════════════════════════
    //  AUDIO PLAYBACK
    // ═══════════════════════════════════════════════════
    function playAudio(base64) {
        try {
            if (currentAudio) { currentAudio.pause(); currentAudio = null; }
            const bytes = atob(base64);
            const buffer = new Uint8Array(bytes.length);
            for (let i = 0; i < bytes.length; i++) buffer[i] = bytes.charCodeAt(i);
            const blob = new Blob([buffer], { type: 'audio/mp3' });
            const url = URL.createObjectURL(blob);
            currentAudio = new Audio(url);
            setOrbState('speaking');
            currentAudio.play().catch(() => {});
            currentAudio.onended = () => {
                setOrbState('idle');
                URL.revokeObjectURL(url);
                currentAudio = null;
            };
        } catch (e) {
            console.error('Audio playback error:', e);
            setOrbState('idle');
        }
    }

    // ═══════════════════════════════════════════════════
    //  VOICE INPUT (Web Speech API)
    // ═══════════════════════════════════════════════════
    function initSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            console.warn('Speech recognition not supported');
            return;
        }

        recognition = new SpeechRecognition();
        recognition.lang = 'en-IN';
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onresult = (event) => {
            const text = event.results[0][0].transcript;
            isListening = false;
            setOrbState('processing');
            sendMessage(text);
        };

        recognition.onerror = () => {
            isListening = false;
            setOrbState('idle');
        };

        recognition.onend = () => {
            isListening = false;
            if (orb.classList.contains('listening')) setOrbState('idle');
        };
    }

    function toggleListening() {
        if (isSpeaking && currentAudio) {
            currentAudio.pause();
            currentAudio = null;
            setOrbState('idle');
            return;
        }

        if (!recognition) {
            orbLabel.textContent = 'Voice not supported — type instead';
            setTimeout(() => orbLabel.textContent = 'Tap to speak', 3000);
            return;
        }

        if (isListening) {
            recognition.stop();
            isListening = false;
            setOrbState('idle');
        } else {
            try {
                recognition.start();
                isListening = true;
                setOrbState('listening');
            } catch (e) {
                // Already started
            }
        }
    }

    // ═══════════════════════════════════════════════════
    //  ORB STATE
    // ═══════════════════════════════════════════════════
    function setOrbState(state) {
        orb.classList.remove('listening', 'processing', 'speaking');
        isSpeaking = false;

        switch (state) {
            case 'listening':
                orb.classList.add('listening');
                orbLabel.textContent = 'Listening...';
                break;
            case 'processing':
                orb.classList.add('processing');
                orbLabel.textContent = 'Processing...';
                break;
            case 'speaking':
                orb.classList.add('speaking');
                orbLabel.textContent = 'Speaking...';
                isSpeaking = true;
                break;
            default:
                orbLabel.textContent = 'Tap to speak';
        }
    }

    // ═══════════════════════════════════════════════════
    //  NOTIFICATIONS
    // ═══════════════════════════════════════════════════
    function showNotification(title, body) {
        toastTitle.textContent = title;
        toastBody.textContent = body;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 6000);

        // Also add to chat
        addMessage('jarvis', `🔔 ${title}: ${body}`);
    }

    // ═══════════════════════════════════════════════════
    //  EVENT LISTENERS
    // ═══════════════════════════════════════════════════
    orb.addEventListener('click', toggleListening);

    sendBtn.addEventListener('click', () => {
        sendMessage(textInput.value);
        textInput.value = '';
    });

    textInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            sendMessage(textInput.value);
            textInput.value = '';
        }
    });

    document.querySelectorAll('.action-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const skill = btn.dataset.skill;
            if (skill) sendAction(skill);
        });
    });

    // ── Init ──────────────────────────────────────────
    initSpeechRecognition();

    // ── PWA Install ───────────────────────────────────
    let deferredPrompt;
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
    });

    // Register service worker
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(() => {});
    }

})();
