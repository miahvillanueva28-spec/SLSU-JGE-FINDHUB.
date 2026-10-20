
document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    const root = document.documentElement;

    /* ======================================
       DARK MODE / LIGHT MODE
       ====================================== */

    const themeButton = document.querySelector("#theme-toggle");

    function readThemePreference() {
        try {
            return localStorage.getItem("findhub-theme");
        } catch (error) {
            return null;
        }
    }

    function saveThemePreference(theme) {
        try {
            localStorage.setItem("findhub-theme", theme);
        } catch (error) {
            // Patuloy na gagana ang theme kahit disabled ang storage.
        }
    }

    const savedTheme = readThemePreference();
    const prefersDark = window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches;

    applyTheme(savedTheme || (prefersDark ? "dark" : "light"));

    if (themeButton) {
        themeButton.addEventListener("click", function () {
            const nextTheme =
                root.dataset.theme === "dark" ? "light" : "dark";

            applyTheme(nextTheme);
            saveThemePreference(nextTheme);
        });
    }

    function applyTheme(theme) {
        const isDark = theme === "dark";

        root.dataset.theme = isDark ? "dark" : "light";

        if (themeButton) {
            themeButton.setAttribute(
                "aria-label",
                isDark ? "Switch to light mode" : "Switch to dark mode"
            );

            const icon = themeButton.querySelector(".theme-icon");
            const label = themeButton.querySelector(".theme-label");

            if (icon) {
                icon.textContent = isDark ? "☀" : "☾";
            }

            if (label) {
                label.textContent = isDark ? "Light mode" : "Dark mode";
            }
        }

        const themeColor = document.querySelector(
            'meta[name="theme-color"]'
        );

        if (themeColor) {
            themeColor.setAttribute(
                "content",
                isDark ? "#101a14" : "#176b45"
            );
        }
    }

    /* ======================================
       MOBILE NAVIGATION
       ====================================== */

    const menuButton = document.querySelector(".menu-toggle");
    const navigation = document.querySelector("#primary-navigation");

    function closeNavigation() {
        if (!menuButton || !navigation) return;

        navigation.classList.remove("open");
        menuButton.setAttribute("aria-expanded", "false");
        menuButton.setAttribute("aria-label", "Open navigation");
    }

    if (menuButton && navigation) {
        menuButton.addEventListener("click", function () {
            const isOpen = navigation.classList.toggle("open");

            menuButton.setAttribute("aria-expanded", String(isOpen));
            menuButton.setAttribute(
                "aria-label",
                isOpen ? "Close navigation" : "Open navigation"
            );
        });

        navigation.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", closeNavigation);
        });

        document.addEventListener("click", function (event) {
            if (
                !navigation.contains(event.target) &&
                !menuButton.contains(event.target)
            ) {
                closeNavigation();
            }
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                closeNavigation();
            }
        });
    }

    /* ======================================
       TOAST NOTIFICATIONS
       ====================================== */

    function getToastContainer() {
        let container = document.querySelector(".toast-container");

        if (!container) {
            container = document.createElement("div");
            container.className = "toast-container";
            container.setAttribute("aria-live", "polite");
            container.setAttribute("aria-atomic", "true");
            document.body.appendChild(container);
        }

        return container;
    }

    function showToast(message, type = "success") {
        if (!message) return;

        const container = getToastContainer();
        const toast = document.createElement("div");

        toast.className = "toast";

        if (type === "error" || type === "warning") {
            toast.classList.add(type);
        }

        toast.setAttribute(
            "role",
            type === "error" ? "alert" : "status"
        );

        // textContent: ligtas sa pag-display ng text.
        toast.textContent = message;
        container.appendChild(toast);

        window.setTimeout(function () {
            toast.classList.add("removing");

            window.setTimeout(function () {
                toast.remove();
            }, 300);
        }, 3500);
    }

    document.querySelectorAll("[data-toast-message]").forEach(
        function (element) {
            const message = element.getAttribute("data-toast-message");
            const type =
                element.getAttribute("data-toast-type") || "success";

            if (message) {
                showToast(message, type);
            }
        }
    );

    /* ======================================
       DISMISS FLASH MESSAGES
       ====================================== */

    document.querySelectorAll(".flash-dismiss").forEach(
        function (button) {
            button.addEventListener("click", function () {
                const message = button.closest(".flash-message");

                if (message) {
                    message.remove();
                }
            });
        }
    );

    /* ======================================
       IMAGE PREVIEW MODAL
       ====================================== */

    let modal = document.querySelector(".image-modal");

    if (!modal) {
        modal = document.createElement("div");
        modal.className = "image-modal";
        modal.setAttribute("role", "dialog");
        modal.setAttribute("aria-modal", "true");
        modal.setAttribute("aria-label", "Image preview");
        modal.hidden = true;

        const closeButton = document.createElement("button");
        closeButton.className = "image-modal-close";
        closeButton.type = "button";
        closeButton.setAttribute(
            "aria-label",
            "Close image preview"
        );
        closeButton.textContent = "×";

        const preview = document.createElement("img");
        preview.alt = "Enlarged item photo";

        modal.append(closeButton, preview);
        document.body.appendChild(modal);
    }

    const modalClose = modal.querySelector(".image-modal-close");

    function closeImageModal() {
        if (!modal) return;

        modal.classList.remove("open");
        modal.hidden = true;

        const preview = modal.querySelector("img");

        if (preview) {
            preview.removeAttribute("src");
        }
    }

    if (modalClose) {
        modalClose.addEventListener("click", closeImageModal);
    }

    modal.addEventListener("click", function (event) {
        if (event.target === modal) {
            closeImageModal();
        }
    });

    document.querySelectorAll(
        "[data-image-preview], .report-photo"
    ).forEach(function (image) {
        function openImagePreview() {
            const source =
                image.dataset.imagePreview ||
                image.currentSrc ||
                image.src;

            const preview = modal.querySelector("img");

            if (source && preview) {
                preview.src = source;
                modal.hidden = false;
                modal.classList.add("open");

                if (modalClose) {
                    modalClose.focus();
                }
            }
        }

        image.addEventListener("click", openImagePreview);

        if (
            image.tagName.toLowerCase() === "img" &&
            !image.hasAttribute("tabindex")
        ) {
            image.setAttribute("tabindex", "0");
            image.setAttribute("role", "button");

            image.addEventListener("keydown", function (event) {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openImagePreview();
                }
            });
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeImageModal();
        }
    });

    /* ======================================
       IMAGE FILE VALIDATION AND PREVIEW
       ====================================== */

    document.querySelectorAll(
        'input[type="file"][data-image-input]'
    ).forEach(function (input) {
        input.addEventListener("change", function () {
            const file = input.files && input.files[0];
            const targetSelector = input.dataset.previewTarget;
            const target = targetSelector
                ? document.querySelector(targetSelector)
                : null;

            if (!file) {
                if (target) {
                    target.removeAttribute("src");
                    target.hidden = true;
                }
                return;
            }

            if (!file.type || !file.type.startsWith("image/")) {
                showToast(
                    "Pumili ng valid na image file.",
                    "error"
                );

                input.value = "";

                if (target) {
                    target.removeAttribute("src");
                    target.hidden = true;
                }

                return;
            }

            if (file.size > 5 * 1024 * 1024) {
                showToast(
                    "Ang image ay dapat 5 MB o mas mababa.",
                    "error"
                );

                input.value = "";

                if (target) {
                    target.removeAttribute("src");
                    target.hidden = true;
                }

                return;
            }

            if (target) {
                if (target.dataset.objectUrl) {
                    URL.revokeObjectURL(target.dataset.objectUrl);
                }

                const objectUrl = URL.createObjectURL(file);

                target.dataset.objectUrl = objectUrl;
                target.src = objectUrl;
                target.hidden = false;
            }
        });
    });

    /* ======================================
       PREVENT DOUBLE FORM SUBMISSION
       ====================================== */

    document.querySelectorAll("form[data-loading-form]").forEach(
        function (form) {
            form.addEventListener("submit", function (event) {
                if (form.dataset.submitting === "true") {
                    event.preventDefault();
                    return;
                }

                if (!form.checkValidity()) {
                    return;
                }

                form.dataset.submitting = "true";

                const button = form.querySelector(
                    'button[type="submit"], input[type="submit"]'
                );

                if (button) {
                    button.disabled = true;

                    if (button.tagName === "BUTTON") {
                        button.dataset.originalText =
                            button.textContent;

                        button.textContent = "Please wait...";
                    } else {
                        button.dataset.originalText = button.value;
                        button.value = "Please wait...";
                    }
                }
            });
        }
    );
});
