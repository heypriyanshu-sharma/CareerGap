document.addEventListener("DOMContentLoaded", function () {
    const signupForm = document.getElementById("signup-form");
    const emailInput = document.getElementById("email");
    const passwordInput = document.getElementById("password");
    const confirmPasswordInput =
        document.getElementById("confirm-password");
    const signupButton = document.querySelector(".login-button");

    signupForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const email = emailInput.value.trim();
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;

        if (!email || !password || !confirmPassword) {
            alert("Please complete all fields.");
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