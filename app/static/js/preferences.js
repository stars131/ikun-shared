(() => {
    const VIEW_KEY = "ikun_view_mode";
    const CAROUSEL_KEY = "ikun_carousel_autoplay";
    const validViews = new Set(["list", "post"]);

    const getStoredView = () => {
        const value = localStorage.getItem(VIEW_KEY);
        return validViews.has(value) ? value : "list";
    };

    const getStoredAutoplay = () => {
        const value = localStorage.getItem(CAROUSEL_KEY);
        return value === null ? "on" : value;
    };

    const initHomePage = () => {
        const params = new URLSearchParams(window.location.search);
        const currentView = params.get("view");
        const storedView = getStoredView();
        if (!currentView || !validViews.has(currentView)) {
            params.set("view", storedView);
            const nextUrl = `${window.location.pathname}?${params.toString()}`;
            window.location.replace(nextUrl);
            return;
        }
        if (storedView !== currentView) {
            localStorage.setItem(VIEW_KEY, currentView);
        }

        const viewSelect = document.querySelector("[data-view-select]");
        if (viewSelect) {
            viewSelect.value = currentView;
            viewSelect.addEventListener("change", () => {
                localStorage.setItem(VIEW_KEY, viewSelect.value);
            });
        }

        const carouselElement = document.getElementById("trendingCarousel");
        if (carouselElement) {
            const autoplay = getStoredAutoplay();
            const carousel = window.bootstrap ? window.bootstrap.Carousel.getOrCreateInstance(carouselElement) : null;
            if (autoplay === "off") {
                carouselElement.setAttribute("data-bs-interval", "false");
                if (carousel) {
                    carousel.pause();
                }
            } else if (carousel) {
                carousel.cycle();
            }
        }
    };

    const initSettingsPage = () => {
        const buttons = Array.from(document.querySelectorAll(".setting-view-btn"));
        const autoplaySwitch = document.getElementById("carouselAutoplaySwitch");
        const saveBtn = document.getElementById("saveDisplaySettings");
        if (!buttons.length || !autoplaySwitch || !saveBtn) {
            return;
        }

        const applyActiveView = (viewValue) => {
            buttons.forEach((button) => {
                button.classList.toggle("active", button.dataset.viewValue === viewValue);
            });
        };

        let selectedView = getStoredView();
        applyActiveView(selectedView);
        autoplaySwitch.checked = getStoredAutoplay() !== "off";

        buttons.forEach((button) => {
            button.addEventListener("click", () => {
                selectedView = button.dataset.viewValue || "list";
                applyActiveView(selectedView);
            });
        });

        saveBtn.addEventListener("click", () => {
            localStorage.setItem(VIEW_KEY, selectedView);
            localStorage.setItem(CAROUSEL_KEY, autoplaySwitch.checked ? "on" : "off");
            saveBtn.textContent = "已保存 \u2713";
            saveBtn.classList.remove("btn-warning");
            saveBtn.classList.add("btn-success");
            saveBtn.disabled = true;
            window.setTimeout(() => {
                window.location.href = `/?view=${selectedView}`;
            }, 800);
        });
    };

    if (window.location.pathname === "/") {
        initHomePage();
    }
    if (window.location.pathname === "/settings") {
        initSettingsPage();
    }
})();
