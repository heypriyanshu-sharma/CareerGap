document.addEventListener("DOMContentLoaded", function () {

    // =================================================
    // PASSWORD RESET
    // =================================================
    // The reset link Supabase emails carries a short-lived
    // recovery session in the URL. This page only accepts
    // a new password through that session; the current
    // password is never requested, read or displayed.
    // =================================================

    const MIN_PASSWORD_LENGTH = 6;

    const form =
        document.getElementById("reset-password-form");

    const passwordInput =
        document.getElementById("new-password");

    const confirmPasswordInput =
        document.getElementById(
            "confirm-new-password"
        );

    const updateButton =
        document.getElementById("reset-submit");

    const statusLabel =
        document.getElementById("reset-status");


    if (!form || !passwordInput || !confirmPasswordInput) {
        console.error(
            "CareerGap password reset form could not be initialized."
        );

        return;
    }


    function setStatus(message, type) {

        if (!statusLabel) {
            return;
        }

        statusLabel.textContent = message;

        statusLabel.className =
            `recovery-status ${type}`.trim();

    }


    // =================================================
    // SHOW / HIDE PASSWORD
    // Matches the existing login and signup pattern:
    // toggling only swaps the input type, so the
    // entered value is never read or modified.
    // =================================================

    function setupPasswordToggle(input, toggle) {

        if (!input || !toggle) {
            return;
        }

        const openEye =
            toggle.querySelector(
                ".password-eye-open"
            );

        const closedEye =
            toggle.querySelector(
                ".password-eye-closed"
            );

        toggle.addEventListener("click", function () {

            const isPassword =
                input.type === "password";

            input.type =
                isPassword ? "text" : "password";

            if (openEye) {
                openEye.classList.toggle(
                    "hidden",
                    isPassword
                );
            }

            if (closedEye) {
                closedEye.classList.toggle(
                    "hidden",
                    !isPassword
                );
            }

            toggle.setAttribute(
                "aria-label",
                isPassword
                    ? "Hide password"
                    : "Show password"
            );

            toggle.setAttribute(
                "aria-pressed",
                String(isPassword)
            );

            input.focus();

        });

    }


    setupPasswordToggle(
        passwordInput,
        document.getElementById("new-password-toggle")
    );

    setupPasswordToggle(
        confirmPasswordInput,
        document.getElementById(
            "confirm-new-password-toggle"
        )
    );


    // =================================================
    // RECOVERY SESSION CHECK
    // =================================================
    // Supabase places the recovery session in the URL
    // fragment when the emailed link is opened. The
    // form stays hidden until a valid session is
    // detected, so an expired or malformed link can
    // never be used to set a password.
    // =================================================

    let recoveryActive = false;


    function enableForm() {

        if (recoveryActive) {
            return;
        }

        recoveryActive = true;

        form.classList.remove("hidden");

        setStatus("", "");

    }


    function rejectForm(message) {

        form.classList.add("hidden");

        setStatus(message, "error");

    }


    careerGapSupabase.auth.onAuthStateChange(
        function (event, session) {

            if (
                event === "PASSWORD_RECOVERY" &&
                session
            ) {
                enableForm();
            }

        }
    );


    // The session may already be cached by the time
    // this page runs, in which case the event above
    // fired before this subscription was registered.
    careerGapSupabase.auth.getSession().then(
        function ({ data }) {

            if (data && data.session) {
                enableForm();
                return;
            }

            // Give the client a moment to finish
            // reading the recovery session from the
            // URL before declaring the link invalid.
            window.setTimeout(function () {

                careerGapSupabase.auth.getSession()
                    .then(function ({ data }) {

                        if (
                            !recoveryActive &&
                            !(data && data.session)
                        ) {
                            rejectForm(
                                "This password reset " +
                                    "link is invalid or " +
                                    "has expired. Please " +
                                    "request a new one."
                            );
                        }

                    });

            }, 500);

        }
    );


    // =================================================
    // UPDATE PASSWORD
    // =================================================

    form.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();

            if (!recoveryActive) {
                rejectForm(
                    "This password reset link is " +
                        "invalid or has expired. Please " +
                        "request a new one."
                );

                return;
            }


            const password = passwordInput.value;

            const confirmPassword =
                confirmPasswordInput.value;


            if (!password || !confirmPassword) {

                setStatus(
                    "Both password fields are required.",
                    "error"
                );

                return;

            }


            if (password.length < MIN_PASSWORD_LENGTH) {

                setStatus(
                    "Password must be at least " +
                        MIN_PASSWORD_LENGTH +
                        " characters.",
                    "error"
                );

                return;

            }


            if (password !== confirmPassword) {

                setStatus(
                    "Passwords do not match.",
                    "error"
                );

                return;

            }


            if (updateButton) {
                updateButton.disabled = true;
                updateButton.textContent =
                    "Updating...";
            }


            const { error } =
                await careerGapSupabase.auth
                    .updateUser({
                        password: password
                    });


            if (error) {

                setStatus(
                    error.message ||
                        "Unable to update your password.",
                    "error"
                );

                if (updateButton) {
                    updateButton.disabled = false;
                    updateButton.textContent =
                        "Update Password";
                }

                return;

            }


            setStatus(
                "Password updated successfully.",
                "success"
            );

            form.reset();

            window.setTimeout(function () {
                window.location.href = "login.html";
            }, 800);

        }
    );

});