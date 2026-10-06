// =========================================================
// CAREERGAP — PROFILE PAGE
// =========================================================
//
// Reuses the existing Supabase session and the same API base URL
// resolution as script.js, so this page talks to the same backend in
// local development and in production.

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const form =
            document.getElementById(
                "profile-form"
            );

        const fullNameInput =
            document.getElementById(
                "profile-full-name"
            );

        const targetRoleInput =
            document.getElementById(
                "profile-target-role"
            );

        const experienceLevelInput =
            document.getElementById(
                "profile-experience-level"
            );

        const saveButton =
            document.getElementById(
                "profile-save"
            );

        const statusLabel =
            document.getElementById(
                "profile-status"
            );

        const pageAvatar =
            document.getElementById(
                "profile-page-avatar"
            );

        const pageName =
            document.getElementById(
                "profile-page-name"
            );

        const pageEmail =
            document.getElementById(
                "profile-page-email"
            );

        // Mirrors the resolution in script.js: the meta tag override
        // only applies on localhost, so the deployed frontend can never
        // point at a local backend.
        const metaApiUrl =
            document.querySelector(
                'meta[name="api-base-url"]'
            );

        const configuredApiUrl =
            metaApiUrl
                ? metaApiUrl.getAttribute("content").trim()
                : "";

        const isLocalhost =
            window.location.protocol === "file:" ||
            window.location.hostname === "localhost" ||
            window.location.hostname === "127.0.0.1";

        const API_BASE_URL =
            configuredApiUrl && isLocalhost
                ? configuredApiUrl
                : isLocalhost
                    ? "http://127.0.0.1:8001"
                    : "https://careergap.onrender.com";

        function setStatus(
            message,
            type = ""
        ) {

            if (!statusLabel) {
                return;
            }

            statusLabel.textContent = message;

            statusLabel.className =
                `account-status ${type}`.trim();

        }

        function safeAvatarUrl(value) {

            if (
                typeof value !== "string"
            ) {
                return "";
            }

            const trimmed = value.trim();

            if (
                !trimmed.startsWith("http://")
                && !trimmed.startsWith("https://")
            ) {
                return "";
            }

            try {
                new URL(trimmed);
            } catch (_) {
                return "";
            }

            return trimmed;

        }

        function getInitials(value) {

            if (!value) {
                return "?";
            }

            const parts =
                value.trim().split(/\s+/);

            if (parts.length === 1) {
                return parts[0]
                    .charAt(0)
                    .toUpperCase();
            }

            return (
                parts[0].charAt(0) +
                parts[parts.length - 1].charAt(0)
            ).toUpperCase();

        }

        function setAvatar(
            value,
            avatarUrl
        ) {

            if (!pageAvatar) {
                return;
            }

            const safeUrl =
                safeAvatarUrl(avatarUrl);

            if (safeUrl) {
                pageAvatar.style.backgroundImage =
                    `url("${safeUrl}")`;
                pageAvatar.textContent = "";
                return;
            }

            pageAvatar.textContent =
                getInitials(value);

            pageAvatar.style.backgroundImage =
                "none";

        }

        function renderIdentity(
            user,
            profile
        ) {

            const email =
                user.email || "";

            const name =
                (profile &&
                    profile.full_name &&
                    profile.full_name.trim()) ||
                email;

            if (pageName) {
                pageName.textContent = name;
            }

            if (pageEmail) {
                pageEmail.textContent = email;
            }

            setAvatar(
                name,
                profile && profile.avatar_url
            );

        }

        function fillForm(profile) {

            if (fullNameInput) {
                fullNameInput.value =
                    (profile &&
                        profile.full_name) ||
                    "";
            }

            if (targetRoleInput) {
                targetRoleInput.value =
                    (profile &&
                        profile.target_role) ||
                    "";
            }

            if (experienceLevelInput) {
                experienceLevelInput.value =
                    (profile &&
                        profile.experience_level) ||
                    "";
            }

        }

        async function getAccessToken() {

            const { data, error } =
                await careerGapSupabase.auth
                    .getSession();

            if (error || !data.session) {
                window.location.replace(
                    "login.html"
                );

                return null;
            }

            return data.session.access_token;

        }

        async function loadProfile() {

            const accessToken =
                await getAccessToken();

            if (!accessToken) {
                return;
            }

            try {

                const response =
                    await fetch(
                        `${API_BASE_URL}/auth/profile`,
                        {
                            headers: {
                                Authorization:
                                    `Bearer ${accessToken}`
                            }
                        }
                    );

                if (!response.ok) {
                    throw new Error(
                        "Unable to load profile."
                    );
                }

                const data =
                    await response.json();

                const profile =
                    data.profile || {};

                const {
                    data: sessionData } =
                        await careerGapSupabase
                            .auth
                            .getSession();

                renderIdentity(
                    sessionData.session.user,
                    profile
                );

                fillForm(profile);

            } catch (error) {

                console.error(
                    "Profile load error:",
                    error
                );

                setStatus(
                    "Unable to load your profile.",
                    "error"
                );

            }

        }

        async function saveProfile(event) {

            event.preventDefault();

            const accessToken =
                await getAccessToken();

            if (!accessToken) {
                return;
            }

            if (saveButton) {
                saveButton.disabled = true;
                saveButton.textContent = "Saving...";
            }

            setStatus("");

            const payload = {
                full_name:
                    fullNameInput
                        ? fullNameInput.value
                        : "",
                target_role:
                    targetRoleInput
                        ? targetRoleInput.value
                        : "",
                experience_level:
                    experienceLevelInput &&
                    experienceLevelInput.value
                        ? experienceLevelInput.value
                        : null
            };

            try {

                const response =
                    await fetch(
                        `${API_BASE_URL}/auth/profile`,
                        {
                            method: "PUT",

                            headers: {
                                "Content-Type":
                                    "application/json",

                                Authorization:
                                    `Bearer ${accessToken}`
                            },

                            body:
                                JSON.stringify(payload)
                        }
                    );

                if (!response.ok) {

                    let detail =
                        "Unable to save your profile.";

                    try {
                        const error =
                            await response.json();
                        detail =
                            error.detail || detail;
                    } catch (_) {}

                    throw new Error(detail);
                }

                const profile =
                    await response.json();

                fillForm(profile);

                setStatus(
                    "Profile saved.",
                    "success"
                );

                const {
                    data: sessionData
                } = await careerGapSupabase.auth
                    .getSession();

                renderIdentity(
                    sessionData.session.user,
                    profile
                );

                // The save succeeded, so hand the user back to
                // the dashboard. Only the success path redirects:
                // a failed or rejected request falls through to
                // the catch below and stays on the page.
                window.setTimeout(function () {
                    window.location.href = "index.html";
                }, 800);

            } catch (error) {

                console.error(
                    "Profile save error:",
                    error
                );

                setStatus(
                    error.message ||
                        "Unable to save your profile.",
                    "error"
                );

            } finally {

                if (saveButton) {
                    saveButton.disabled = false;
                    saveButton.textContent =
                        "Save profile";
                }

            }

        }

        if (form) {
            form.addEventListener(
                "submit",
                saveProfile
            );
        }


        // =================================================
        // CHANGE PASSWORD
        // =================================================
        // Password changes go straight to Supabase Auth
        // with the existing session. The current password
        // is never requested, read or displayed: Supabase
        // only allows setting a new one.
        // =================================================

        const MIN_PASSWORD_LENGTH = 6;

        const changePasswordButton =
            document.getElementById(
                "change-password"
            );

        const changePasswordForm =
            document.getElementById(
                "change-password-form"
            );

        const newPasswordInput =
            document.getElementById(
                "new-password"
            );

        const confirmPasswordInput =
            document.getElementById(
                "confirm-new-password"
            );

        const updatePasswordButton =
            document.getElementById(
                "update-password"
            );

        const passwordStatusLabel =
            document.getElementById(
                "password-status"
            );


        function setPasswordStatus(
            message,
            type = ""
        ) {

            if (!passwordStatusLabel) {
                return;
            }

            passwordStatusLabel.textContent =
                message;

            passwordStatusLabel.className =
                `account-status ${type}`.trim();

        }


        // =================================================
        // SHOW / HIDE PASSWORD
        // Matches the login page pattern. Toggling only
        // swaps the input type, so the entered value is
        // never read or modified.
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
            newPasswordInput,
            document.getElementById(
                "new-password-toggle"
            )
        );

        setupPasswordToggle(
            confirmPasswordInput,
            document.getElementById(
                "confirm-new-password-toggle"
            )
        );


        if (
            changePasswordButton &&
            changePasswordForm
        ) {

            changePasswordButton.addEventListener(
                "click",
                function () {

                    const isHidden =
                        changePasswordForm.classList
                            .contains("hidden");

                    changePasswordForm.classList
                        .toggle("hidden");

                    if (
                        isHidden &&
                        newPasswordInput
                    ) {
                        newPasswordInput.focus();
                    }

                }
            );

        }


        if (changePasswordForm) {

            changePasswordForm.addEventListener(
                "submit",
                async function (event) {

                    event.preventDefault();

                    const newPassword =
                        newPasswordInput
                            ? newPasswordInput.value
                            : "";

                    const confirmPassword =
                        confirmPasswordInput
                            ? confirmPasswordInput.value
                            : "";


                    if (!newPassword || !confirmPassword) {

                        setPasswordStatus(
                            "Both password fields are required.",
                            "error"
                        );

                        return;

                    }


                    if (
                        newPassword.length <
                        MIN_PASSWORD_LENGTH
                    ) {

                        setPasswordStatus(
                            "Password must be at least " +
                                MIN_PASSWORD_LENGTH +
                                " characters.",
                            "error"
                        );

                        return;

                    }


                    if (newPassword !== confirmPassword) {

                        setPasswordStatus(
                            "Passwords do not match.",
                            "error"
                        );

                        return;

                    }


                    if (updatePasswordButton) {
                        updatePasswordButton.disabled =
                            true;
                        updatePasswordButton.textContent =
                            "Updating...";
                    }


                    const { error } =
                        await careerGapSupabase.auth
                            .updateUser({
                                password: newPassword
                            });


                    if (error) {

                        setPasswordStatus(
                            error.message ||
                                "Unable to update your password.",
                            "error"
                        );

                        if (updatePasswordButton) {
                            updatePasswordButton.disabled =
                                false;
                            updatePasswordButton.textContent =
                                "Update Password";
                        }

                        return;

                    }


                    setPasswordStatus(
                        "Password updated successfully.",
                        "success"
                    );

                    changePasswordForm.reset();

                    if (changePasswordForm) {
                        changePasswordForm.classList
                            .add("hidden");
                    }

                }
            );

        }


        loadProfile();

    }
);