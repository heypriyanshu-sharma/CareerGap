document.documentElement.style.visibility = "hidden";

(async function () {
    const { data, error } =
        await careerGapSupabase.auth.getSession();

    if (error || !data.session) {
        window.location.replace("login.html");
        return;
    }

    const userEmail =
        document.getElementById("user-email");

    if (userEmail) {
        userEmail.textContent =
            data.session.user.email || "";
    }

    const authActionButton =
    document.getElementById(
        "auth-action-button"
    );

if (authActionButton) {

    const { data } =
        await careerGapSupabase.auth.getSession();

    if (!data.session) {

        authActionButton.textContent =
            "Login";

        authActionButton.disabled =
            false;

        authActionButton.addEventListener(
            "click",
            function () {
                window.location.replace(
                    "login.html"
                );
            }
        );

    } else {

        authActionButton.textContent =
            "Log out";

        authActionButton.disabled =
            false;

        authActionButton.addEventListener(
            "click",
            async function () {

                authActionButton.disabled =
                    true;

                authActionButton.textContent =
                    "Logging out...";

                const { error } =
                    await careerGapSupabase.auth.signOut();

                if (error) {

                    alert(
                        "Unable to log out. Please try again."
                    );

                    authActionButton.disabled =
                        false;

                    authActionButton.textContent =
                        "Log out";

                    return;
                }

                window.location.replace(
                    "login.html"
                );
            }
        );
    }
}

    document.documentElement.style.visibility = "visible";
})();