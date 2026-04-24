document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('details-form');
    const errorEl = document.getElementById('error');
    const sessionId = localStorage.getItem('idp_session_id');

    if (!sessionId) {
        window.location.href = '/captcha';
        return;
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorEl.textContent = '';

        const email = document.getElementById('email').value.trim().toLowerCase();
        const phone = document.getElementById('phone').value.trim();

        if (!email.endsWith('@gmail.com')) {
            errorEl.textContent = 'Please use a valid Gmail address.';
            return;
        }
        if (!phone) {
            errorEl.textContent = 'Phone number is required.';
            return;
        }

        try {
            const res = await fetch('/user-details', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, phone, session_id: sessionId }),
            });
            const data = await res.json();

            if (!res.ok) {
                errorEl.textContent = data.detail || 'Failed to save details.';
                return;
            }

            localStorage.setItem('idp_session_id', data.session_id || sessionId);
            window.location.href = '/app';
        } catch {
            errorEl.textContent = 'Could not reach backend. Please try again.';
        }
    });
});
