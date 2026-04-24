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

        // Email validation - must be valid Gmail format
        const emailRegex = /^[a-zA-Z0-9._%+-]+@gmail\.com$/;
        if (!email || !emailRegex.test(email)) {
            errorEl.textContent = 'Please enter a valid Gmail address (e.g., username@gmail.com).';
            return;
        }

        // Phone validation - must be valid international format
        const phoneRegex = /^\+?[1-9]\d{1,14}$/;
        const cleanedPhone = phone.replace(/[\s\-\(\)]/g, '');
        if (!cleanedPhone || !phoneRegex.test(cleanedPhone)) {
            errorEl.textContent = 'Please enter a valid phone number with country code (e.g., +91 9876543210).';
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
