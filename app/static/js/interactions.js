(() => {
    const DEBOUNCE_MS = 600;

    const showInteractionTip = (message, isWarning = false) => {
        if (!message) {
            return;
        }
        let tip = document.getElementById("interaction-tip");
        if (!tip) {
            tip = document.createElement("div");
            tip.id = "interaction-tip";
            tip.className = "interaction-tip";
            document.body.appendChild(tip);
        }
        tip.textContent = message;
        tip.classList.toggle("warning", isWarning);
        tip.classList.add("show");
        window.setTimeout(() => tip.classList.remove("show"), 1800);
    };

    const updateReactionCounters = (resourceId, likes, favorites) => {
        const boxes = document.querySelectorAll(".resource-reactions");
        boxes.forEach((box) => {
            if (box.dataset.resourceId !== String(resourceId)) {
                return;
            }
            const likeCounter = box.querySelector('[data-role="like-count"]');
            const favoriteCounter = box.querySelector('[data-role="favorite-count"]');
            if (likeCounter) {
                likeCounter.textContent = String(likes);
            }
            if (favoriteCounter) {
                favoriteCounter.textContent = String(favorites);
            }
        });
        const summaryBlocks = document.querySelectorAll(`[data-resource-summary="${resourceId}"]`);
        summaryBlocks.forEach((summary) => {
            const likeSummary = summary.querySelector('[data-role="summary-like"]');
            const favoriteSummary = summary.querySelector('[data-role="summary-favorite"]');
            if (likeSummary) {
                likeSummary.textContent = String(likes);
            }
            if (favoriteSummary) {
                favoriteSummary.textContent = String(favorites);
            }
        });
    };

    const bindInteractionButtons = () => {
        document.addEventListener("click", async (event) => {
            const button = event.target.closest(".interaction-btn");
            if (!button) {
                return;
            }
            const resourceId = button.dataset.resourceId;
            const action = button.dataset.action;
            if (!resourceId || !action) {
                return;
            }
            if (button.dataset.busy === "1") {
                return;
            }
            button.dataset.busy = "1";
            button.disabled = true;
            try {
                const response = await fetch(`/api/resources/${resourceId}/${action}`, {
                    method: "POST",
                    headers: { "X-Requested-With": "XMLHttpRequest" },
                });
                if (!response.ok) {
                    throw new Error("interaction request failed");
                }
                const data = await response.json();
                updateReactionCounters(data.resource_id, data.likes, data.favorites);
                showInteractionTip(data.message || "操作成功", !data.accepted);
                if (data.accepted) {
                    button.classList.remove("interaction-pulse");
                    void button.offsetWidth;
                    button.classList.add("interaction-pulse");
                }
            } catch (error) {
                console.error(error);
                showInteractionTip("操作失败，请稍后重试", true);
            } finally {
                button.disabled = false;
                window.setTimeout(() => { button.dataset.busy = "0"; }, DEBOUNCE_MS);
            }
        });
    };

    const applyAdaptiveCoverRatio = (imgElement) => {
        const wrapper = imgElement.closest(".post-media");
        if (!wrapper || !imgElement.naturalHeight) {
            return;
        }
        const ratio = imgElement.naturalWidth / imgElement.naturalHeight;
        wrapper.classList.remove("ratio-auto", "ratio-landscape", "ratio-square", "ratio-portrait");
        if (ratio >= 1.3) {
            wrapper.classList.add("ratio-landscape");
            return;
        }
        if (ratio <= 0.8) {
            wrapper.classList.add("ratio-portrait");
            return;
        }
        wrapper.classList.add("ratio-square");
    };

    const bindAdaptiveCovers = () => {
        const covers = document.querySelectorAll(".adaptive-cover");
        covers.forEach((cover) => {
            if (cover.complete) {
                applyAdaptiveCoverRatio(cover);
                return;
            }
            cover.addEventListener("load", () => applyAdaptiveCoverRatio(cover), { once: true });
        });
    };

    bindInteractionButtons();
    bindAdaptiveCovers();
})();
