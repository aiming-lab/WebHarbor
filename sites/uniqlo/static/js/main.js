// UNIQLO mirror - client-side behaviors

document.addEventListener('DOMContentLoaded', () => {
    // Auto-dismiss flash messages
    document.querySelectorAll('.flash-msg').forEach(msg => {
        setTimeout(() => {
            msg.style.transition = 'opacity 0.4s';
            msg.style.opacity = '0';
            setTimeout(() => msg.remove(), 400);
        }, 4500);
    });
});
