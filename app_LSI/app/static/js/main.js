// ─── Method selector highlight ────────────────────────────────────────────────
document.querySelectorAll('.method-option input[type="radio"]').forEach(radio => {
  radio.addEventListener('change', () => {
    document.querySelectorAll('.method-option').forEach(el => el.classList.remove('selected'));
    if (radio.checked) radio.closest('.method-option').classList.add('selected');
  });
});

// ─── Animate bar fills on load ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.bar-fill, .sim-bar').forEach(bar => {
    const target = bar.style.width;
    bar.style.width = '0%';
    setTimeout(() => { bar.style.width = target; }, 100);
  });
});
