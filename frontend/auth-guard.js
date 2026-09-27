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

    const logoutButton =
        document.getElementById("logout-button");

    if (logoutButton) {
        logoutButton.addEventListener(
            "click",
            async function () {
                logoutButton.disabled = true;
                logoutButton.textContent = "Logging out...";

                const { error } =
                    await careerGapSupabase.auth.signOut();

                if (error) {
                    alert(
                        "Unable to log out. Please try again."
                    );

                    logoutButton.disabled = false;
                    logoutButton.textContent = "Log out";
                    return;
                }

                window.location.replace("login.html");
            }
        );
    }

    document.documentElement.style.visibility = "visible";
})();