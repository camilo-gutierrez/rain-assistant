// ---------------------------------------------------------------------------
// Notifications (Service Worker + push)
// ---------------------------------------------------------------------------

import { state, ORIGINAL_TITLE } from './app.js';

// Visibility / focus tracking
document.addEventListener('visibilitychange', () => {
    state.tabFocused = !document.hidden;
    if (state.tabFocused) {
        state.unreadCount = 0;
        document.title = ORIGINAL_TITLE;
    }
});

window.addEventListener('focus', () => {
    state.tabFocused = true;
    state.unreadCount = 0;
    document.title = ORIGINAL_TITLE;
});

window.addEventListener('blur', () => {
    state.tabFocused = false;
});

// Rain icon for notifications
let _rainIconDataUrl = null;

function generateRainIcon() {
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    ctx.beginPath();
    ctx.arc(32, 32, 30, 0, Math.PI * 2);
    ctx.fillStyle = '#0a0a14';
    ctx.fill();
    ctx.strokeStyle = '#00d4ff';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = '#00d4ff';
    ctx.font = 'bold 32px Orbitron, monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('R', 32, 34);
    return canvas.toDataURL();
}

function getRainIcon() {
    if (!_rainIconDataUrl) _rainIconDataUrl = generateRainIcon();
    return _rainIconDataUrl;
}

export function sendNotification(title, body) {
    if (!state.notificationsEnabled || state.tabFocused) return;

    state.unreadCount++;
    document.title = '(' + state.unreadCount + ') ' + ORIGINAL_TITLE;

    const options = {
        body: (body || '').slice(0, 150),
        icon: getRainIcon(),
        tag: 'rain-response',
        renotify: true,
    };

    if (state.swRegistration) {
        state.swRegistration.showNotification(title, options).catch(e => {
            console.warn('SW notification failed:', e);
        });
        return;
    }

    try {
        const notification = new Notification(title, options);
        notification.onclick = () => {
            window.focus();
            notification.close();
        };
        setTimeout(() => notification.close(), 5000);
    } catch (e) {
        console.warn('Notification failed:', e);
    }
}

async function requestPermission() {
    if (!('Notification' in window)) return;

    if ('serviceWorker' in navigator) {
        try {
            state.swRegistration = await navigator.serviceWorker.register('/sw.js');
        } catch (e) {
            console.warn('SW registration failed:', e);
        }
    }

    if (Notification.permission === 'granted') {
        state.notificationsEnabled = true;
        return;
    }
    if (Notification.permission !== 'denied') {
        const perm = await Notification.requestPermission();
        state.notificationsEnabled = (perm === 'granted');
    }
}

export function initNotifications() {
    ['click', 'keydown', 'touchstart'].forEach(evt => {
        document.addEventListener(evt, function onFirst() {
            requestPermission();
            document.removeEventListener(evt, onFirst);
        }, { once: true });
    });
}
