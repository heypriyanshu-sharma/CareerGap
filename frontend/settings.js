// =========================================================
// CAREERGAP — SETTINGS PAGE
// =========================================================
//
// Sign out reuses the shared careerGapSignOut() helper from
// supabase-config.js, the same one the account menu uses; there is no
// second auth path on this page. Delete Account asks the backend to
// delete the account behind the verified session, so the target user is
// always the signed-in user, and then clears the now-invalid session
// through that same helper.

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const emailLabel =
            document.getElementById(
                "settings-email"
            );

        const nameLabel =
            document.getElementById(
                "settings-name"
            );

        const statusLabel =
            document.getElementById(
                "settings-status"
            );

        const signOutButton =
            document.getElementById(
                "settings-signout"
            );

        const deleteButton =
            document.getElementById(
                "settings-delete-account"
            );

        const modal =
            document.getElementById(
                "delete-modal"
            );

        const deleteCancel =
            document.getElementById(
                "delete-cancel"
            );

        const deleteConfirm =
            document.getElementById(
                "delete-confirm"
            );

        // Same resolution as script.js: the meta tag override applies
        // only on localhost.
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

        function resolveUserIdentity(user) {

            if (!user) {
                return "";
            }

            const metadata =
                user.user_metadata &&
                typeof user.user_metadata === "object"
                    ? user.user_metadata
                    : {};

            const fullName =
                metadata.full_name ||
                metadata.name ||
                metadata.user_name;

            if (
                typeof fullName === "string" &&
                fullName.trim()
            ) {
                return fullName.trim();
            }

            if (
                typeof user.email === "string" &&
                user.email.trim()
            ) {
                return user.email.trim();
            }

            return "";
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

        async function loadAccount() {

            const { data, error } =
                await careerGapSupabase.auth
                    .getSession();

            if (error || !data.session) {
                window.location.replace(
                    "login.html"
                );

                return;
            }

            const user = data.session.user;

            if (emailLabel) {
                emailLabel.textContent =
                    user.email || "";
            }

            if (nameLabel) {
                nameLabel.textContent =
                    resolveUserIdentity(user);
            }

            try {

                const accessToken =
                    data.session.access_token;

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
                    return;
                }

                const payload =
                    await response.json();

                const profile =
                    payload.profile || {};

                if (
                    profile.full_name &&
                    nameLabel
                ) {
                    nameLabel.textContent =
                        profile.full_name;
                }

            } catch (_) {
                // The account information below is already filled
                // from the session, so a profile read failure is
                // not worth surfacing here.
            }

        }

        async function signOut() {

            if (signOutButton) {
                signOutButton.disabled = true;
                signOutButton.textContent =
                    "Signing out...";
            }

            const result = await careerGapSignOut();

            if (!result.ok) {
                setStatus(
                    "Unable to sign out. Please try again.",
                    "error"
                );

                if (signOutButton) {
                    signOutButton.disabled = false;
                    signOutButton.textContent =
                        "Sign out";
                }

                return;
            }

        }

        function openModal() {

            if (!modal) {
                return;
            }

            modal.classList.remove("hidden");

            setStatus("");

            if (deleteConfirm) {
                deleteConfirm.focus();
            }

        }

        function closeModal() {

            if (!modal) {
                return;
            }

            modal.classList.add("hidden");

            if (deleteButton) {
                deleteButton.focus();
            }

        }

        async function confirmDelete() {

            const accessToken =
                await getAccessToken();

            if (!accessToken) {
                return;
            }

            if (deleteConfirm) {
                deleteConfirm.disabled = true;
                deleteConfirm.textContent =
                    "Deleting...";
            }

            setStatus("");

            try {

                const response =
                    await fetch(
                        `${API_BASE_URL}/auth/delete-account`,
                        {
                            method: "DELETE",

                            headers: {
                                Authorization:
                                    `Bearer ${accessToken}`
                            }
                        }
                    );

                if (!response.ok) {

                    let detail =
                        "Unable to delete your account.";

                    try {
                        const error =
                            await response.json();
                        detail =
                            error.detail || detail;
                    } catch (_) {}

                    throw new Error(detail);
                }

                // The account is gone, so the local session is no
                // longer valid. Clear it through the shared helper
                // before leaving the page.
                await careerGapSignOut();

                return;

            } catch (error) {

                console.error(
                    "Delete account error:",
                    error
                );

                setStatus(
                    error.message ||
                        "Unable to delete your account.",
                    "error"
                );

                closeModal();

            } finally {

                if (deleteConfirm) {
                    deleteConfirm.disabled = false;
                    deleteConfirm.textContent =
                        "Delete";
                }

            }

        }

        if (signOutButton) {
            signOutButton.addEventListener(
                "click",
                signOut
            );
        }

        if (deleteButton) {
            deleteButton.addEventListener(
                "click",
                openModal
            );
        }

        if (deleteCancel) {
            deleteCancel.addEventListener(
                "click",
                closeModal
            );
        }

        if (deleteConfirm) {
            deleteConfirm.addEventListener(
                "click",
                confirmDelete
            );
        }

        document.addEventListener(
            "keydown",
            function (event) {

                if (
                    event.key === "Escape" &&
                    modal &&
                    !modal.classList.contains(
                        "hidden"
                    )
                ) {
                    closeModal();
                }

            }
        );

        if (modal) {
            modal.addEventListener(
                "click",
                function (event) {
                    if (event.target === modal) {
                        closeModal();
                    }
                }
            );
        }

        loadAccount();

    }
);