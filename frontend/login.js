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