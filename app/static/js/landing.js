(() => {
    // Scroll reveal with IntersectionObserver
    const revealObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    revealObserver.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.15 }
    );

    document.querySelectorAll('.reveal').forEach((el) => {
        revealObserver.observe(el);
    });

    // Navigation scroll effect (throttled)
    const nav = document.getElementById('landingNav');
    let ticking = false;

    function onScroll() {
        if (!ticking) {
            window.requestAnimationFrame(() => {
                if (nav) {
                    nav.classList.toggle('scrolled', window.scrollY > 80);
                }
                ticking = false;
            });
            ticking = true;
        }
    }

    window.addEventListener('scroll', onScroll, { passive: true });

    // Count-up animation
    function animateCount(element, target, duration) {
        const start = 0;
        const startTime = performance.now();

        function easeOut(t) {
            return 1 - Math.pow(1 - t, 3);
        }

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const easedProgress = easeOut(progress);
            const current = Math.round(start + (target - start) * easedProgress);
            element.textContent = current.toLocaleString();

            if (progress < 1) {
                requestAnimationFrame(update);
            } else {
                element.classList.add('counted');
            }
        }

        requestAnimationFrame(update);
    }

    const statsObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    const numbers = entry.target.querySelectorAll('.stat-number[data-target]');
                    numbers.forEach((num) => {
                        const target = parseInt(num.dataset.target, 10) || 0;
                        animateCount(num, target, 2000);
                    });
                    statsObserver.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.3 }
    );

    const statsSection = document.getElementById('stats');
    if (statsSection) {
        statsObserver.observe(statsSection);
    }
})();
