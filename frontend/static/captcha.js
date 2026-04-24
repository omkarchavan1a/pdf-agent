document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('captcha-form');
    const errorEl = document.getElementById('error');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorEl.textContent = '';

        const captchaTokenInput = document.querySelector('[name="cf-turnstile-response"]');
        const captchaToken = captchaTokenInput ? captchaTokenInput.value : '';
        const captchaWidget = document.querySelector('.cf-turnstile');
        const captchaConfigured = !!(captchaWidget && (captchaWidget.dataset.sitekey || '').trim());

        if (captchaConfigured && !captchaToken) {
            errorEl.textContent = 'Please complete CAPTCHA verification.';
            return;
        }

        let sessionId = localStorage.getItem('idp_session_id');
        if (!sessionId) {
            sessionId = (window.crypto && crypto.randomUUID)
                ? crypto.randomUUID()
                : `session_${Date.now()}_${Math.random().toString(16).slice(2)}`;
        }

        try {
            const res = await fetch('/captcha/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ captcha_token: captchaToken, session_id: sessionId }),
            });
            const data = await res.json();

            if (!res.ok) {
                errorEl.textContent = data.detail || 'CAPTCHA verification failed.';
                return;
            }

            localStorage.setItem('idp_session_id', data.session_id || sessionId);
            window.location.href = '/user-details';
        } catch {
            errorEl.textContent = 'Could not reach backend. Please try again.';
        }
    });
});
