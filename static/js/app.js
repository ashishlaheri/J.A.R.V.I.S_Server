/* ═══════════════════════════════════════════════════════════
   J.A.R.V.I.S. v3.1 — Frontend Application
   Voice + Text + WebSocket + Particles + Sound FX + PWA
   ═══════════════════════════════════════════════════════════ */

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
    const responseTime   = $('#response-time');
    const reconnectOverlay = $('#reconnect-overlay');
    const particleCanvas = $('#particle-canvas');

    // ── State ─────────────────────────────────────────
    let ws = null;
    let token = localStorage.getItem('jarvis_token');
    let isListening = false;
    let isProcessing = false;
    let isSpeaking = false;
    let currentAudio = null;
    let recognition = null;
    let requestStartTime = 0;
    let reconnectAttempts = 0;
    let audioCtx = null;

    // ═══════════════════════════════════════════════════
    //  PARTICLE SYSTEM
    // ═══════════════════════════════════════════════════
    const particles = [];
    const PARTICLE_COUNT = 35;
    let ctx = null;
    let animFrame = null;

    function initParticles() {
        if (!particleCanvas) return;
        ctx = particleCanvas.getContext('2d');
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);

        for (let i = 0; i < PARTICLE_COUNT; i++) {
            particles.push({
                x: Math.random() * particleCanvas.width,
                y: Math.random() * particleCanvas.height,
                vx: (Math.random() - 0.5) * 0.3,
                vy: (Math.random() - 0.5) * 0.3,
                size: Math.random() * 2 + 0.5,
                alpha: Math.random() * 0.4 + 0.1,
                pulse: Math.random() * Math.PI * 2
            });
        }
        animateParticles();
    }

    function resizeCanvas() {
        if (!particleCanvas) return;
        particleCanvas.width = window.innerWidth;
        particleCanvas.height = window.innerHeight;
    }

    function animateParticles() {
        if (!ctx) return;
        ctx.clearRect(0, 0, particleCanvas.width, particleCanvas.height);

        for (const p of particles) {
            p.x += p.vx;
            p.y += p.vy;
            p.pulse += 0.02;

            // Wrap around
            if (p.x < 0) p.x = particleCanvas.width;
            if (p.x > particleCanvas.width) p.x = 0;
            if (p.y < 0) p.y = particleCanvas.height;
            if (p.y > particleCanvas.height) p.y = 0;

            const alpha = p.alpha * (0.6 + Math.sin(p.pulse) * 0.4);
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(0, 212, 255, ${alpha})`;
            ctx.fill();

            // Small glow
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(0, 212, 255, ${alpha * 0.1})`;
            ctx.fill();
        }

        // Draw connection lines between close particles
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 120) {
                    const alpha = (1 - dist / 120) * 0.06;
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(0, 212, 255, ${alpha})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        }

        animFrame = requestAnimationFrame(animateParticles);
    }

    // ═══════════════════════════════════════════════════
    //  SOUND EFFECTS (Web Audio API — no files needed)
    // ═══════════════════════════════════════════════════
    function getAudioCtx() {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        return audioCtx;
    }

    function playBeep(freq = 800, duration = 0.1, type = 'sine', volume = 0.15) {
        try {
            const ctx = getAudioCtx();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = type;
            osc.frequency.setValueAtTime(freq, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(freq * 1.5, ctx.currentTime + duration);
            gain.gain.setValueAtTime(volume, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + duration);
        } catch (e) { /* Audio not supported */ }
    }

    // ── Sci-Fi Sound Effects ──
    function sfxActivate() {
        playBeep(500, 0.08, 'sine', 0.15);
        setTimeout(() => playBeep(800, 0.08, 'sine', 0.15), 80);
        setTimeout(() => playBeep(1100, 0.06, 'sine', 0.1), 160);
    }
    function sfxDeactivate() {
        playBeep(1100, 0.06, 'sine', 0.1);
        setTimeout(() => playBeep(700, 0.08, 'sine', 0.12), 80);
    }
    function sfxMessage() {
        playBeep(900, 0.05, 'sine', 0.1);
        setTimeout(() => playBeep(1400, 0.04, 'sine', 0.08), 60);
    }
    function sfxSend() {
        playBeep(400, 0.06, 'triangle', 0.1);
        setTimeout(() => playBeep(600, 0.04, 'triangle', 0.08), 50);
    }
    function sfxError() {
        playBeep(150, 0.2, 'sawtooth', 0.12);
        setTimeout(() => playBeep(100, 0.15, 'sawtooth', 0.08), 150);
    }
    function sfxConnect() {
        playBeep(400, 0.08, 'sine', 0.1);
        setTimeout(() => playBeep(600, 0.08, 'sine', 0.12), 100);
        setTimeout(() => playBeep(900, 0.1, 'sine', 0.15), 200);
    }
    function sfxButtonTap() { playBeep(700, 0.04, 'sine', 0.08); }

    // ── Clock ─────────────────────────────────────────
    function updateClock() {
        const now = new Date();
        clock.textContent = now.toLocaleTimeString('en-US', {
            hour: '2-digit', minute: '2-digit', hour12: true
        });
    }
    setInterval(updateClock, 1000);
    updateClock();

    // ═══════════════════════════════════════════════════
    //  AUTH
    // ═══════════════════════════════════════════════════
    async function login(password) {
        try {
            loginBtn.disabled = true;
            loginBtn.querySelector('.btn-text').textContent = 'CONNECTING...';

            const base = location.origin;
            const res = await fetch(`${base}/api/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });

            if (!res.ok) {
                loginError.textContent = 'Access denied.';
                sfxError();
                loginBtn.disabled = false;
                loginBtn.querySelector('.btn-text').textContent = 'INITIALIZE';
                return;
            }

            const data = await res.json();
            token = data.token;
            localStorage.setItem('jarvis_token', token);
            sfxActivate();
            showMain();
        } catch (e) {
            loginError.textContent = 'Connection failed. Is the server running?';
            sfxError();
            loginBtn.disabled = false;
            loginBtn.querySelector('.btn-text').textContent = 'INITIALIZE';
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
        const url = `${protocol}://${location.host}/ws`;

        try {
            ws = new WebSocket(url);
        } catch (e) {
            showReconnecting(true);
            scheduleReconnect();
            return;
        }

        ws.onopen = () => {
            connStatus.classList.add('connected');
            showReconnecting(false);
            reconnectAttempts = 0;
            sfxConnect();
            // First message: auth token
            ws.send(JSON.stringify({ token }));
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                switch (data.type) {
                    case 'response':
                        removeProcessing();
                        showResponseTime();
                        addMessage('jarvis', data.text, true);
                        sfxMessage();
                        if (data.audio) playAudio(data.audio);
                        else setOrbState('idle');
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

                    case 'agent_data':
                        // Data from local agent (screenshots, status)
                        removeProcessing();
                        setOrbState('idle');
                        if (data.subtype === 'screenshot' && data.image) {
                            showScreenshot(data.image);
                            addMessage('jarvis', '📸 Live screenshot received from your PC, Sir.', true);
                        } else if (data.text) {
                            addMessage('jarvis', data.text, true);
                        }
                        // Re-enable all sec buttons
                        document.querySelectorAll('.sec-btn.loading').forEach(b => b.classList.remove('loading'));
                        break;

                    case 'error':
                        removeProcessing();
                        addMessage('jarvis', data.message || 'Something went wrong, Sir.');
                        sfxError();
                        // If auth error, clear token and show login
                        if (data.message && data.message.includes('Authentication')) {
                            localStorage.removeItem('jarvis_token');
                            token = null;
                            mainScreen.classList.remove('active');
                            loginScreen.classList.add('active');
                        }
                        break;
                }
            } catch (e) {
                console.error('Message parse error:', e);
            }
        };

        ws.onclose = (event) => {
            connStatus.classList.remove('connected');
            if (event.code !== 1000) {
                showReconnecting(true);
                scheduleReconnect();
            }
        };

        ws.onerror = () => {
            connStatus.classList.remove('connected');
        };
    }

    function scheduleReconnect() {
        reconnectAttempts++;
        const delay = Math.min(2000 * Math.pow(1.5, reconnectAttempts - 1), 30000);
        setTimeout(() => {
            if (!ws || ws.readyState === WebSocket.CLOSED) {
                connectWebSocket();
            }
        }, delay);
    }

    function showReconnecting(show) {
        if (reconnectOverlay) {
            reconnectOverlay.classList.toggle('hidden', !show);
        }
    }

    function sendMessage(text) {
        if (!text.trim() || !ws || ws.readyState !== WebSocket.OPEN) return;
        addMessage('user', text);
        ws.send(JSON.stringify({ type: 'chat', text }));
        requestStartTime = Date.now();
        setOrbState('processing');
        sfxSend();
    }

    function sendAction(skill) {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        ws.send(JSON.stringify({ type: 'action', skill, text: skill }));
        requestStartTime = Date.now();
        showProcessing();
        setOrbState('processing');
        sfxSend();
    }

    function handleAction(action) {
        if (action.type === 'open_url' && action.url) {
            window.open(action.url, '_blank');
        }
    }

    // ═══════════════════════════════════════════════════
    //  RESPONSE TIME
    // ═══════════════════════════════════════════════════
    function showResponseTime() {
        if (!requestStartTime || !responseTime) return;
        const elapsed = ((Date.now() - requestStartTime) / 1000).toFixed(1);
        responseTime.textContent = `${elapsed}s`;
        responseTime.classList.add('visible');
        setTimeout(() => responseTime.classList.remove('visible'), 4000);
        requestStartTime = 0;
    }

    // ═══════════════════════════════════════════════════
    //  CHAT UI
    // ═══════════════════════════════════════════════════
    function addMessage(sender, text, typewriter = false) {
        const div = document.createElement('div');
        div.className = `chat-msg ${sender}`;
        const label = sender === 'user' ? 'YOU' : 'JARVIS';
        const escaped = escapeHtml(text);

        if (typewriter && sender === 'jarvis') {
            div.innerHTML = `<div class="msg-label">${label}</div><div class="msg-text"></div>`;
            chatArea.appendChild(div);
            chatArea.scrollTop = chatArea.scrollHeight;
            typewriterEffect(div.querySelector('.msg-text'), escaped);
        } else {
            div.innerHTML = `<div class="msg-label">${label}</div><div class="msg-text" style="opacity:1">${escaped}</div>`;
            chatArea.appendChild(div);
            chatArea.scrollTop = chatArea.scrollHeight;
        }
    }

    function typewriterEffect(element, text, speed = 12) {
        let i = 0;
        element.style.opacity = '1';
        element.textContent = '';

        function type() {
            if (i < text.length) {
                // Handle HTML entities
                if (text[i] === '&') {
                    const end = text.indexOf(';', i);
                    if (end !== -1) {
                        element.innerHTML += text.substring(i, end + 1);
                        i = end + 1;
                    } else {
                        element.textContent += text[i];
                        i++;
                    }
                } else {
                    element.textContent += text[i];
                    i++;
                }
                chatArea.scrollTop = chatArea.scrollHeight;
                setTimeout(type, speed);
            }
        }
        type();
    }

    function showProcessing() {
        const div = document.createElement('div');
        div.className = 'chat-msg jarvis processing-msg';
        div.innerHTML = `<div class="msg-label">JARVIS</div><div class="processing-dots"><span></span><span></span><span></span></div>`;
        chatArea.appendChild(div);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function removeProcessing() {
        chatArea.querySelectorAll('.processing-msg').forEach(el => el.remove());
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ═══════════════════════════════════════════════════
    //  AUDIO PLAYBACK
    // ═══════════════════════════════════════════════════
    let currentAudioSource = null;

    function playAudio(base64) {
        try {
            if (currentAudio) { currentAudio.pause(); currentAudio = null; }
            if (currentAudioSource) { currentAudioSource.stop(); currentAudioSource = null; }
            
            const ctx = getAudioCtx();
            // Resume context if suspended (iOS requirement)
            if (ctx.state === 'suspended') ctx.resume();

            const bytes = atob(base64);
            const buffer = new Uint8Array(bytes.length);
            for (let i = 0; i < bytes.length; i++) buffer[i] = bytes.charCodeAt(i);
            
            setOrbState('speaking');
            
            ctx.decodeAudioData(buffer.buffer, (decodedData) => {
                const source = ctx.createBufferSource();
                source.buffer = decodedData;
                source.connect(ctx.destination);
                currentAudioSource = source;
                
                source.onended = () => {
                    setOrbState('idle');
                    currentAudioSource = null;
                };
                
                source.start(0);
            }, (err) => {
                console.error("Audio decode error", err);
                setOrbState('idle');
            });

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

        recognition.onerror = (event) => {
            isListening = false;
            setOrbState('idle');
            if (event.error === 'not-allowed') {
                orbLabel.textContent = 'Mic access denied';
                setTimeout(() => orbLabel.textContent = 'Tap to speak', 3000);
            }
        };

        recognition.onend = () => {
            isListening = false;
            if (orb.classList.contains('listening')) setOrbState('idle');
        };
    }

    function toggleListening() {
        // Tap while speaking → stop audio
        if (isSpeaking && (currentAudio || currentAudioSource)) {
            if (currentAudio) { currentAudio.pause(); currentAudio = null; }
            if (currentAudioSource) {
                try { currentAudioSource.stop(); } catch(e){}
                currentAudioSource = null;
            }
            setOrbState('idle');
            sfxDeactivate();
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
            sfxDeactivate();
        } else {
            try {
                // Resume audio context on user gesture (iOS requirement)
                if (audioCtx && audioCtx.state === 'suspended') {
                    audioCtx.resume();
                }
                recognition.start();
                isListening = true;
                setOrbState('listening');
                sfxActivate();
                // Haptic feedback on supported devices
                if (navigator.vibrate) navigator.vibrate(30);
            } catch (e) {
                // Already started, ignore
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
        sfxMessage();
        if (navigator.vibrate) navigator.vibrate([50, 50, 50]);
        setTimeout(() => toast.classList.add('hidden'), 6000);
        addMessage('jarvis', `🔔 ${title}: ${body}`);
    }

    // ═══════════════════════════════════════════════════
    //  EVENT LISTENERS
    // ═══════════════════════════════════════════════════
    orb.addEventListener('click', toggleListening);

    sendBtn.addEventListener('click', () => {
        const text = textInput.value.trim();
        if (text) {
            sendMessage(text);
            textInput.value = '';
        }
    });

    textInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const text = textInput.value.trim();
            if (text) {
                sendMessage(text);
                textInput.value = '';
            }
        }
    });

    // Quick action buttons
    document.querySelectorAll('.action-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const skill = btn.dataset.skill;
            if (skill) {
                sfxButtonTap();
                sendAction(skill);
                if (navigator.vibrate) navigator.vibrate(20);
            }
        });
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Space to toggle voice (when not typing)
        if (e.code === 'Space' && document.activeElement !== textInput && document.activeElement !== passwordInput) {
            e.preventDefault();
            toggleListening();
        }
        // Escape to stop speech
        if (e.key === 'Escape') {
            if (currentAudio) {
                currentAudio.pause();
                currentAudio = null;
                setOrbState('idle');
            }
            if (isListening && recognition) {
                recognition.stop();
                isListening = false;
                setOrbState('idle');
            }
        }
        // Ctrl+/ or Cmd+/ to focus text input
        if ((e.ctrlKey || e.metaKey) && e.key === '/') {
            e.preventDefault();
            textInput.focus();
        }
    });

    // ── Init ──────────────────────────────────────────
    initSpeechRecognition();
    initParticles();
    initSecurityPanel();

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

    // Resume audio context on first user interaction (iOS Safari requirement)
    document.addEventListener('touchstart', () => {
        if (audioCtx && audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
    }, { once: true });

    // ═══════════════════════════════════════════════════
    //  SECURITY PANEL
    // ═══════════════════════════════════════════════════
    function initSecurityPanel() {
        const secToggleBtn = $('#btn-security-toggle');
        const secPanel     = $('#security-panel');
        const secBackdrop  = $('#security-backdrop');
        const ssViewer     = $('#screenshot-viewer');
        const ssImg        = $('#screenshot-img');
        const ssTime       = $('#screenshot-time');
        const closeSSBtn   = $('#close-screenshot');

        if (!secToggleBtn || !secPanel || !secBackdrop) return;

        function openSecurityPanel() {
            secPanel.classList.remove('hidden');
            secBackdrop.classList.remove('hidden');
            secToggleBtn.classList.add('active');
            if (navigator.vibrate) navigator.vibrate(15);
            sfxButtonTap();
        }

        function closeSecurityPanel() {
            secPanel.classList.add('hidden');
            secBackdrop.classList.add('hidden');
            secToggleBtn.classList.remove('active');
            if (navigator.vibrate) navigator.vibrate(10);
        }

        // Toggle panel open/close
        secToggleBtn.addEventListener('click', () => {
            if (secPanel.classList.contains('hidden')) {
                openSecurityPanel();
            } else {
                closeSecurityPanel();
            }
        });

        // Close when clicking backdrop
        secBackdrop.addEventListener('click', closeSecurityPanel);

        // Close on swipe down or handle click
        const handle = document.querySelector('.security-sheet-handle');
        if (handle) {
            handle.addEventListener('click', closeSecurityPanel);
            let startY = 0;
            secPanel.addEventListener('touchstart', (e) => startY = e.touches[0].clientY, {passive: true});
            secPanel.addEventListener('touchend', (e) => {
                const endY = e.changedTouches[0].clientY;
                if (endY - startY > 60 && e.target.closest('.security-panel')) closeSecurityPanel();
            }, {passive: true});
        }

        // Security command labels (shown in chat)
        const cmdLabels = {
            'screenshot_upload': '📸 Requesting live screenshot from your PC...',
            'lock_now':          '🔒 Locking your PC now, Sir.',
            'alarm':             '🚨 Sounding alarm on your PC, Sir!',
            'warning':           '⚠️ Showing warning popup on your PC, Sir.',
            'freeze':            '❄️ Freezing keyboard and mouse for 10 seconds, Sir.',
            'logoff':            '🚪 Logging off current user on your PC, Sir.',
            'disable_wifi':      '📶 Cutting Wi-Fi connection on your PC, Sir.',
            'running_apps':      '💻 Fetching running apps from your PC...',
        };

        // Wire up all security buttons
        document.querySelectorAll('.sec-btn[data-sec-cmd]').forEach(btn => {
            btn.addEventListener('click', () => {
                const cmd = btn.dataset.secCmd;
                if (!cmd) return;
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    addMessage('jarvis', '⚠️ Not connected to server, Sir. Please reconnect.');
                    return;
                }

                // Show feedback in chat
                const label = cmdLabels[cmd] || `Executing ${cmd} on your PC...`;
                addMessage('user', label.replace(/^[^\s]+ /, ''));
                addMessage('jarvis', label, true);

                // Set loading state
                btn.classList.add('loading');
                setTimeout(() => btn.classList.remove('loading'), 8000); // auto-remove after 8s

                // Send command to cloud server → forwarded to local agent
                ws.send(JSON.stringify({
                    type: 'action',
                    skill: 'security',
                    text: cmd,
                    command: cmd,
                    action: {
                        type: 'local_command',
                        command: cmd,
                        target: ''
                    }
                }));

                if (navigator.vibrate) navigator.vibrate([20, 10, 20]);
                sfxSend();
            });
        });

        // Close screenshot viewer
        if (closeSSBtn) {
            closeSSBtn.addEventListener('click', () => {
                if (ssViewer) ssViewer.classList.add('hidden');
            });
        }
    }

    function showScreenshot(base64Image) {
        const ssViewer = $('#screenshot-viewer');
        const ssImg    = $('#screenshot-img');
        const ssTime   = $('#screenshot-time');
        const secPanel = $('#security-panel');
        const secBackdrop = $('#security-backdrop');

        if (!ssViewer || !ssImg) return;

        // Make sure the security panel is visible
        if (secPanel && secPanel.classList.contains('hidden')) {
            secPanel.classList.remove('hidden');
            if (secBackdrop) secBackdrop.classList.remove('hidden');
            const toggleBtn = $('#btn-security-toggle');
            if (toggleBtn) toggleBtn.classList.add('active');
        }

        ssImg.src = `data:image/jpeg;base64,${base64Image}`;
        if (ssTime) ssTime.textContent = `Captured at ${new Date().toLocaleTimeString()}`;
        ssViewer.classList.remove('hidden');

        // Scroll to show it
        ssViewer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

})();
