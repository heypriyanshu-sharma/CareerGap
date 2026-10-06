document.addEventListener("DOMContentLoaded", function () {

    const loginForm =
        document.getElementById("login-form");

    const emailInput =
        document.getElementById("email");

    const passwordInput =
        document.getElementById("password");

    const loginButton =
        document.querySelector(".login-button");

    const passwordToggle =
        document.getElementById("password-toggle");

    const forgotPasswordLink =
        document.getElementById("forgot-password");

    const loginHeading =
        document.getElementById("login-heading");

    const recoveryForm =
        document.getElementById("password-recovery");

    const recoveryHeading =
        document.getElementById("recovery-heading");

    const recoveryEmailInput =
        document.getElementById("recovery-email");

    const recoverySubmitButton =
        document.getElementById("recovery-submit");

    const recoveryStatus =
        document.getElementById("recovery-status");

    const recoveryBackLink =
        document.getElementById("recovery-back");

    const homeBackLink =
        document.getElementById("home-back");

    const signupPrompt =
        document.getElementById("signup-prompt");


    if (
        !loginForm ||
        !emailInput ||
        !passwordInput ||
        !loginButton
    ) {
        console.error(
            "CareerGap login form could not be initialized."
        );

        return;
    }


    // =================================================
    // SHOW / HIDE PASSWORD
    // =================================================

    if (passwordToggle) {

    const openEye =
        passwordToggle.querySelector(
            ".password-eye-open"
        );

    const closedEye =
        passwordToggle.querySelector(
            ".password-eye-closed"
        );

    passwordToggle.addEventListener(
        "click",
        function () {

            const isPassword =
                passwordInput.type === "password";


            passwordInput.type =
                isPassword
                    ? "text"
                    : "password";


            openEye.classList.toggle(
                "hidden",
                isPassword
            );

            closedEye.classList.toggle(
                "hidden",
                !isPassword
            );


            passwordToggle.setAttribute(
                "aria-label",
                isPassword
                    ? "Hide password"
                    : "Show password"
            );

            passwordToggle.setAttribute(
                "aria-pressed",
                String(isPassword)
            );

        }
    );

}


    // =================================================
    // FORGOT PASSWORD
    // =================================================
    // Recovery is handled entirely by Supabase Auth.
    // The email is only used to ask Supabase to send
    // a reset link, and the response message is
    // deliberately generic so it never reveals whether
    // an account exists for that address.
    // =================================================

    function setRecoveryStatus(message, type) {

        if (!recoveryStatus) {
            return;
        }

        recoveryStatus.textContent = message;

        recoveryStatus.className =
            `recovery-status ${type}`.trim();

    }


    function showRecovery() {

        // Reuse the email the visitor already typed
        // when it looks like a valid address.
        const typedEmail =
            emailInput.value.trim();

        if (
            recoveryEmailInput &&
            typedEmail &&
            typedEmail.includes("@")
        ) {
            recoveryEmailInput.value = typedEmail;
        }

        if (loginForm) {
            loginForm.classList.add("hidden");
        }

        if (loginHeading) {
            loginHeading.classList.add("hidden");
        }

        if (signupPrompt) {
            signupPrompt.classList.add("hidden");
        }

        if (homeBackLink) {
            homeBackLink.classList.add("hidden");
        }

        if (recoveryForm) {
            recoveryForm.classList.remove("hidden");
        }

        if (recoveryHeading) {
            recoveryHeading.classList.remove("hidden");
        }

        if (recoveryBackLink) {
            recoveryBackLink.classList.remove("hidden");
        }

        setRecoveryStatus("", "");

        if (recoveryEmailInput) {
            recoveryEmailInput.focus();
        }

    }


    function showLogin() {

        if (recoveryForm) {
            recoveryForm.classList.add("hidden");
        }

        if (recoveryHeading) {
            recoveryHeading.classList.add("hidden");
        }

        if (recoveryBackLink) {
            recoveryBackLink.classList.add("hidden");
        }

        if (loginForm) {
            loginForm.classList.remove("hidden");
        }

        if (loginHeading) {
            loginHeading.classList.remove("hidden");
        }

        if (signupPrompt) {
            signupPrompt.classList.remove("hidden");
        }

        if (homeBackLink) {
            homeBackLink.classList.remove("hidden");
        }

        setRecoveryStatus("", "");

    }


    if (forgotPasswordLink) {

        forgotPasswordLink.addEventListener(
            "click",
            function (event) {

                event.preventDefault();

                showRecovery();

            }
        );

    }


    if (recoveryBackLink) {

        recoveryBackLink.addEventListener(
            "click",
            function (event) {

                event.preventDefault();

                showLogin();

            }
        );

    }


    if (recoveryForm) {

        recoveryForm.addEventListener(
            "submit",
            async function (event) {

                event.preventDefault();

                const recoveryEmail =
                    recoveryEmailInput
                        ? recoveryEmailInput.value.trim()
                        : "";

                if (
                    !recoveryEmail ||
                    !recoveryEmail.includes("@")
                ) {

                    setRecoveryStatus(
                        "Please enter a valid email address.",
                        "error"
                    );

                    return;

                }


                if (recoverySubmitButton) {
                    recoverySubmitButton.disabled = true;
                    recoverySubmitButton.textContent =
                        "Sending...";
                }


                // The redirect target is derived from the
                // page origin, so local development and
                // the deployed site each resolve to their
                // own reset-password page.
                const redirectTo =
                    window.location.origin +
                    "/reset-password.html";


                const { error } =
                    await careerGapSupabase.auth
                        .resetPasswordForEmail(
                            recoveryEmail,
                            {
                                redirectTo: redirectTo
                            }
                        );


                if (recoverySubmitButton) {
                    recoverySubmitButton.disabled = false;
                    recoverySubmitButton.textContent =
                        "Send reset link";
                }


                if (error) {

                    setRecoveryStatus(
                        error.message ||
                            "Unable to send the reset link. Please try again.",
                        "error"
                    );

                    return;

                }


                // Generic on purpose: Supabase's response
                // must not be used to guess which email
                // addresses have an account.
                setRecoveryStatus(
                    "If an account exists for that email, " +
                        "a password reset link has been sent.",
                    "success"
                );

            }
        );

    }


    // =================================================
    // LOGIN
    // =================================================

    loginForm.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();


            const email =
                emailInput.value.trim();

            const password =
                passwordInput.value;


            if (!email || !password) {

                alert(
                    "Please enter your email and password."
                );

                return;

            }


            loginButton.disabled = true;

            loginButton.innerHTML =
                "Signing in...";


            const { error } =
                await careerGapSupabase.auth
                    .signInWithPassword({
                        email: email,
                        password: password
                    });


            if (error) {

                alert(error.message);

                loginButton.disabled = false;

                loginButton.innerHTML =
                    "Sign In <span>→</span>";

                return;

            }


            window.location.href =
                "index.html";

        }
    );

});