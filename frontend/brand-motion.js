(function () {
    "use strict";

    var logo = document.querySelector(".brand-logo");

    if (!logo) {
        return;
    }

    var brand = logo.closest(".brand") || logo;

    brand.addEventListener("click", function () {
        if (
            window.matchMedia &&
            window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ) {
            return;
        }

        logo.classList.remove("is-tracing");
        void logo.getBoundingClientRect();
        logo.classList.add("is-tracing");
    });

    logo.addEventListener("animationend", function (event) {
        if (event.animationName === "brand-logo-trace") {
            logo.classList.remove("is-tracing");
        }
    });
})();
