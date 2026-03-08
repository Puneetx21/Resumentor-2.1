document.addEventListener('DOMContentLoaded', function() {
    const scoreRing = document.querySelector('.score-ring');
    if (scoreRing) {
        const p = scoreRing.dataset.score || 0;
        scoreRing.style.setProperty('--p', 0);
        setTimeout(() => {
            scoreRing.style.setProperty('--p', p);
        }, 100);
    }
});
