document.addEventListener("DOMContentLoaded", function () {
    const signupForm = document.getElementById("signup-form");
    const emailInput = document.getElementById("email");
    const passwordInput = document.getElementById("password");
    const confirmPasswordInput =
        document.getElementById("confirm-password");
    const signupButton = document.querySelector(".login-button");

    // =================================================
    // SHOW / HIDE PASSWORD
    // Matches the existing login page pattern.
    // Toggling only swaps the input type, so the
    // entered value is never read or modified.
    // =================================================

    function setupPasswordToggle(input, toggle, label) {
        if (!input || !toggle) {
            return;
        }

        const openEye =
            toggle.querySelector(".password-eye-open");

        const closedEye =
            toggle.querySelector(".password-eye-closed");

        toggle.addEventListener("click", function () {
            const isPassword = input.type === "password";

            input.type = isPassword ? "text" : "password";

            if (openEye) {
                openEye.classList.toggle("hidden", isPassword);
            }

            if (closedEye) {
                closedEye.classList.toggle("hidden", !isPassword);
            }

            toggle.setAttribute(
                "aria-label",
                isPassword
                    ? `Hide ${label}`
                    : `Show ${label}`
            );

            toggle.setAttribute("aria-pressed", String(isPassword));

            input.focus();
        });
    }

    setupPasswordToggle(
        passwordInput,
        document.getElementById("password-toggle"),
        "password"
    );

    setupPasswordToggle(
        confirmPasswordInput,
        document.getElementById("confirm-password-toggle"),
        "password confirmation"
    );

    // =================================================
    // PASSWORD POLICY
    // Matches reset-password.js: the minimum length is
    // checked before submit so the user gets a clear
    // message; Supabase Auth remains the authoritative
    // server-side validator.
    // =================================================

    const MIN_PASSWORD_LENGTH = 8;

    signupForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const email = emailInput.value.trim();
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;

        if (!email || !password || !confirmPassword) {
            alert("Please complete all fields.");
            return;
        }

        if (password.length < MIN_PASSWORD_LENGTH) {
            alert(
                "Password must be at least " +
                    MIN_PASSWORD_LENGTH +
                    " characters."
            );
            return;
        }

        if (password !== confirmPassword) {
            alert("Passwords do not match.");
            return;
        }

        signupButton.disabled = true;
        signupButton.innerHTML = "Creating account...";

        const { error } =
            await careerGapSupabase.auth.signUp({
                email: email,
                password: password,
            });

        if (error) {
            alert(error.message);
            signupButton.disabled = false;
            signupButton.innerHTML =
                "Create Account <span>→</span>";
            return;
        }

        alert(
            "Account created. Please check your email and confirm your account before signing in."
        );

        window.location.href = "login.html";
    });
});