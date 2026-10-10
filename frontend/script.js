// =========================================================
// CAREERGAP FRONTEND
// =========================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        // =================================================
        // ELEMENTS
        // =================================================

        const addProjectButton =
            document.getElementById("add-project");

        const projectsContainer =
            document.getElementById("projects-container");

        const analyzeButton =
            document.getElementById("analyze-button");

        const resumeInput =
            document.getElementById("resume");

        const jobDescriptionInput =
            document.getElementById("job-description");

        const resumeFileInput =
            document.getElementById("resume-file");

        const jobDescriptionFileInput =
            document.getElementById("job-description-file");

        const resumeUploadButton =
            document.getElementById("resume-upload-button");

        const jobDescriptionUploadButton =
            document.getElementById(
                "job-description-upload-button"
            );

        const resumeUploadStatus =
            document.getElementById(
                "resume-upload-status"
            );

        const jobDescriptionUploadStatus =
            document.getElementById(
                "job-description-upload-status"
            );

        const resultsSection =
            document.getElementById("results");

        const analysisTabs =
            document.getElementById("analysis-tabs");

        const currentAnalysisTab =
            document.getElementById(
                "current-analysis-tab"
            );

        const historyTab =
            document.getElementById("history-tab");
        
        const savedAnalysisTab =
            document.getElementById(
                "saved-analysis-tab"
            );
        const savedAnalysisSection =
            document.getElementById(
            "saved-analysis"
            );

        const savedResultsContent =
            document.getElementById(
            "saved-results-content"
            );

        const analysisHistorySection =
            document.getElementById(
                "analysis-history"
            );

        const resultsContent =
            document.getElementById("results-content");

        const loadingSection =
            document.getElementById("loading");

        const analysisHistoryList =
            document.getElementById(
                "analysis-history-list"
            );

        // =================================================
        // DASHBOARD NAVIGATION
        // =================================================

        const primaryNavButtons =
            Array.from(
                document.querySelectorAll(
                    ".primary-nav-btn"
                )
            );

        const subnav =
            document.getElementById(
                "analysis-subnav"
            );

        const subnavTabs =
            Array.from(
                document.querySelectorAll(
                    ".analysis-subnav-tab"
                )
            );

        const analyzeSection =
            document.getElementById(
                "analyze"
            );

        const resumeBuilderSection =
            document.getElementById(
                "resume-builder"
            );

        const brandLink =
            document.querySelector(
                ".brand"
            );

        let activeWorkspace = "analyze";

        let analysisHistoryData = [];
        let currentAnalysis = null;

        function setActiveWorkspace(view) {

            activeWorkspace = view;

            primaryNavButtons.forEach(
                function (button) {

                    const isActive =
                        button.dataset.view === view;

                    button.classList.toggle(
                        "active",
                        isActive
                    );

                    button.setAttribute(
                        "aria-current",
                        isActive
                            ? "page"
                            : "false"
                    );
                }
            );

            const onAnalyze =
                view === "analyze";

            if (analyzeSection) {
                analyzeSection.classList.toggle(
                    "hidden",
                    !onAnalyze
                );
            }

            if (resumeBuilderSection) {
                resumeBuilderSection.classList.toggle(
                    "hidden",
                    view !== "resume-builder"
                );
            }

            if (analysisTabs) {
                analysisTabs.classList.toggle(
                    "hidden",
                    view === "resume-builder"
                );
            }

            if (onAnalyze) {
                setAnalysisView("current");
                return;
            }

            if (view === "saved-analyses") {
                setAnalysisView("history");
                loadAnalysisHistory();
                return;
            }

            if (resultsSection) {
                resultsSection.classList.add(
                    "hidden"
                );
            }

            if (analysisHistorySection) {
                analysisHistorySection.classList.add(
                    "hidden"
                );
            }

            if (savedAnalysisSection) {
                savedAnalysisSection.classList.add(
                    "hidden"
                );
            }

            if (currentAnalysisTab) {
                currentAnalysisTab.classList.remove(
                    "active"
                );
            }

            if (historyTab) {
                historyTab.classList.remove(
                    "active"
                );
            }

            if (savedAnalysisTab) {
                savedAnalysisTab.classList.remove(
                    "active"
                );
            }

            syncSubnavState();
        }

        function scrollToWorkspace(view) {

            let target = null;

            if (view === "analyze") {
                target = analyzeSection;
            } else if (
                view === "resume-builder"
            ) {
                target = resumeBuilderSection;
            } else if (
                view === "saved-analyses"
            ) {
                target = analysisHistorySection;
            }

            if (!target) {
                return;
            }

            const reduced =
                window.matchMedia(
                    "(prefers-reduced-motion: reduce)"
                ).matches;

            target.scrollIntoView({
                behavior: reduced
                    ? "auto"
                    : "smooth",
                block: "start",
            });
        }

        function syncStickyOffsets() {

            const navbar =
                document.querySelector(
                    ".navbar"
                );

            if (navbar) {

                const height =
                    navbar.getBoundingClientRect()
                        .height;

                if (height > 0) {

                    document.documentElement.style
                        .setProperty(
                            "--navbar-offset",
                            Math.round(height) + "px"
                        );
                }
            }

            if (subnav) {

                const height =
                    subnav.getBoundingClientRect()
                        .height;

                if (height > 0) {

                    document.documentElement.style
                        .setProperty(
                            "--subnav-offset",
                            Math.round(height) + "px"
                        );
                }
            }
        }

        window.addEventListener(
            "resize",
            function () {

                window.clearTimeout(
                    syncStickyOffsets.timer
                );

                syncStickyOffsets.timer =
                    window.setTimeout(
                        syncStickyOffsets,
                        120
                    );
            }
        );

        window.addEventListener(
            "scroll",
            function () {

                window.clearTimeout(
                    syncStickyOffsets.scrollTimer
                );

                syncStickyOffsets.scrollTimer =
                    window.setTimeout(
                        syncStickyOffsets,
                        80
                    );
            },
            { passive: true }
        );

        function setSubnavTabEnabled(
            tab,
            enabled
        ) {

            if (enabled) {
                tab.removeAttribute(
                    "disabled"
                );
            } else {
                tab.setAttribute(
                    "disabled",
                    "disabled"
                );
            }
        }

        function getVisibleAnalysisContainer() {

            if (
                savedAnalysisSection &&
                savedResultsContent &&
                !savedAnalysisSection.classList.contains(
                    "hidden"
                )
            ) {
                return savedResultsContent;
            }

            if (
                resultsSection &&
                resultsContent &&
                !resultsSection.classList.contains(
                    "hidden"
                )
            ) {
                return resultsContent;
            }

            return null;
        }

        function findSubnavTarget(targetSelector) {

            const container =
                getVisibleAnalysisContainer();

            if (!container) {
                return null;
            }

            return container.querySelector(
                targetSelector
            );
        }

        function syncSubnavState() {

            const container =
                getVisibleAnalysisContainer();

            // Sections such as AI advice, project analysis and
            // resources are optional, so each tab is resolved and
            // enabled on its own instead of gating the whole bar.

            const resolvedTargets =
                subnavTabs.map(
                    function (tab) {

                        return Boolean(
                            findSubnavTarget(
                                tab.dataset.target
                            )
                        );

                    }
                );

            subnavTabs.forEach(
                function (tab, index) {

                    setSubnavTabEnabled(
                        tab,
                        resolvedTargets[index]
                    );

                }
            );

            const isAnalyzing =
                loadingSection &&
                !loadingSection.classList.contains(
                    "hidden"
                );

            const hasNavigableSections =
                !isAnalyzing &&
                Boolean(
                    container
                ) &&
                resolvedTargets.some(
                    function (resolved) {

                        return resolved;

                    }
                );

            if (subnav) {
                subnav.classList.toggle(
                    "hidden",
                    !hasNavigableSections
                );
            }
        }

        function activateSubnavTab(tab) {

            if (
                !tab ||
                tab.hasAttribute("disabled")
            ) {
                return;
            }

            subnavTabs.forEach(
                function (other) {

                    const isActive =
                        other === tab;

                    other.classList.toggle(
                        "active",
                        isActive
                    );

                    other.setAttribute(
                        "aria-selected",
                        isActive
                            ? "true"
                            : "false"
                    );
                }
            );

            const target =
                findSubnavTarget(
                    tab.dataset.target
                );

            if (!target) {
                return;
            }

            const reduced =
                window.matchMedia(
                    "(prefers-reduced-motion: reduce)"
                ).matches;

            target.scrollIntoView({
                behavior: reduced
                    ? "auto"
                    : "smooth",
                block: "start",
            });
        }

        primaryNavButtons.forEach(
            function (button) {

                button.addEventListener(
                    "click",
                    function () {

                        setActiveWorkspace(
                            button.dataset.view
                        );

                        scrollToWorkspace(
                            button.dataset.view
                        );
                    }
                );
            }
        );

        subnavTabs.forEach(
            function (tab) {

                tab.addEventListener(
                    "click",
                    function () {

                        activateSubnavTab(tab);
                    }
                );
            }
        );

        if (brandLink) {

            brandLink.addEventListener(
                "click",
                function () {

                    setActiveWorkspace(
                        "analyze"
                    );
                }
            );
        }

        syncSubnavState();

        syncStickyOffsets();

        // =================================================
        // PROFILE DROPDOWN
        // =================================================

        const profileTrigger =
            document.getElementById("profile-trigger");
        const profileMenu =
            document.getElementById("profile-menu");
        const profileName =
            document.getElementById("profile-name");
        const menuUserName =
            document.getElementById("menu-user-name");
        const menuUserEmail =
            document.getElementById("menu-user-email");
        const menuProfileAvatar =
            document.querySelector(".profile-menu-avatar");
        const profileAvatar =
            document.querySelector(".profile-avatar");

        const menuProfile =
            document.getElementById("menu-profile");
        const menuResumes =
            document.getElementById("menu-resumes");
        const menuAnalyses =
            document.getElementById("menu-analyses");
        const menuSettings =
            document.getElementById("menu-settings");
        const menuSignout =
            document.getElementById("menu-signout");

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

        async function loadProfileForUI(accessToken) {

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
                    return null;
                }

                const data =
                    await response.json();

                return data && data.profile
                    ? data.profile
                    : null;

            } catch (_) {
                return null;
            }

        }

        function resolveProfileName(user, profile) {

            if (
                profile &&
                typeof profile.full_name === "string" &&
                profile.full_name.trim()
            ) {
                return profile.full_name.trim();
            }

            return resolveUserIdentity(user);

        }

        // Only absolute http(s) image URLs are rendered. Anything else
        // falls back to initials, so a stored value can never become a
        // javascript: or data: source.
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

        function getInitials(name) {
            if (!name) return "?";
            const parts = name.trim().split(/\s+/);
            if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
            return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
        }

        function setAvatar(element, user) {
            if (!element) return;
            const metadata = user.user_metadata || {};
            const avatarUrl = safeAvatarUrl(metadata.avatar_url);
            if (avatarUrl) {
                element.style.backgroundImage = `url("${avatarUrl}")`;
                element.textContent = "";
            } else {
                const name = resolveUserIdentity(user) || user.email || "";
                element.textContent = getInitials(name);
                element.style.backgroundImage = "none";
            }
        }

        function updateProfileUI(user, profile) {
            const name = resolveProfileName(user, profile);
            const email = user.email || "";

            if (profileName) {
                profileName.textContent = name || email;
            }
            if (menuUserName) {
                menuUserName.textContent = name || email;
            }
            if (menuUserEmail) {
                menuUserEmail.textContent = email;
            }
            setAvatar(profileAvatar, user);
            setAvatar(menuProfileAvatar, user);

            // Both the navbar trigger and the opened dropdown header
            // show a single initial. It must come from the same resolved
            // display name as the trigger text (the stored
            // profile.full_name), so "PRIYANSHU SHARMA" renders as [P]
            // in both places rather than the email-derived initial.
            const resolvedAvatarName =
                resolveProfileName(user, profile) ||
                user.email || "";
            const avatarInitial =
                resolvedAvatarName.trim()
                    ? resolvedAvatarName.trim().charAt(0).toUpperCase()
                    : "?";

            if (profileAvatar && profileAvatar.textContent) {
                profileAvatar.textContent = avatarInitial;
            }
            if (menuProfileAvatar && menuProfileAvatar.textContent) {
                menuProfileAvatar.textContent = avatarInitial;
            }
        }

        function clearProfileUI() {
            if (profileName) profileName.textContent = "";
            if (menuUserName) menuUserName.textContent = "";
            if (menuUserEmail) menuUserEmail.textContent = "";
            if (profileAvatar) {
                profileAvatar.textContent = "";
                profileAvatar.style.backgroundImage = "none";
            }
            if (menuProfileAvatar) {
                menuProfileAvatar.textContent = "";
                menuProfileAvatar.style.backgroundImage = "none";
            }
        }

        function toggleProfileMenu(forceClose) {
            if (!profileMenu || !profileTrigger) return;

            const isOpen = !profileMenu.classList.contains("hidden");

            if (forceClose || isOpen) {
                profileMenu.classList.add("hidden");
                profileTrigger.setAttribute("aria-expanded", "false");
            } else {
                profileMenu.classList.remove("hidden");
                profileTrigger.setAttribute("aria-expanded", "true");
            }
        }

        function closeProfileMenu() {
            toggleProfileMenu(true);
        }

        function setupSignedOutTrigger() {

            // The account icon is the only route to the sign-in page,
            // so it stays visible when there is no session and simply
            // navigates instead of opening the menu. Hiding it would
            // remove the way back into the product.

            clearProfileUI();

            profileMenu.classList.add("hidden");

            if (profileAvatar) {
                profileAvatar.textContent = "?";
            }

            profileTrigger.setAttribute(
                "aria-label",
                "Log in"
            );

            profileTrigger.setAttribute(
                "aria-expanded",
                "false"
            );

            profileTrigger.addEventListener(
                "click",
                function () {
                    window.location.replace(
                        "login.html"
                    );
                }
            );

        }

        async function setupProfileDropdown() {

            if (!profileTrigger || !profileMenu) return;

            const { data, error } =
                await careerGapSupabase.auth.getSession();

            if (error || !data.session) {

                setupSignedOutTrigger();

                return;

            }

            updateProfileUI(data.session.user);
            profileTrigger.style.display = "flex";

            const accessToken =
                data.session.access_token || "";

            if (accessToken) {
                const profile =
                    await loadProfileForUI(
                        accessToken
                    );
                updateProfileUI(
                    data.session.user,
                    profile
                );
            }

            profileTrigger.addEventListener("click", function (e) {
                e.stopPropagation();
                toggleProfileMenu();
            });

            document.addEventListener("click", function (e) {
                if (
                    profileMenu &&
                    !profileMenu.contains(e.target) &&
                    !profileTrigger.contains(e.target)
                ) {
                    closeProfileMenu();
                }
            });

            document.addEventListener("keydown", function (e) {
                if (e.key === "Escape") {
                    closeProfileMenu();
                }
            });

            if (menuProfile) {
                menuProfile.addEventListener("click", function () {
                    closeProfileMenu();
                    window.location.href = "profile.html";
                });
            }

            if (menuResumes) {
                menuResumes.addEventListener("click", function () {
                    closeProfileMenu();
                    const btn = document.getElementById("nav-resume-builder");
                    if (btn) btn.click();
                });
            }

            if (menuAnalyses) {
                menuAnalyses.addEventListener("click", function () {
                    closeProfileMenu();
                    const btn = document.getElementById("nav-saved-analyses");
                    if (btn) btn.click();
                });
            }

            if (menuSettings) {
                menuSettings.addEventListener("click", function () {
                    closeProfileMenu();
                    window.location.href = "settings.html";
                });
            }

            if (menuSignout) {
                menuSignout.addEventListener("click", async function () {
                    closeProfileMenu();
                    menuSignout.disabled = true;
                    menuSignout.textContent = "Signing out...";

                    const result = await careerGapSignOut();

                    if (!result.ok) {
                        alert("Unable to sign out. Please try again.");
                        menuSignout.disabled = false;
                        menuSignout.innerHTML = `
                            <svg class="menu-icon" viewBox="0 0 24 24" aria-hidden="true">
                                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
                                <polyline points="16 17 21 12 16 7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
                                <line x1="21" y1="12" x2="9" y2="12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
                            </svg>
                            Sign out
                        `;
                        return;
                    }
                });
            }
        }

        setupProfileDropdown();

        // =================================================
        // API CONFIGURATION
        // =================================================

        // Read API base URL from meta tag (local dev override only),
        // otherwise auto-detect: localhost/127.0.0.1 -> local backend,
        // file: protocol -> local backend, otherwise production. The
        // override is scoped to localhost so a local URL in the meta
        // tag can never be used by the deployed frontend.
        const metaApiUrl = document.querySelector('meta[name="api-base-url"]');
        const configuredApiUrl = metaApiUrl ? metaApiUrl.getAttribute("content").trim() : "";
        const isLocalhost =
            window.location.protocol === "file:" ||
            window.location.hostname === "localhost" ||
            window.location.hostname === "127.0.0.1";

        const API_BASE_URL = configuredApiUrl && isLocalhost
            ? configuredApiUrl
            : isLocalhost
            ? "http://127.0.0.1:8001"
            : "https://careergap.onrender.com";

        async function getAccessToken(
            redirectIfMissing = true
        ) {

            const { data, error } =
                await careerGapSupabase.auth.getSession();

            if (error || !data.session) {

                if (redirectIfMissing) {

                    window.location.replace(
                        "login.html"
                    );

                }

                return null;
            }

            return data.session.access_token;
        }

        // =================================================
        // HISTORY
        // =================================================

        async function loadAnalysisHistory() {

            if (!analysisHistoryList) {
                return;
            }

            const accessToken =
                await getAccessToken(false);

            if (!accessToken) {
                return;
            }

            try {

                const response =
                    await fetch(
                        `${API_BASE_URL}/analyses`,
                        {
                            headers: {
                                Authorization:
                                    `Bearer ${accessToken}`
                            }
                        }
                    );

                if (!response.ok) {

                    throw new Error(
                        "Unable to load analysis history."
                    );
                }

                const analyses =
                    await response.json();

                analysisHistoryData =
                    Array.isArray(analyses)
                        ? analyses
                        : [];

                if (!analysisHistoryData.length) {

                    analysisHistoryList.innerHTML = `
                        <div class="empty-state">
                            No previous analyses yet.
                        </div>
                    `;

                    return;
                }

                analysisHistoryList.innerHTML =
                    analysisHistoryData
                        .map(
                            function (item, index) {

                                const analysis =
                                    item.analysis || {};

                                const score =
                                    Number(
                                        analysis.score || 0
                                    );

                                const createdDate =
                                    new Date(
                                        item.created_at
                                    ).toLocaleDateString(
                                        undefined,
                                        {
                                            day: "numeric",
                                            month: "short",
                                            year: "numeric"
                                        }
                                    );

                                return `
                                    <article
                                        class="analysis-history-item"
                                    >

                                        <div>
                                            <h3>
                                                Career Analysis
                                            </h3>

                                            <p>
                                                ${escapeHTML(
                                                    item.job_description
                                                )}
                                            </p>

                                            <span>
                                                ${createdDate}
                                            </span>
                                        </div>

                                        <strong>
                                            ${score.toFixed(1)}%
                                        </strong>

                                        <div
                                            class="analysis-history-actions"
                                        >

                                            <button
                                                type="button"
                                                class="history-view-button"
                                                data-history-index="${index}"
                                            >
                                                View Analysis
                                            </button>

                                            <button
                                                type="button"
                                                class="history-delete-button"
                                                data-history-index="${index}"
                                                data-analysis-id="${escapeHTML(
                                                    String(
                                                        item.id || ""
                                                    )
                                                )}"
                                                aria-label="Delete analysis"
                                                title="Delete analysis"
                                            >
                                                ×
                                            </button>

                                        </div>

                                    </article>
                                `;

                            }
                        )
                        .join("");

            } catch (error) {

                console.error(
                    "Analysis history error:",
                    error
                );

                analysisHistoryList.innerHTML = `
                    <div class="empty-state">
                        Unable to load previous analyses.
                    </div>
                `;
            }
        }

        // =================================================
        // AUTO-GROW TEXTAREAS
        // =================================================

        const TEXTAREA_MAX_HEIGHT = 360;

        function autoGrowTextarea(textarea) {

            if (!textarea) {
                return;
            }

            textarea.style.height = "auto";

            const newHeight =
                Math.min(
                    textarea.scrollHeight,
                    TEXTAREA_MAX_HEIGHT
                );

            textarea.style.height =
                `${newHeight}px`;

            textarea.style.overflowY =
                textarea.scrollHeight >
                TEXTAREA_MAX_HEIGHT
                    ? "auto"
                    : "hidden";
        }

        function setupAutoGrow(textarea) {

            if (!textarea) {
                return;
            }

            autoGrowTextarea(textarea);

            textarea.addEventListener(
                "input",
                function () {
                    autoGrowTextarea(textarea);
                }
            );
        }

        setupAutoGrow(resumeInput);

        setupAutoGrow(
            jobDescriptionInput
        );

        projectsContainer
            .querySelectorAll(
                ".project-description"
            )
            .forEach(setupAutoGrow);

        projectsContainer.addEventListener(
            "input",
            function (event) {

                if (
                    event.target.matches(
                        ".project-description"
                    )
                ) {
                    autoGrowTextarea(
                        event.target
                    );
                }
            }
        );

        // =================================================
        // FILE UPLOAD
        // =================================================

        function setUploadStatus(
            statusElement,
            message,
            type = ""
        ) {

            if (!statusElement) {
                return;
            }

            statusElement.textContent =
                message;

            statusElement.className =
                `upload-status ${type}`.trim();
        }

        function setUploadButtonState(
            button,
            uploading
        ) {

            if (!button) {
                return;
            }

            button.disabled =
                uploading;

            button.classList.toggle(
                "uploading",
                uploading
            );
        }

        async function uploadFile(
            file,
            textarea,
            statusElement,
            uploadButton
        ) {

            if (!file) {
                return;
            }

            setUploadButtonState(
                uploadButton,
                true
            );

            setUploadStatus(
                statusElement,
                "Reading your file..."
            );

            const formData =
                new FormData();

            formData.append(
                "file",
                file
            );

            try {

                const accessToken =
                    await getAccessToken();

                if (!accessToken) {
                    return;
                }

                const response =
                    await fetch(
                        `${API_BASE_URL}/upload`,
                        {
                            method: "POST",
                            headers: {
                                Authorization:
                                    `Bearer ${accessToken}`
                            },
                            body: formData
                        }
                    );

                let responseData = null;

                try {

                    responseData =
                        await response.json();

                } catch (_) {

                    responseData = null;

                }

                if (!response.ok) {

                    const errorMessage =
                        responseData?.detail ||
                        "Unable to process this file.";

                    throw new Error(
                        errorMessage
                    );
                }

                const extractedText =
                    responseData?.text || "";

                if (!extractedText.trim()) {

                    throw new Error(
                        "No readable text was found in this file."
                    );
                }

                textarea.value =
                    extractedText.trim();

                autoGrowTextarea(
                    textarea
                );

                setUploadStatus(
                    statusElement,
                    `${file.name} loaded successfully.`,
                    "success"
                );

            } catch (error) {

                console.error(
                    "File upload error:",
                    error
                );

                setUploadStatus(
                    statusElement,
                    error.message ||
                    "Unable to process this file.",
                    "error"
                );

            } finally {

                setUploadButtonState(
                    uploadButton,
                    false
                );
            }
        }

        function setupFileUpload(
            fileInput,
            uploadButton,
            textarea,
            statusElement
        ) {

            if (
                !fileInput ||
                !uploadButton ||
                !textarea
            ) {
                return;
            }

            uploadButton.addEventListener(
                "click",
                function () {

                    if (
                        !uploadButton.disabled
                    ) {
                        fileInput.click();
                    }
                }
            );

            fileInput.addEventListener(
                "change",
                async function () {

                    const file =
                        fileInput.files?.[0];

                    if (!file) {
                        return;
                    }

                    await uploadFile(
                        file,
                        textarea,
                        statusElement,
                        uploadButton
                    );

                    fileInput.value = "";

                }
            );
        }

        setupFileUpload(
            resumeFileInput,
            resumeUploadButton,
            resumeInput,
            resumeUploadStatus
        );

        setupFileUpload(
            jobDescriptionFileInput,
            jobDescriptionUploadButton,
            jobDescriptionInput,
            jobDescriptionUploadStatus
        );

        // =================================================
        // ADD PROJECT
        // =================================================

        addProjectButton.addEventListener(
            "click",
            function () {

                const project =
                    document.createElement("div");

                project.className =
                    "project-input";

                project.innerHTML = `
                    <div class="project-input-header">

                        <span class="project-input-label">
                            Additional Project
                        </span>

                        <button
                            type="button"
                            class="remove-project-button"
                            aria-label="Remove this project"
                        >
                            &times; Remove
                        </button>

                    </div>

                    <input
                        type="text"
                        class="project-name"
                        placeholder="Project name"
                    >

                    <textarea
                        class="project-description"
                        placeholder="What did you build? Mention technologies, features or problems you solved..."
                    ></textarea>
                `;

                project
                    .querySelector(
                        ".remove-project-button"
                    )
                    .addEventListener(
                        "click",
                        function () {
                            project.remove();
                        }
                    );

                projectsContainer.appendChild(
                    project
                );

                setupAutoGrow(
                    project.querySelector(
                        ".project-description"
                    )
                );
            }
        );

        // =================================================
        // COLLECT PROJECTS
        // =================================================

        function collectProjects() {

            const projectInputs =
                document.querySelectorAll(
                    ".project-input"
                );

            const projects = [];

            projectInputs.forEach(
                function (project) {

                    const name =
                        project
                            .querySelector(
                                ".project-name"
                            )
                            .value
                            .trim();

                    const description =
                        project
                            .querySelector(
                                ".project-description"
                            )
                            .value
                            .trim();

                    projects.push({
                        name: name,
                        description: description
                    });
                }
            );

            return projects;
        }

        // =================================================
        // COLLECT INPUT
        // =================================================

        function collectCareerGapData() {

            return {
                resume:
                    resumeInput.value.trim(),

                job_description:
                    jobDescriptionInput.value.trim(),

                projects:
                    collectProjects()
            };
        }

        // =================================================
        // API — ANALYSIS
        // =================================================

        async function analyzeCareerGap(
            careerGapData
        ) {

            const accessToken =
                await getAccessToken();

            if (!accessToken) {
                return;
            }

            const response =
                await fetch(
                    `${API_BASE_URL}/analyze`,
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json",

                            Authorization:
                                `Bearer ${accessToken}`
                        },

                        body:
                            JSON.stringify(
                                careerGapData
                            )
                    }
                );

            if (!response.ok) {

                let errorMessage =
                    "CareerGap analysis failed.";

                try {

                    const error =
                        await response.json();

                    errorMessage =
                        error.detail ||
                        errorMessage;

                } catch (_) {}

                throw new Error(
                    errorMessage
                );
            }

            const result =
                await response.json();

            const keywords =
                await fetchAtsKeywords(
                    careerGapData
                );

            if (keywords) {
                result.ats_keywords =
                    keywords;
            }

            return result;
        }

        // =================================================
        // API — ATS KEYWORDS
        // =================================================

        async function fetchAtsKeywords(
            careerGapData
        ) {

            const accessToken =
                await getAccessToken(
                    false
                );

            if (!accessToken) {
                return null;
            }

            try {

                const response =
                    await fetch(
                        `${API_BASE_URL}/ats/keywords`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json",

                                Authorization:
                                    `Bearer ${accessToken}`
                            },

                            body:
                                JSON.stringify(
                                    careerGapData
                                )
                        }
                    );

                if (!response.ok) {
                    return null;
                }

                const data =
                    await response.json();

                return Array.isArray(
                    data.keywords
                )
                    ? data.keywords
                    : null;

            } catch (_) {
                return null;
            }
        }

        // =================================================
        // HTML ESCAPING
        // =================================================

        function escapeHTML(value) {

            if (
                value === null ||
                value === undefined
            ) {
                return "";
            }

            return String(value)
                .replaceAll(
                    "&",
                    "&amp;"
                )
                .replaceAll(
                    "<",
                    "&lt;"
                )
                .replaceAll(
                    ">",
                    "&gt;"
                )
                .replaceAll(
                    '"',
                    "&quot;"
                )
                .replaceAll(
                    "'",
                    "&#039;"
                );
        }

        function safeUrl(rawUrl) {
            if (!rawUrl || typeof rawUrl !== "string") {
                return "#";
            }
            const trimmed = rawUrl.trim();
            try {
                const parsed = new URL(trimmed);
                if (
                    parsed.protocol === "http:" ||
                    parsed.protocol === "https:"
                ) {
                    return parsed.href;
                }
            } catch (_) {}
            return "#";
        }

        // =================================================
        // SCORE MESSAGE
        // =================================================

        function getScoreMessage(score) {

            if (score >= 80) {

                return {
                    title:
                        "You're in a strong position.",

                    text:
                        "Your foundation aligns well with the target role. Focus on strengthening the remaining gaps."
                };
            }

            if (score >= 60) {

                return {
                    title:
                        "You're building solid ground.",

                    text:
                        "You already have a meaningful foundation. Focus on the missing skills that matter most."
                };
            }

            if (score >= 40) {

                return {
                    title:
                        "You're finding your direction.",

                    text:
                        "There is a foundation to build on. Use the missing skills as your next learning path."
                };
            }

            return {
                title:
                    "You're on your way.",

                text:
                    "Start with the most important missing skills and strengthen the projects you already have."
            };
        }


        // =================================================
        // SCORE RING
        // =================================================

        function createScoreCard(
            result
        ) {

            const score =
                Number(result.score || 0);

            const radius = 76;

            const circumference =
                2 * Math.PI * radius;

            const offset =
                circumference -
                (score / 100) *
                circumference;

            const message =
                getScoreMessage(score);

            return `
                <article
                    class="dashboard-card score-card"
                >

                    <div class="score-ring">

                        <svg viewBox="0 0 180 180">

                            <circle
                                class="score-ring-track"
                                cx="90"
                                cy="90"
                                r="${radius}"
                            ></circle>

                            <circle
                                class="score-ring-progress"
                                cx="90"
                                cy="90"
                                r="${radius}"
                                stroke-dasharray="${circumference}"
                                stroke-dashoffset="${offset}"
                            ></circle>

                        </svg>

                        <div class="score-ring-content">

                            <span class="score-number">
                                ${score.toFixed(1)}%
                            </span>

                            <span class="score-label">
                                Skill Match
                            </span>

                        </div>

                    </div>

                    <div class="score-copy">

                        <h3>
                            ${escapeHTML(
                                message.title
                            )}
                        </h3>

                        <p>
                            ${escapeHTML(
                                message.text
                            )}
                        </p>

                    </div>

                </article>
            `;
        }

        // =================================================
        // SKILL BREAKDOWN
        // =================================================

        // =================================================
        // ATS — JOB DESCRIPTION KEYWORDS
        // =================================================

        function createAtsKeywords(
            result
        ) {

            const keywords =
                Array.isArray(
                    result.ats_keywords
                )
                    ? result.ats_keywords
                    : [];

            if (keywords.length === 0) {
                return "";
            }

            const items =
                keywords
                    .map(
                        function (keyword) {

                            const importance =
                                String(
                                    keyword.importance ||
                                    "Mentioned"
                                );

                            const frequency =
                                Number(
                                    keyword.frequency
                                ) || 0;

                            const label =
                                importance
                                    .toLowerCase()
                                    .replace(
                                        /[^a-z]+/g,
                                        "-"
                                    );

                            return `
                                <li class="ats-keyword">

                                    <span class="ats-term">
                                        ${escapeHTML(
                                            keyword.term
                                        )}
                                    </span>

                                    <span class="ats-badge ats-badge--${label}">
                                        ${escapeHTML(
                                            importance
                                        )}
                                    </span>

                                    <span class="ats-frequency">
                                        ${escapeHTML(
                                            frequency
                                        )}x
                                    </span>

                                </li>
                            `;
                        }
                    )
                    .join("");

            return `
                <article
                    id="keywords-section"
                    class="dashboard-card ats-card"
                >

                    <div class="card-title">

                        <span class="card-icon">
                            &#9678;
                        </span>

                        Job Description Keywords

                    </div>

                    <p class="ats-note">
                        Keywords extracted from this job
                        description. This is not a score and
                        is not a comparison with your
                        resume.
                    </p>

                    <ul class="ats-list">
                        ${items}
                    </ul>

                </article>
            `;
        }

        function createSkillBreakdown(
            result
        ) {

            const matched =
                result.matched_skills || [];

            const missing =
                result.missing_skills || [];

            const skills = [
                ...matched,
                ...missing
            ];

            if (skills.length === 0) {

                return `
                    <article
                        id="skills-section"
                        class="dashboard-card skill-card"
                    >

                        <div class="card-title">

                            <span class="card-icon">
                                &#9678;
                            </span>

                            Skill Breakdown

                        </div>

                        <div class="empty-state">
                            No skills detected.
                        </div>

                    </article>
                `;
            }

            return `
                <article
                    id="skills-section"
                    class="dashboard-card skill-card"
                >

                    <div class="card-title">

                        <span class="card-icon">
                            &#9678;
                        </span>

                        Skill Breakdown

                    </div>

                    <div class="skill-list">

                        ${skills.map(
                            function (skill) {

                                const isMatched =
                                    matched.includes(
                                        skill
                                    );

                                return `
                                    <div
                                        class="skill-row"
                                    >

                                        <div
                                            class="skill-row-left"
                                        >

                                            <span
                                                class="skill-status ${
                                                    isMatched
                                                        ? "matched"
                                                        : "missing"
                                                }"
                                            >

                                                ${
                                                    isMatched
                                                        ? "&#10003;"
                                                        : "&bull;"
                                                }

                                            </span>

                                            <span>
                                                ${escapeHTML(
                                                    skill
                                                )}
                                            </span>

                                        </div>

                                    </div>
                                `;
                            }
                        ).join("")}

                    </div>

                </article>
            `;
        }

        // =================================================
        // ROLE INSIGHTS
        // =================================================

        function createRoleInsights(
            result
        ) {

            const jobSkills =
                result.job_skills || [];

            const missing =
                result.missing_skills || [];

            return `
                <article
                    class="dashboard-card role-card"
                >

                    <div class="card-title">

                        <span class="card-icon">
                            &#9678;
                        </span>

                        Role Insights

                    </div>

                    <div class="role-stat">

                        <div class="role-stat-label">
                            Target Role
                        </div>

                        <div class="role-stat-value">

                            ${escapeHTML(
                                inferRole(
                                    jobSkills
                                )
                            )}

                        </div>

                    </div>

                    <div class="role-stat">

                        <div class="role-stat-label">
                            Total Skills Found
                        </div>

                        <div class="role-stat-value">
                            ${jobSkills.length}
                        </div>

                    </div>

                    <div class="role-stat">

                        <div class="role-stat-label">
                            Skills Missing
                        </div>

                        <div class="role-stat-value">
                            ${missing.length}
                        </div>

                    </div>

                </article>
            `;
        }

        // =================================================
        // INFER ROLE
        // =================================================

        function inferRole(
            jobSkills
        ) {

            const skills =
                jobSkills.map(
                    skill =>
                        skill.toLowerCase()
                );

            if (
                skills.includes(
                    "fastapi"
                ) ||
                skills.includes(
                    "django"
                ) ||
                skills.includes(
                    "flask"
                )
            ) {
                return "Backend Developer";
            }

            if (
                skills.includes(
                    "react"
                ) ||
                skills.includes(
                    "html"
                ) ||
                skills.includes(
                    "css"
                )
            ) {
                return "Frontend Developer";
            }

            if (
                skills.includes(
                    "machine learning"
                ) ||
                skills.includes(
                    "scikit-learn"
                ) ||
                skills.includes(
                    "pandas"
                )
            ) {
                return "Data / ML Role";
            }

            return "Target Role";
        }

        // =================================================
        // PROJECT ANALYSIS
        // =================================================

        function createProjectAnalysis(
            result
        ) {

            const analyses =
                result.project_analysis || [];

            const recommendations =
                result.project_recommendations || [];

            if (!analyses.length) {

                return `
                    <div class="empty-state">
                        No project analysis available.
                    </div>
                `;
            }

            return `
                <section
                    id="projects-section"
                    class="dashboard-section project-analysis-section"
                >

                    <div
                        class="dashboard-section-header"
                    >

                        <div>

                            <div class="card-title">

                                <span class="card-icon">
                                    &loz;
                                </span>

                                Your Projects Analysis

                            </div>

                        </div>

                        <span class="section-action">
                            How to improve?
                        </span>

                    </div>

                    <div
                        class="project-results-grid"
                    >

                        ${analyses.map(
                            function (project) {

                                const projectRecommendations =
                                    recommendations.filter(
                                        recommendation =>
                                            recommendation.project ===
                                            project.name
                                    );

                                return `
                                    <article
                                        class="project-result-card"
                                    >

                                        <h4>
                                            ${escapeHTML(
                                                project.name
                                            )}
                                        </h4>

                                        <div
                                            class="project-skills"
                                        >

                                            ${
                                                (
                                                    project.skills ||
                                                    []
                                                )
                                                    .map(
                                                        skill => `
                                                            <span
                                                                class="skill-pill"
                                                            >
                                                                ${escapeHTML(
                                                                    skill
                                                                )}
                                                            </span>
                                                        `
                                                    )
                                                    .join("")
                                            }

                                        </div>

                                        <div
                                            class="project-upgrades"
                                        >

                                            ${
                                                projectRecommendations.length
                                                    ? projectRecommendations
                                                        .map(
                                                            createUpgradeItem
                                                        )
                                                        .join("")

                                                    : `
                                                        <div
                                                            class="upgrade-item"
                                                        >

                                                            <strong>
                                                                &#10003;
                                                                No upgrade needed
                                                            </strong>

                                                            <p>
                                                                This project does not currently
                                                                need a forced skill addition.
                                                            </p>

                                                        </div>
                                                    `
                                            }

                                        </div>

                                    </article>
                                `;
                            }
                        ).join("")}

                    </div>

                </section>
            `;
        }

        // =================================================
        // PROJECT RECOMMENDATION
        // =================================================

        function createUpgradeItem(
            recommendation
        ) {

            const compatibility =
                recommendation.compatibility ||
                "UNKNOWN";

            let compatibilityClass =
                "unknown";

            if (
                compatibility ===
                "HIGH"
            ) {
                compatibilityClass =
                    "high";
            }

            if (
                compatibility ===
                "ALREADY DEMONSTRATED"
            ) {
                compatibilityClass =
                    "already";
            }

            const upgrade =
                recommendation.upgrade;

            return `
                <div
                    class="upgrade-item"
                >

                    <div
                        class="upgrade-item-header"
                    >

                        <strong>
                            ${escapeHTML(
                                recommendation.skill
                            )}
                        </strong>

                        <span
                            class="compatibility ${compatibilityClass}"
                        >
                            ${escapeHTML(
                                compatibility
                            )}
                        </span>

                    </div>

                    <p>
                        ${escapeHTML(
                            recommendation.reason
                        )}
                    </p>

                    ${
                        upgrade
                            ? `
                                <div
                                    class="upgrade-action"
                                >
                                    &rarr;
                                    ${escapeHTML(
                                        upgrade
                                    )}
                                </div>
                            `
                            : compatibility ===
                              "ALREADY DEMONSTRATED"
                                ? `
                                    <div
                                        class="upgrade-action"
                                    >
                                        &#10003;
                                        Already demonstrated
                                    </div>
                                `
                                : ""
                    }

                </div>
            `;
        }

        // =================================================
        // LEARNING & GITHUB RESOURCES
        // =================================================

        function createCuratedCard(
            resource
        ) {

            const skill =
                resource.skill ||
                "Resource";

            const type =
                resource.type ||
                "Learning Resource";

            const title =
                resource.title ||
                `${skill} Resource`;

            const description =
                resource.description ||
                "A recommended learning resource.";

            const url =
                safeUrl(
                    resource.url
                );

            let metaText =
                "Free Resource";

            let actionText =
                "Open Resource";

            if (type === "Documentation") {
                metaText =
                    "Official Documentation";
                actionText =
                    "View Documentation";
            } else if (type === "Practice") {
                metaText =
                    "Hands-on Practice";
                actionText =
                    "Start Practice";
            } else if (
                type ===
                "YouTube Tutorial Search"
            ) {
                metaText =
                    "YouTube Search";
                actionText =
                    "Search YouTube";
            }

            return `
                <article
                    class="resource-card"
                >

                    <div
                        class="resource-card-header"
                    >

                        <span
                            class="resource-skill"
                        >
                            ${escapeHTML(
                                skill
                            )}
                        </span>

                        <span
                            class="resource-type-badge"
                        >
                            ${escapeHTML(
                                type
                            )}
                        </span>

                    </div>

                    <h4>
                        ${escapeHTML(
                            title
                        )}
                    </h4>

                    <p
                        class="resource-description"
                    >
                        ${escapeHTML(
                            description
                        )}
                    </p>

                    <div
                        class="resource-meta"
                    >

                        <span>
                            ${escapeHTML(
                                metaText
                            )}
                        </span>

                        <span>
                            Free
                        </span>

                    </div>

                    <a
                        class="resource-link"
                        href="${escapeHTML(
                            url
                        )}"
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        ${escapeHTML(
                            actionText
                        )}
                        &#8599;
                    </a>

                </article>
            `;
        }

        function createGitHubCard(
            resource
        ) {

            const repo =
                resource.repo || {};

            const skill =
                resource.skill ||
                "Resource";

            const name =
                repo.full_name ||
                "GitHub Repository";

            const description =
                repo.description ||
                "A relevant learning resource.";

            const stars =
                Number(
                    repo.stargazers_count ||
                    0
                );

            const url =
                safeUrl(
                    repo.html_url
                );

            return `
                <article
                    class="resource-card"
                >

                    <div
                        class="resource-card-header"
                    >

                        <span
                            class="resource-skill"
                        >
                            ${escapeHTML(
                                skill
                            )}
                        </span>

                        <span
                            class="resource-type-badge"
                        >
                            GitHub
                        </span>

                    </div>

                    <h4>
                        ${escapeHTML(
                            name
                        )}
                    </h4>

                    <p
                        class="resource-description"
                    >
                        ${escapeHTML(
                            description
                        )}
                    </p>

                    <div
                        class="resource-meta"
                    >

                        <span>
                            &#9733;
                            ${formatStars(
                                stars
                            )}
                        </span>

                        <span>
                            Relevance
                            ${Number(
                                resource.score ||
                                0
                            )}
                        </span>

                    </div>

                    <a
                        class="resource-link"
                        href="${escapeHTML(
                            url
                        )}"
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        View on GitHub
                        &#8599;
                    </a>

                </article>
            `;
        }

        function createResourceCarousel(
            options
        ) {

            const title =
                options.title ||
                "Resources";

            const icon =
                options.icon ||
                "&#9679;";

            const cards =
                Array.isArray(
                    options.cards
                )
                    ? options.cards
                    : [];

            if (!cards.length) {
                return "";
            }

            const subtitle =
                `${cards.length} ` +
                (
                    cards.length === 1
                        ? "resource"
                        : "resources"
                );

            return `
                <div class="resource-group">

                    <div
                        class="resource-group-header"
                    >

                        <div
                            class="resource-group-heading"
                        >

                            <span
                                class="resource-group-icon"
                            >
                                ${icon}
                            </span>

                            <div>

                                <div
                                    class="resource-group-title"
                                >
                                    ${escapeHTML(
                                        title
                                    )}
                                </div>

                                <div
                                    class="resource-group-subtitle"
                                >
                                    ${escapeHTML(
                                        subtitle
                                    )}
                                </div>

                            </div>

                        </div>

                        <div
                            class="resource-group-controls"
                        >

                            <button
                                type="button"
                                class="resource-carousel-button"
                                data-carousel-prev
                                aria-label="Scroll ${escapeHTML(
                                    title
                                )} left"
                            >
                                &#10094;
                            </button>

                            <button
                                type="button"
                                class="resource-carousel-button"
                                data-carousel-next
                                aria-label="Scroll ${escapeHTML(
                                    title
                                )} right"
                            >
                                &#10095;
                            </button>

                        </div>

                    </div>

                    <div
                        class="resource-carousel"
                        data-carousel
                        tabindex="0"
                        role="group"
                        aria-label="${escapeHTML(
                            title
                        )}"
                    >

                        ${cards.join("")}

                    </div>

                </div>
            `;
        }

        function createResources(
            result
        ) {

            const curated =
                Array.isArray(
                    result &&
                    result.curated_resources
                )
                    ? result.curated_resources
                    : [];

            const github =
                Array.isArray(
                    result &&
                    result.github_recommendations
                )
                    ? result.github_recommendations
                    : [];

            if (!curated.length && !github.length) {

                return `
                    <section
                        class="dashboard-section"
                    >

                        <div class="card-title">
                            Recommended Learning Resources
                        </div>

                        <div class="empty-state">
                            No resources found for the current gap.
                        </div>

                    </section>
                `;
            }

            const documentationCards =
                curated
                    .filter(
                        function (resource) {
                            return (
                                resource &&
                                resource.type ===
                                    "Documentation"
                            );
                        }
                    )
                    .map(
                        createCuratedCard
                    );

            const videoCards =
                curated
                    .filter(
                        function (resource) {
                            return (
                                resource &&
                                resource.type !==
                                    "Documentation"
                            );
                        }
                    )
                    .map(
                        createCuratedCard
                    );

            const githubCards =
                github.map(
                    createGitHubCard
                );

            const groups = [
                createResourceCarousel({
                    title:
                        "GitHub Projects",

                    icon:
                        "&#9733;",

                    cards:
                        githubCards
                }),

                createResourceCarousel({
                    title:
                        "Video Tutorials & Courses",

                    icon:
                        "&#9654;",

                    cards:
                        videoCards
                }),

                createResourceCarousel({
                    title:
                        "Official Documentation",

                    icon:
                        "&#128218;",

                    cards:
                        documentationCards
                })
            ].join("");

            return `
                <section
                    id="resources-section"
                    class="dashboard-section resources-section"
                >

                    <div
                        class="dashboard-section-header"
                    >

                        <div class="card-title">

                            <span class="card-icon">
                                &#9691;
                            </span>

                            Recommended Learning Resources

                        </div>

                        <span class="section-action">
                            Curated &amp; GitHub
                        </span>

                    </div>

                    <div class="resource-groups">

                        ${groups}

                    </div>

                </section>
            `;
        }

        // =================================================
        // RESOURCE CAROUSEL CONTROLS
        // =================================================

        function syncCarouselButtons(
            carousel
        ) {

            if (
                !carousel ||
                !carousel.classList
            ) {
                return;
            }

            const group =
                carousel.closest(
                    ".resource-group"
                );

            if (!group) {
                return;
            }

            const previousButton =
                group.querySelector(
                    "[data-carousel-prev]"
                );

            const nextButton =
                group.querySelector(
                    "[data-carousel-next]"
                );

            if (
                !previousButton ||
                !nextButton
            ) {
                return;
            }

            const maxScroll =
                carousel.scrollWidth -
                carousel.clientWidth;

            const position =
                Math.max(
                    0,
                    carousel.scrollLeft
                );

            const threshold = 2;

            const hasOverflow =
                maxScroll > threshold;

            const atStart =
                position <= threshold;

            const atEnd =
                position >=
                    maxScroll - threshold;

            previousButton.disabled =
                !hasOverflow || atStart;

            nextButton.disabled =
                !hasOverflow || atEnd;

            group.classList.toggle(
                "has-no-overflow",
                !hasOverflow
            );
        }

        function syncAllCarousels(
            root
        ) {

            const scope =
                root || document;

            scope
                .querySelectorAll(
                    "[data-carousel]"
                )
                .forEach(
                    syncCarouselButtons
                );
        }

        function scrollCarousel(
            carousel,
            direction
        ) {

            if (!carousel) {
                return;
            }

            const step =
                Math.max(
                    200,
                    Math.round(
                        carousel.clientWidth * 0.8
                    )
                );

            const target =
                carousel.scrollLeft +
                step * direction;

            if (
                typeof carousel.scrollTo ===
                    "function"
            ) {

                carousel.scrollTo({
                    left: target,
                    behavior: "smooth"
                });

            } else {
                carousel.scrollLeft =
                    target;
            }

            window.setTimeout(
                function () {
                    syncCarouselButtons(
                        carousel
                    );
                },
                400
            );
        }

        function initCarouselControls() {

            document.addEventListener(
                "click",
                function (event) {

                    const button =
                        event.target instanceof
                            Element
                            ? event.target.closest(
                                "[data-carousel-prev], [data-carousel-next]"
                            )
                            : null;

                    if (
                        !button ||
                        button.disabled
                    ) {
                        return;
                    }

                    const group =
                        button.closest(
                            ".resource-group"
                        );

                    if (!group) {
                        return;
                    }

                    const carousel =
                        group.querySelector(
                            "[data-carousel]"
                        );

                    if (!carousel) {
                        return;
                    }

                    event.preventDefault();

                    scrollCarousel(
                        carousel,
                        button.hasAttribute(
                            "data-carousel-next"
                        )
                            ? 1
                            : -1
                    );
                }
            );

            document.addEventListener(
                "scroll",
                function (event) {

                    const target =
                        event.target;

                    if (
                        !(target instanceof Element) ||
                        !target.hasAttribute(
                            "data-carousel"
                        )
                    ) {
                        return;
                    }

                    syncCarouselButtons(
                        target
                    );
                },
                true
            );

            window.addEventListener(
                "resize",
                function () {
                    syncAllCarousels();
                }
            );

            window.addEventListener(
                "load",
                function () {
                    syncAllCarousels();
                }
            );
        }

        // =================================================
        // FORMAT STARS
        // =================================================

        function formatStars(
            stars
        ) {

            if (stars >= 1000) {

                return (
                    (stars / 1000)
                        .toFixed(1)
                        .replace(
                            ".0",
                            ""
                        ) +
                    "k"
                );
            }

            return stars.toLocaleString();
        }

        // =================================================
        // NEXT STEPS
        // =================================================

        function createNextSteps(
            result
        ) {

            const priorities =
                result.skill_priorities || [];

            const missing =
                result.missing_skills || [];

            const steps = [];

            priorities.forEach(
                function (priority) {

                    if (
                        steps.length >= 4
                    ) {
                        return;
                    }

                    steps.push({
                        title:
                            `Learn ${priority.skill}`,

                        description:
                            priority.importance ===
                            "HIGH"
                                ? "High importance for your target role."
                                : "Build this skill as part of your gap."
                    });
                }
            );

            missing.forEach(
                function (skill) {

                    if (
                        steps.length >= 4
                    ) {
                        return;
                    }

                    const alreadyIncluded =
                        steps.some(
                            step =>
                                step.title
                                    .toLowerCase()
                                    .includes(
                                        skill.toLowerCase()
                                    )
                        );

                    if (!alreadyIncluded) {

                        steps.push({

                            title:
                                `Practice ${skill}`,

                            description:
                                "Strengthen the skill with a practical project."
                        });
                    }
                }
            );

            if (!steps.length) {

                steps.push({

                    title:
                        "Keep building",

                    description:
                        "Your current skill set already aligns well."
                });
            }

            return `
                <section
                    class="dashboard-section"
                >

                    <div class="card-title">

                        <span class="card-icon">
                            &rarr;
                        </span>

                        Next Steps

                    </div>

                    <div
                        class="next-steps"
                        style="margin-top: 23px;"
                    >

                        ${steps.map(
                            function (
                                step,
                                index
                            ) {

                                return `
                                    <div
                                        class="next-step"
                                    >

                                        <span
                                            class="next-number"
                                        >
                                            ${index + 1}
                                        </span>

                                        <div>

                                            <h4>
                                                ${escapeHTML(
                                                    step.title
                                                )}
                                            </h4>

                                            <p>
                                                ${escapeHTML(
                                                    step.description
                                                )}
                                            </p>

                                        </div>

                                    </div>
                                `;
                            }
                        ).join("")}

                    </div>

                </section>
            `;
        }

                // =================================================
        // AI CAREER ADVICE
        // =================================================

        function renderAdviceMarkdown(
            text
        ) {

            if (!text) {
                return "";
            }

            return escapeHTML(text)
                .split("\n")
                .map(
                    function (line) {

                        const formattedLine =
                            line.replace(
                                /\*\*(.*?)\*\*/g,
                                "<strong>$1</strong>"
                            );

                        if (
                            line.startsWith(
                                "### "
                            )
                        ) {

                            return (
                                "<h4>" +
                                formattedLine.slice(
                                    4
                                ) +
                                "</h4>"
                            );
                        }

                        if (
                            line.startsWith(
                                "## "
                            )
                        ) {

                            return (
                                "<h4>" +
                                formattedLine.slice(
                                    3
                                ) +
                                "</h4>"
                            );
                        }

                        if (
                            line.startsWith(
                                "* "
                            ) ||
                            line.startsWith(
                                "- "
                            )
                        ) {

                            return (
                                "<li>" +
                                formattedLine.slice(
                                    2
                                ) +
                                "</li>"
                            );
                        }

                        if (
                            /^\d+\. /.test(
                                line
                            )
                        ) {

                            return (
                                '<div class="advice-step">' +
                                formattedLine +
                                "</div>"
                            );
                        }

                        return formattedLine
                            ? "<p>" +
                              formattedLine +
                              "</p>"
                            : '<div class="advice-spacer"></div>';
                    }
                )
                .join("")
                .replace(
                    /(<li>.*?<\/li>)+/g,
                    "<ul>$&</ul>"
                );
        }

        function createAICareerAdvice(
            result
        ) {

// The advisor stores plain text. Blank or non-text values carry no
            // advice. A recorded advisor failure is reported inside the
            // section instead of making the section disappear silently.
            const advice =
                typeof result.ai_advice ===
                    "string"
                    ? result.ai_advice.trim()
                    : "";

            const unavailable =
                typeof result.ai_advice_error ===
                    "string"
                    ? result.ai_advice_error.trim()
                    : "";

            if (!advice && !unavailable) {
                return "";
            }

            return `
                <section
                    id="ai-advice-section"
                    class="dashboard-section ai-advice-section"
                >

                    <div
                        class="dashboard-section-header"
                    >

                        <div class="card-title">

                            <span class="card-icon">
                                &#10022;
                            </span>

                            AI Career Advice

                        </div>

                        <span class="section-action">
                            CareerGap Advisor
                        </span>

                    </div>

                    <div
                        class="ai-advice-content"
                    >
                        ${
                            advice
                                ? renderAdviceMarkdown(
                                    advice
                                )
                                : `
                                    <div class="empty-state">
                                        ${escapeHTML(
                                            unavailable
                                        )}
                                    </div>
                                `
                        }
                    </div>

                </section>
            `;
        }

        // =================================================
        // ANALYSIS VIEW
        // =================================================

        function setAnalysisView(view) {

    const showHistoryArea =
        view === "history" ||
        view === "saved";

    // The current results panel is only revealed once a report has
    // actually been rendered into it. Showing it empty leaves a bare
    // background band on the initial Analyze screen.
    const hasCurrentReport =
        view === "current" &&
        resultsContent &&
        resultsContent.children.length > 0;

    if (resultsSection) {
        resultsSection.classList.toggle(
            "hidden",
            !hasCurrentReport
        );
    }

    if (analysisHistorySection) {
        analysisHistorySection.classList.toggle(
            "hidden",
            !showHistoryArea
        );
    }

    if (savedAnalysisSection) {
        savedAnalysisSection.classList.toggle(
            "hidden",
            view !== "saved"
        );
    }

    if (currentAnalysisTab) {
        currentAnalysisTab.classList.toggle(
            "active",
            view === "current"
        );
    }

    if (historyTab) {
        historyTab.classList.toggle(
            "active",
            view === "history"
        );
    }

    if (savedAnalysisTab) {
        savedAnalysisTab.classList.toggle(
            "active",
            view === "saved"
        );
    }

    syncSubnavState();
}

        // =================================================
        // BUILD COMPLETE DASHBOARD
        // =================================================

        function buildAnalysisMarkup(
            result
        ) {

            const top = `
                <div
                    id="overview-section"
                    class="dashboard-top"
                >

                    ${createScoreCard(
                        result
                    )}

                    ${createSkillBreakdown(
                        result
                    )}

                    ${createRoleInsights(
                        result
                    )}

                </div>
            `;

            const projects =
                createProjectAnalysis(
                    result
                );

            const resources =
                createResources(
                    result
                );

            const nextSteps =
                createNextSteps(
                    result
                );

            const aiAdvice =
                createAICareerAdvice(
                    result
                );

            const atsKeywords =
                createAtsKeywords(
                    result
                );

            return (
                top +
                projects +
                atsKeywords +
                aiAdvice +
                `
                    <div
                        class="dashboard-bottom"
                    >

                        <div>
                            ${resources}
                        </div>

                        <div>
                            ${nextSteps}
                        </div>

                    </div>
                `
            );
        }

        // =================================================
        // CURRENT ANALYSIS
        // =================================================

        function displayResults(
            result
        ) {

            resultsContent.innerHTML =
                buildAnalysisMarkup(
                    result
                );

            syncSubnavState();

            setActiveWorkspace(
                activeWorkspace
            );

            window.requestAnimationFrame(
                function () {
                    syncAllCarousels();
                }
            );

            resultsSection.classList.remove(
                "hidden"
            );

            loadingSection.classList.add(
                "hidden"
            );

            resultsSection.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }

        // =================================================
        // SAVED ANALYSIS
        // =================================================

        function normalizeSavedAnalysis(
            value
        ) {

            let result = value;

            if (
                typeof result ===
                "string"
            ) {

                try {

                    result =
                        JSON.parse(
                            result
                        );

                } catch (error) {

                    console.error(
                        "Saved analysis JSON parse error:",
                        error
                    );

                    return null;
                }
            }

            if (
                result &&
                typeof result ===
                    "object" &&
                result.analysis &&
                typeof result.analysis ===
                    "object" &&
                result.score ===
                    undefined
            ) {

                result =
                    result.analysis;
            }

            return result;
        }

        async function displaySavedAnalysis(
    savedAnalysis,
    savedJobDescription
) {

    const result =
        normalizeSavedAnalysis(
            savedAnalysis
        );

    if (
        !result ||
        typeof result !== "object"
    ) {
        savedResultsContent.innerHTML = `
            <div class="empty-state">
                Unable to display this saved analysis.
            </div>
        `;

        savedAnalysisSection.classList.remove(
            "hidden"
        );

        savedResultsContent.classList.remove(
            "hidden"
        );

        return;
    }

    // ATS keywords are attached client-side after /analyze and are
    // never written to the stored analysis, so every saved row is
    // missing them. Recompute them from the saved job description
    // with the same endpoint the live analysis uses. That endpoint
    // validates the whole request body but reads only
    // job_description, so the resume and project placeholders below
    // never influence the extracted keywords.
    if (
        !Array.isArray(result.ats_keywords) ||
        !result.ats_keywords.length
    ) {

        const jobDescription =
            typeof savedJobDescription ===
                "string"
                ? savedJobDescription.trim()
                : "";

        if (jobDescription) {

            const keywords =
                await fetchAtsKeywords({
                    resume:
                        "Saved analysis",
                    job_description:
                        jobDescription,
                    projects: [
                        {
                            name:
                                "Saved analysis",
                            description:
                                "Saved analysis"
                        }
                    ]
                });

            if (keywords) {
                result.ats_keywords =
                    keywords;
            }

        }

    }

    savedResultsContent.innerHTML = `
        <div class="saved-analysis-header">
            <div>
                <p class="eyebrow">
                    SAVED ANALYSIS
                </p>

                <h2>
                    Previous CareerGap Analysis
                </h2>

                <p>
                    You are viewing a saved analysis.
                </p>
            </div>
        </div>

        ${buildAnalysisMarkup(result)}
    `;

    window.requestAnimationFrame(
        function () {
            syncAllCarousels();
        }
    );

    savedResultsContent.classList.remove(
        "hidden"
    );

    savedAnalysisSection.classList.remove(
        "hidden"
    );

    syncSubnavState();

    savedAnalysisSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}

        // =================================================
        // HISTORY BUTTONS
        // =================================================

        if (analysisHistoryList) {

            analysisHistoryList.addEventListener(
                "click",
                async function (event) {

                    // -------------------------------------
                    // VIEW SAVED ANALYSIS
                    // -------------------------------------

                    const viewButton =
                        event.target.closest(
                            ".history-view-button"
                        );

                    if (viewButton) {

                        const index =
                            Number(
                                viewButton.dataset
                                    .historyIndex
                            );

                        const savedAnalysis =
                            analysisHistoryData[
                                index
                            ];

                        if (!savedAnalysis) {

                            console.error(
                                "Saved analysis not found:",
                                index
                            );

                            return;
                        }

                        console.log(
                            "Opening saved analysis:",
                            savedAnalysis
                        );

                        await displaySavedAnalysis(
                            savedAnalysis.analysis,
                            savedAnalysis.job_description
                        );

                        setAnalysisView(
                            "saved"
                        );

                        return;
                    }

                    // -------------------------------------
                    // DELETE SAVED ANALYSIS
                    // -------------------------------------

                    const deleteButton =
                        event.target.closest(
                            ".history-delete-button"
                        );

                    if (!deleteButton) {
                        return;
                    }

                    const index =
                        Number(
                            deleteButton.dataset
                                .historyIndex
                        );

                    const savedAnalysis =
                        analysisHistoryData[
                            index
                        ];

                    if (!savedAnalysis) {

                        console.error(
                            "Analysis to delete not found:",
                            index
                        );

                        return;
                    }

                    const analysisId =
                        savedAnalysis.id;

                    if (!analysisId) {

                        alert(
                            "Unable to delete this analysis."
                        );

                        return;
                    }

                    const confirmed =
                        window.confirm(
                            "Delete this analysis? This cannot be undone."
                        );

                    if (!confirmed) {
                        return;
                    }

                    deleteButton.disabled =
                        true;

                    deleteButton.textContent =
                        "…";

                    try {

                        const accessToken =
                            await getAccessToken();

                        if (!accessToken) {
                            return;
                        }

                        const response =
                            await fetch(
                                `${API_BASE_URL}/analyses/${encodeURIComponent(
                                    analysisId
                                )}`,
                                {
                                    method:
                                        "DELETE",

                                    headers: {
                                        Authorization:
                                            `Bearer ${accessToken}`
                                    }
                                }
                            );

                        if (!response.ok) {

                            let message =
                                "Unable to delete this analysis.";

                            try {

                                const error =
                                    await response.json();

                                message =
                                    error.detail ||
                                    message;

                            } catch (_) {
                                // Keep default message.
                            }

                            throw new Error(
                                message
                            );
                        }

                        analysisHistoryData =
                            analysisHistoryData.filter(
                                function (item) {

                                    return (
                                        String(
                                            item.id
                                        ) !==
                                        String(
                                            analysisId
                                        )
                                    );
                                }
                            );

                        setAnalysisView(
                            "history"
                        );

                        await loadAnalysisHistory();

                    } catch (error) {

                        console.error(
                            "Delete analysis error:",
                            error
                        );

                        alert(
                            error.message ||
                            "Unable to delete this analysis."
                        );

                        deleteButton.disabled =
                            false;

                        deleteButton.textContent =
                            "×";
                    }
                }
            );
        }

        // =================================================
        // TAB BUTTONS
        // =================================================

        if (currentAnalysisTab) {

            currentAnalysisTab.addEventListener(
                "click",
                function () {

                    if (
                        activeWorkspace ===
                        "resume-builder"
                    ) {
                        return;
                    }

                    if (!currentAnalysis) {
                        return;
                    }

                    setAnalysisView(
                        "current"
                    );
                }
            );
        }

        if (historyTab) {

            historyTab.addEventListener(
                "click",
                function () {

                    if (
                        activeWorkspace ===
                        "resume-builder"
                    ) {
                        return;
                    }

                    setAnalysisView(
                        "history"
                    );

                    loadAnalysisHistory();

                }
            );
        }

        if (savedAnalysisTab) {

            savedAnalysisTab.addEventListener(
                "click",
                function () {

                    if (
                        activeWorkspace ===
                        "resume-builder"
                    ) {
                        return;
                    }

                    if (
                        savedResultsContent &&
                        savedResultsContent.innerHTML
                    ) {

                        setAnalysisView(
                            "saved"
                        );
                    }
                }
            );
        }

        // =================================================
        // ANALYZE
        // =================================================

        analyzeButton.addEventListener(
            "click",
            async function () {

                const data =
                    collectCareerGapData();

                if (!data.resume) {

                    alert(
                        "Please enter your resume or upload a resume file."
                    );

                    return;
                }

                if (!data.job_description) {

                    alert(
                        "Please enter the target job description or upload a job description file."
                    );

                    return;
                }

                const invalidProject =
                    data.projects.some(
                        project =>
                            !project.name ||
                            !project.description
                    );

                if (invalidProject) {

                    alert(
                        "Please complete every project name and description."
                    );

                    return;
                }

                console.log(
                    "Sending data to CareerGap API:"
                );

                console.log(data);

                analyzeButton.disabled =
                    true;

                analyzeButton.innerHTML =
                    "Analyzing...";

                resultsSection.classList.add(
                    "hidden"
                );

                loadingSection.classList.remove(
                    "hidden"
                );

                loadingSection.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });

                syncSubnavState();

                try {

                    const result =
                        await analyzeCareerGap(
                            data
                        );

                    console.log(
                        "CareerGap API Response:"
                    );

                    console.log(result);

                    currentAnalysis =
                        result;

                    if (
                        currentAnalysisTab
                    ) {

                        currentAnalysisTab.disabled =
                            false;
                    }

                    displayResults(
                        result
                    );

                    setAnalysisView(
                        "current"
                    );

                } catch (error) {

                    console.error(
                        "CareerGap Error:",
                        error
                    );

                    loadingSection.classList.add(
                        "hidden"
                    );

                    resultsSection.classList.remove(
                        "hidden"
                    );

                    resultsContent.innerHTML = `
                        <div
                            class="result-error"
                        >

                            <h3>
                                Something went wrong.
                            </h3>

                            <p>
                                ${escapeHTML(
                                    error.message
                                )}
                            </p>

                        </div>
                    `;

                    syncSubnavState();

                } finally {

                    analyzeButton.disabled =
                        false;

                    analyzeButton.innerHTML =
                        `
                            Analyze My Career Gap
                            <span>&rarr;</span>
                        `;
                }
            }
        );

        // =================================================
        // INITIALIZE
        // =================================================

        if (currentAnalysisTab) {
            currentAnalysisTab.disabled = true;
        }

        initCarouselControls();

        loadAnalysisHistory();

        setActiveWorkspace(
            "analyze"
        );


        window.setTimeout(
            syncStickyOffsets,
            200
        );
        // =========================================================
        // RESUME BUILDER
        // =========================================================

        let resumeBuilderState = {
            resumes: [],
            selectedResumeId: null,
            selectedResume: null,
            viewMode: "empty",
        };

        // Holds the custom section-type dropdown controller
        // created by setupSectionTypeSelect().
        let sectionTypeSelect = null;

        const resumeElements = {
            list: document.getElementById("resume-list"),
            empty: document.getElementById("resume-list-empty"),
            loading: document.getElementById("resume-list-loading"),
            error: document.getElementById("resume-list-error"),
            createBtn: document.getElementById("create-resume-btn"),
            view: document.getElementById("resume-view"),
            viewTitle: document.getElementById("resume-view-title"),
            preview: document.getElementById("resume-preview"),
            setDefaultBtn: document.getElementById("resume-set-default-btn"),
            editBtn: document.getElementById("resume-edit-btn"),
            deleteBtn: document.getElementById("resume-delete-btn"),
            exportBtn: document.getElementById("resume-export-btn"),
            editor: document.getElementById("resume-editor"),
            editorEmpty: document.getElementById("resume-editor-empty"),
            cancelBtn: document.getElementById("resume-cancel-btn"),
            saveBtn: document.getElementById("resume-save-btn"),
            form: document.getElementById("resume-form"),
            formId: document.getElementById("resume-form-id"),
            formIsDefault: document.getElementById("resume-form-is-default"),
            editorError: document.getElementById("resume-editor-error"),
            addSectionBtn: document.getElementById("add-section-btn"),
            sectionsContainer: document.getElementById("resume-sections-container"),
            linksContainer: document.getElementById("contact-links-container"),
            addLinkBtn: document.getElementById("add-link-btn"),
            summaryTextarea: document.getElementById("resume-summary"),
            summaryCount: document.getElementById("summary-count"),
            titleInput: document.getElementById("resume-title"),
            titleCount: document.getElementById("title-count"),
        };

        async function apiRequest(path, options = {}, redirectIfMissing = true) {
            const accessToken = await getAccessToken(redirectIfMissing);

            // A missing session must never look like a successful call. Returning
            // null here would let delete and set-default drop the resume from
            // local state while the server still had it.
            if (!accessToken) {
                throw new Error("You need to sign in to manage resumes.");
            }

            const response = await fetch(`${API_BASE_URL}${path}`, {
                ...options,
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${accessToken}`,
                    ...options.headers,
                },
            });

            if (!response.ok) {
                let message = "Request failed.";
                try {
                    const error = await response.json();
                    message = error.detail || message;
                } catch (_) {}
                throw new Error(message);
            }

            // DELETE /resumes/{id} answers 204 with no body, so there is nothing
            // to parse. Calling json() on it throws a misleading SyntaxError.
            if (response.status === 204) {
                return null;
            }

            return response.json();
        }

        async function loadResumes() {
            resumeElements.loading.classList.remove("hidden");
            resumeElements.list.classList.add("hidden");
            resumeElements.empty.classList.add("hidden");
            resumeElements.error.classList.add("hidden");

            try {
                // A list load must not force a login redirect, the same way
                // loadAnalysisHistory reads the session without redirecting.
                // Without a session the panel is left in its loading state
                // rather than claiming the user has no resumes.
                const data = await apiRequest("/resumes?limit=50", {}, false);

                if (!data) {
                    resumeElements.loading.classList.add("hidden");
                    return;
                }

                resumeBuilderState.resumes = Array.isArray(data) ? data : [];
                renderResumeList();
            } catch (error) {
                console.error("Load resumes error:", error);
                resumeElements.loading.classList.add("hidden");
                resumeElements.error.textContent = escapeHTML(error.message);
                resumeElements.error.classList.remove("hidden");
            }
        }

        function renderResumeList() {
            resumeElements.loading.classList.add("hidden");

            if (!resumeBuilderState.resumes.length) {
                resumeElements.list.classList.add("hidden");
                resumeElements.empty.classList.remove("hidden");
                return;
            }

            resumeElements.empty.classList.add("hidden");
            resumeElements.error.classList.add("hidden");
            resumeElements.list.classList.remove("hidden");

            resumeElements.list.innerHTML = resumeBuilderState.resumes
                .map((resume) => {
                    const isDefault = resume.is_default === true;
                    const updatedDate = resume.updated_at
                        ? new Date(resume.updated_at).toLocaleDateString(undefined, {
                              day: "numeric",
                              month: "short",
                              year: "numeric",
                          })
                        : "";
                    const isActive = resume.id === resumeBuilderState.selectedResumeId;

                    return `
                        <button
                            type="button"
                            class="resume-list-item${isActive ? " active" : ""}"
                            data-resume-id="${escapeHTML(resume.id)}"
                            aria-pressed="${isActive}"
                        >
                            <div class="resume-list-item-main">
                                <span class="resume-list-item-title">${escapeHTML(resume.title)}</span>
                                <div class="resume-list-item-meta">
                                    ${isDefault ? '<span class="resume-list-item-badge default">Default</span>' : ""}
                                    ${updatedDate ? `<span class="resume-list-item-badge updated">${escapeHTML(updatedDate)}</span>` : ""}
                                </div>
                            </div>
                        </button>
                    `;
                })
                .join("");

            resumeElements.list.querySelectorAll(".resume-list-item").forEach((item) => {
                item.addEventListener("click", () => {
                    const resumeId = item.dataset.resumeId;
                    selectResume(resumeId);
                });
            });
        }

        // GET /resumes returns summaries only (id, title, is_default, created_at,
        // updated_at). The document itself has to be read from GET /resumes/{id}.
        // Editing or previewing from a summary row would show an empty resume and
        // saving that back would overwrite the stored document with nothing.
        async function fetchResumeDetail(resumeId) {
            return await apiRequest(
                `/resumes/${encodeURIComponent(resumeId)}`
            );
        }

        async function selectResume(resumeId) {
            const summary = resumeBuilderState.resumes.find((r) => r.id === resumeId);
            if (!summary) {
                return;
            }

            resumeBuilderState.selectedResumeId = resumeId;
            resumeBuilderState.viewMode = "view";
            updateViewMode();

            resumeElements.preview.innerHTML =
                '<div class="resume-loading"><div class="loading-orbit-small"></div><p>Loading...</p></div>';

            try {
                const resume = await fetchResumeDetail(resumeId);

                if (resumeBuilderState.selectedResumeId !== resumeId) {
                    return;
                }

                resumeBuilderState.selectedResume = resume;
                renderResumePreview(resume);
                renderResumeList();
            } catch (error) {
                console.error("Load resume error:", error);
                resumeElements.preview.innerHTML = `
                    <div class="resume-editor-error">
                        ${escapeHTML(error.message)}
                    </div>
                `;
            }
        }

        function updateViewMode() {
            const { view, editor, editorEmpty } = resumeElements;

            const onView =
                resumeBuilderState.viewMode === "view";

            const onEditor =
                resumeBuilderState.viewMode === "edit";

            // The view panel starts hidden through the `hidden` attribute while
            // the editor starts hidden through the `hidden` class. Both have to
            // be cleared, otherwise the panel stays display:none either way.
            view.classList.toggle("hidden", !onView);
            view.hidden = !onView;

            editor.classList.toggle("hidden", !onEditor);
            editorEmpty.classList.toggle("hidden", onView || onEditor);
        }

        function renderResumePreview(resume) {
            resumeElements.viewTitle.textContent = escapeHTML(resume.title);
            resumeElements.setDefaultBtn.setAttribute(
                "aria-pressed",
                resume.is_default === true ? "true" : "false"
            );

            const content = resume.content || {};
            const contact = content.contact || {};
            const summary = content.summary || "";
            const sections = content.sections || [];

            let previewHtml = "";

            if (Object.keys(contact).length) {
                previewHtml += `
                    <div class="resume-preview-section">
                        <div class="resume-preview-section-title">Contact</div>
                        <div class="resume-preview-contact">
                            ${contact.full_name ? `<span class="resume-preview-contact-item"><span class="resume-preview-contact-label">Name</span>${escapeHTML(contact.full_name)}</span>` : ""}
                            ${contact.email ? `<span class="resume-preview-contact-item"><span class="resume-preview-contact-label">Email</span>${escapeHTML(contact.email)}</span>` : ""}
                            ${contact.phone ? `<span class="resume-preview-contact-item"><span class="resume-preview-contact-label">Phone</span>${escapeHTML(contact.phone)}</span>` : ""}
                            ${contact.location ? `<span class="resume-preview-contact-item"><span class="resume-preview-contact-label">Location</span>${escapeHTML(contact.location)}</span>` : ""}
                        </div>
                        ${contact.links && contact.links.length ? `
                            <div class="resume-preview-links">
                                ${contact.links.map(link => `<a class="resume-preview-link" href="${safeUrl(link.url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(link.label)}</a>`).join("")}
                            </div>
                        ` : ""}
                    </div>
                `;
            }

            if (summary) {
                previewHtml += `
                    <div class="resume-preview-section">
                        <div class="resume-preview-section-title">Professional Summary</div>
                        <div class="resume-preview-summary">${escapeHTML(summary)}</div>
                    </div>
                `;
            }

            if (sections.length) {
                sections.forEach((section) => {
                    previewHtml += renderPreviewSection(section);
                });
            }

            if (!previewHtml) {
                previewHtml = '<div class="empty-state">This resume is empty. Click Edit to add content.</div>';
            }

            resumeElements.preview.innerHTML = previewHtml;
        }

        function renderPreviewSection(section) {
            // The heading is what the user typed and is what the API stores, so
            // it wins over the built-in label for the section title.
            const heading =
                typeof section.heading === "string" && section.heading.trim()
                    ? section.heading.trim()
                    : RESUME_SECTION_HEADINGS[section.type] ||
                      section.type;

            const items = Array.isArray(section.items) ? section.items : [];

            if (section.type === "skills") {
                const skills = items
                    .filter(
                        (skill) =>
                            typeof skill === "string" && skill.trim()
                    )
                    .map((skill) => skill.trim());

                if (!skills.length) {
                    return "";
                }

                const groups = _groupSkillsByCategory(skills);

                return `
                    <div class="resume-preview-section">
                        <div class="resume-preview-section-title">${escapeHTML(heading)}</div>
                        <div class="resume-preview-skills">
                            ${groups
                                .map((group) => `
                                    <div class="resume-preview-skill-group">
                                        <span class="resume-preview-skill-category">${escapeHTML(group.category)}</span>
                                        ${group.skills
                                            .map(
                                                (skill) =>
                                                    `<span class="resume-preview-skill">${escapeHTML(skill)}</span>`
                                            )
                                            .join("")}
                                    </div>
                                `)
                                .join("")}
                        </div>
                    </div>
                `;
            }

            if (!items.length && !section.text) {
                return "";
            }

            const entries = items
                .map((item) => {
                    const data =
                        item && typeof item === "object" ? item : {};

                    const metaParts = [];

                    if (data.location) {
                        metaParts.push(data.location);
                    }

                    if (data.start) {
                        metaParts.push(
                            data.end
                                ? `${data.start} - ${data.end}`
                                : data.start
                        );
                    }

                    const bullets = Array.isArray(data.bullets)
                        ? data.bullets.filter(Boolean)
                        : [];

                    return `
                        <div class="resume-preview-item">
                            ${
                                data.title || data.organization
                                    ? `
                                        <div class="resume-preview-item-header">
                                            <div>
                                                ${
                                                    data.title
                                                        ? `<div class="resume-preview-item-title">${escapeHTML(data.title)}</div>`
                                                        : ""
                                                }
                                                ${
                                                    data.organization
                                                        ? `<div class="resume-preview-item-subtitle">${escapeHTML(data.organization)}</div>`
                                                        : ""
                                                }
                                            </div>
                                            ${
                                                data.url
                                                    ? `<a class="resume-preview-link" href="${escapeHTML(safeUrl(data.url))}" target="_blank" rel="noopener noreferrer">Link</a>`
                                                    : ""
                                            }
                                        </div>
                                    `
                                    : ""
                            }

                            ${
                                metaParts.length
                                    ? `<div class="resume-preview-item-meta">${escapeHTML(metaParts.join(" · "))}</div>`
                                    : ""
                            }

                            ${
                                data.text
                                    ? `<div class="resume-preview-summary">${escapeHTML(data.text)}</div>`
                                    : ""
                            }

                            ${
                                bullets.length
                                    ? `
                                        <ul class="resume-preview-item-bullets">
                                            ${bullets
                                                .map(
                                                    (bullet) =>
                                                        `<li>${escapeHTML(bullet)}</li>`
                                                )
                                                .join("")}
                                        </ul>
                                    `
                                    : ""
                            }
                        </div>
                    `;
                })
                .join("");

            return `
                <div class="resume-preview-section">
                    <div class="resume-preview-section-title">${escapeHTML(heading)}</div>

                    ${
                        section.text
                            ? `<div class="resume-preview-summary">${escapeHTML(section.text)}</div>`
                            : ""
                    }

                    ${
                        entries
                            ? `<div class="resume-preview-section-content">${entries}</div>`
                            : ""
                    }
                </div>
            `;
        }

        function createResume() {
            resumeBuilderState.selectedResumeId = null;
            resumeBuilderState.selectedResume = null;
            resumeBuilderState.viewMode = "edit";
            updateViewMode();
            resetEditorForm();
            renderResumeList();
        }

        function resetEditorForm() {
            resumeElements.form.reset();
            autoGrowTextarea(resumeElements.summaryTextarea);
            resumeElements.formId.value = "";
            resumeElements.formIsDefault.value = "false";
            resumeElements.linksContainer.innerHTML = "";
            resumeElements.sectionsContainer.innerHTML = "";
            resumeElements.editorError.classList.add("hidden");
            resumeElements.editorError.textContent = "";
            updateSummaryCount();
            updateTitleCount();
            updateAddSectionButton();
        }

        function populateEditorForm(resume) {
            const content = resume.content || {};
            const contact = content.contact || {};
            const summary = content.summary || "";
            const sections = content.sections || [];

            resumeElements.formId.value = resume.id;
            resumeElements.formIsDefault.value = resume.is_default === true ? "true" : "false";

            resumeElements.titleInput.value = resume.title || "";
            updateTitleCount();

            document.getElementById("contact-full_name").value = contact.full_name || "";
            document.getElementById("contact-email").value = contact.email || "";
            document.getElementById("contact-phone").value = contact.phone || "";
            document.getElementById("contact-location").value = contact.location || "";

            resumeElements.linksContainer.innerHTML = "";
            (contact.links || []).forEach((link) => addLinkRow(link.label, link.url));

            resumeElements.summaryTextarea.value = summary;
            autoGrowTextarea(resumeElements.summaryTextarea);
            updateSummaryCount();

            resumeElements.sectionsContainer.innerHTML = "";
            sections.forEach((section) => addSectionItem(section));
        }

        async function editResume() {
            if (!resumeBuilderState.selectedResumeId) {
                return;
            }

            try {
                const resume = await fetchResumeDetail(
                    resumeBuilderState.selectedResumeId
                );

                if (resumeBuilderState.selectedResumeId !== resume.id) {
                    return;
                }

                resumeBuilderState.selectedResume = resume;
                resumeBuilderState.viewMode = "edit";
                updateViewMode();
                populateEditorForm(resume);
            } catch (error) {
                console.error("Open resume for editing error:", error);
                resumeElements.editorError.textContent =
                    escapeHTML(error.message);
                resumeElements.editorError.classList.remove("hidden");
            }
        }

        async function saveResume() {
            const formData = new FormData(resumeElements.form);
            const isDefault = formData.get("is_default") === "true";
            const resumeId = formData.get("id");

            const contact = {
                full_name: formData.get("contact.full_name") || "",
                email: formData.get("contact.email") || "",
                phone: formData.get("contact.phone") || "",
                location: formData.get("contact.location") || "",
                links: [],
            };

            resumeElements.linksContainer.querySelectorAll(".resume-link-row").forEach((row) => {
                const label = row.querySelector('[name="contact.links[].label"]').value.trim();
                const url = row.querySelector('[name="contact.links[].url"]').value.trim();
                if (label || url) {
                    contact.links.push({ label, url });
                }
            });

            const summary = formData.get("summary") || "";

            const sections = [];

            resumeElements.sectionsContainer
                .querySelectorAll(".resume-section-item")
                .forEach((item) => {
                    const type = item.dataset.sectionType;

                    const headingInput =
                        item.querySelector('[name="heading"]');

                    const sectionData = {
                        type,
                        heading: headingInput
                            ? headingInput.value.trim()
                            : "",
                        text: "",
                        items: [],
                    };

                    if (type === "skills") {
                        // Skills are stored as plain strings.
                        const skills = Array.from(
                            item.querySelectorAll(
                                'input[name="skill[]"]'
                            )
                        )
                            .map((input) => input.value.trim())
                            .filter(Boolean);

                        sectionData.items = skills;

                        if (
                            sectionData.heading ||
                            sectionData.items.length
                        ) {
                            sections.push(sectionData);
                        }

                        return;
                    }

                    item.querySelectorAll(
                        ".resume-section-fields-item"
                    ).forEach((entry) => {
                        const entryData = {};

                        entry
                            .querySelectorAll(
                                ".resume-field input, .resume-field textarea"
                            )
                            .forEach((input) => {
                                const value = input.value.trim();

                                if (value) {
                                    entryData[input.name] = value;
                                }
                            });

                        const bullets = Array.from(
                            entry.querySelectorAll(
                                '.resume-bullet-row input[name="bullets[]"]'
                            )
                        )
                            .map((input) => input.value.trim())
                            .filter(Boolean);

                        if (bullets.length) {
                            entryData.bullets = bullets;
                        }

                        if (Object.keys(entryData).length) {
                            sectionData.items.push(entryData);
                        }
                    });

                    if (
                        sectionData.heading ||
                        sectionData.items.length
                    ) {
                        sections.push(sectionData);
                    }
                });

            const title = resumeElements.titleInput.value.trim();

            const payload = {
                title: title || "Untitled Resume",
                content: { contact, summary, sections },
                is_default: isDefault,
            };

            resumeElements.saveBtn.disabled = true;
            resumeElements.saveBtn.textContent = "Saving...";
            resumeElements.editorError.classList.add("hidden");

            try {
                let savedResume;
                if (resumeId) {
                    savedResume = await apiRequest(`/resumes/${encodeURIComponent(resumeId)}`, {
                        method: "PUT",
                        body: JSON.stringify(payload),
                    });
                } else {
                    savedResume = await apiRequest("/resumes", {
                        method: "POST",
                        body: JSON.stringify(payload),
                    });
                }

                await loadResumes();

                // Re-read the stored resume so the preview reflects what
                // the API normalized and saved, not what was typed.
                await selectResume(savedResume.id);
            } catch (error) {
                console.error("Save resume error:", error);
                resumeElements.editorError.textContent = escapeHTML(error.message);
                resumeElements.editorError.classList.remove("hidden");
            } finally {
                resumeElements.saveBtn.disabled = false;
                resumeElements.saveBtn.textContent = "Save";
            }
        }

        function cancelEdit() {
            const selected = resumeBuilderState.selectedResume;

            // Re-render from the fetched detail, not the summary row, so the
            // preview does not collapse to an empty resume on cancel.
            if (resumeBuilderState.selectedResumeId && selected) {
                resumeBuilderState.viewMode = "view";
                renderResumePreview(selected);
            } else {
                resumeBuilderState.viewMode = "empty";
            }

            updateViewMode();
            resetEditorForm();
            renderResumeList();
        }

        async function deleteResume() {
            if (!resumeBuilderState.selectedResumeId) {
                return;
            }

            const confirmed = window.confirm("Delete this resume? This cannot be undone.");
            if (!confirmed) {
                return;
            }

            const resumeId = resumeBuilderState.selectedResumeId;
            resumeElements.deleteBtn.disabled = true;
            resumeElements.deleteBtn.textContent = "…";

            try {
                await apiRequest(`/resumes/${encodeURIComponent(resumeId)}`, {
                    method: "DELETE",
                });

                resumeBuilderState.resumes = resumeBuilderState.resumes.filter((r) => r.id !== resumeId);
                resumeBuilderState.selectedResumeId = null;
                resumeBuilderState.selectedResume = null;
                resumeBuilderState.viewMode = "empty";
                updateViewMode();
                await loadResumes();
            } catch (error) {
                console.error("Delete resume error:", error);
                alert(error.message || "Unable to delete resume.");
            } finally {
                resumeElements.deleteBtn.disabled = false;
                resumeElements.deleteBtn.textContent = "Delete";
            }
        }

        async function setDefaultResume() {
            if (!resumeBuilderState.selectedResumeId) {
                return;
            }

            const resumeId = resumeBuilderState.selectedResumeId;

            // PUT replaces the whole document, and the summary rows in the list
            // carry no content. Sending one would be rejected as an empty write
            // and would overwrite the stored resume, so the full record is read
            // first and sent back unchanged apart from the default flag.
            try {
                const current = await fetchResumeDetail(resumeId);

                const updated = await apiRequest(`/resumes/${encodeURIComponent(resumeId)}`, {
                    method: "PUT",
                    body: JSON.stringify({
                        title: current.title,
                        content: current.content || {},
                        is_default: true,
                    }),
                });

                resumeBuilderState.selectedResume = updated;
                resumeBuilderState.resumes = resumeBuilderState.resumes.map((r) =>
                    r.id === resumeId ? { ...r, is_default: true } : { ...r, is_default: false }
                );
                renderResumeList();
                renderResumePreview(updated);
            } catch (error) {
                console.error("Set default error:", error);
                alert(error.message || "Unable to set as default.");
            }
        }

        async function exportResume() {
            if (!resumeBuilderState.selectedResumeId) {
                return;
            }

            const exportBtn = resumeElements.exportBtn;
            const originalText = exportBtn.textContent;
            exportBtn.disabled = true;
            exportBtn.textContent = "Preparing...";

            try {
                const resumeId = resumeBuilderState.selectedResumeId;
                const response = await fetch(`${API_BASE_URL}/resumes/${encodeURIComponent(resumeId)}/export`, {
                    headers: {
                        Authorization: `Bearer ${await getAccessToken()}`,
                    },
                });

                if (!response.ok) {
                    let message = "Export failed.";
                    try {
                        const error = await response.json();
                        message = error.detail || message;
                    } catch (_) {}
                    throw new Error(message);
                }

                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `${resumeBuilderState.selectedResume?.title?.replace(/\s+/g, "_") || "resume"}.pdf`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            } catch (error) {
                console.error("Export error:", error);
                alert(error.message || "Failed to export PDF.");
            } finally {
                exportBtn.disabled = false;
                exportBtn.textContent = originalText;
            }
        }

        function addLinkRow(label = "", url = "") {
            const row = document.createElement("div");
            row.className = "resume-link-row";
            row.innerHTML = `
                <div class="resume-field">
                    <label>Label</label>
                    <input type="text" name="contact.links[].label" maxlength="80" placeholder="GitHub" value="${escapeHTML(label)}">
                </div>
                <div class="resume-field">
                    <label>URL</label>
                    <input type="url" name="contact.links[].url" maxlength="500" placeholder="https://github.com/username" value="${escapeHTML(url)}">
                </div>
                <button type="button" class="resume-section-item-btn danger" aria-label="Remove link">&times;</button>
            `;
            row.querySelector(".resume-section-item-btn").addEventListener("click", () => row.remove());
            resumeElements.linksContainer.appendChild(row);
        }

        function addSectionItem(sectionData = null) {
            const section = sectionData || { type: "", items: [] };
            const item = document.createElement("div");
            item.className = `resume-section-item section-${section.type}`;
            item.dataset.sectionType = section.type;

            const typeLabel =
                RESUME_SECTION_HEADINGS[section.type] || section.type;

            const fieldsHtml = buildSectionFields(section);

            item.innerHTML = `
                <div class="resume-section-item-header">
                    <span class="resume-section-item-type">${escapeHTML(typeLabel)}</span>
                    <div class="resume-section-item-actions">
                        <button type="button" class="resume-section-item-btn" data-move-up aria-label="Move section up" title="Move up">&#9650;</button>
                        <button type="button" class="resume-section-item-btn" data-move-down aria-label="Move section down" title="Move down">&#9660;</button>
                        <button type="button" class="resume-section-item-btn danger" data-remove-section aria-label="Remove section" title="Remove section">&times;</button>
                    </div>
                </div>
                <div class="resume-section-fields">${fieldsHtml}</div>
            `;

            // Entry descriptions are textareas, so they grow
            // with their content instead of staying fixed.
            item.querySelectorAll("textarea").forEach(setupAutoGrow);

            item.querySelector("[data-move-up]")
                .addEventListener("click", () => moveSection(item, -1));

            item.querySelector("[data-move-down]")
                .addEventListener("click", () => moveSection(item, 1));

            item.querySelector("[data-remove-section]")
                .addEventListener("click", () => {
                    item.remove();
                    updateAddSectionButton();
                });

            resumeElements.sectionsContainer.appendChild(item);
            updateAddSectionButton();
        }

        // The backend normalizes every non-skills section to the same item shape
        // and keeps only title, organization, location, start, end, text, url and
        // bullets. Any other key is dropped server-side, so the inputs are named
        // from ITEM_TEXT_FIELDS rather than from local wording.
        const RESUME_ITEM_FIELD_LIMITS = {
            title: 200,
            organization: 200,
            location: 200,
            start: 40,
            end: 40,
            text: 4000,
            url: 500,
        };

        const RESUME_SECTION_HEADINGS = {
            skills: "Skills",
            education: "Education",
            experience: "Experience",
            projects: "Projects",
            certifications: "Certifications",
            custom: "",
        };

        // Presentation-only skill categorization for grouped display.
        // Derived from the canonical skill taxonomy in career_gap.py.
        // Does not affect stored schema — skills remain a flat string list.
        const SKILL_CATEGORIES = {
            // Programming languages
            "python": "Languages", "c": "Languages", "c++": "Languages", "java": "Languages",
            "javascript": "Languages", "typescript": "Languages", "go": "Languages",
            "rust": "Languages", "r": "Languages",
            // Data / ML
            "sql": "Data & ML", "pandas": "Data & ML", "numpy": "Data & ML",
            "scikit-learn": "Data & ML", "machine learning": "Data & ML",
            "deep learning": "Data & ML", "tensorflow": "Data & ML",
            "pytorch": "Data & ML", "keras": "Data & ML",
            "matplotlib": "Data & ML", "seaborn": "Data & ML",
            "power bi": "Data & ML", "tableau": "Data & ML", "excel": "Data & ML",
            // Backend / APIs
            "fastapi": "Backend & APIs", "flask": "Backend & APIs", "django": "Backend & APIs",
            "rest api": "Backend & APIs", "graphql": "Backend & APIs",
            // Databases
            "postgresql": "Databases", "mysql": "Databases", "mongodb": "Databases",
            "sqlite": "Databases", "redis": "Databases",
            // Cloud / DevOps
            "docker": "Cloud & DevOps", "kubernetes": "Cloud & DevOps",
            "aws": "Cloud & DevOps", "azure": "Cloud & DevOps", "google cloud": "Cloud & DevOps",
            "git": "Cloud & DevOps", "github": "Cloud & DevOps", "linux": "Cloud & DevOps",
            "github actions": "Cloud & DevOps",
            // Web / Frontend
            "html": "Frontend", "css": "Frontend", "react": "Frontend", "node.js": "Frontend",
            // Core CS
            "data structures": "Core CS", "algorithms": "Core CS",
            "object-oriented programming": "Core CS", "oop": "Core CS",
        };

        function _categorizeSkill(skill) {
            if (!skill) return "Other";
            const lower = skill.trim().toLowerCase();
            return SKILL_CATEGORIES[lower] || "Other";
        }

        function _groupSkillsByCategory(skills) {
            const groups = {};
            for (const skill of skills) {
                const cat = _categorizeSkill(skill);
                if (!groups[cat]) groups[cat] = [];
                groups[cat].push(skill);
            }
            // Order categories for consistent presentation
            const order = ["Languages", "Frontend", "Backend & APIs", "Databases", "Cloud & DevOps", "Data & ML", "Core CS", "Other"];
            const result = [];
            for (const cat of order) {
                if (groups[cat]) result.push({ category: cat, skills: groups[cat] });
            }
            for (const cat of Object.keys(groups)) {
                if (!order.includes(cat) && groups[cat]) result.push({ category: cat, skills: groups[cat] });
            }
            return result;
        }

        const RESUME_ITEM_FIELDS = {
            education: [
                { name: "title", label: "Degree", placeholder: "B.S. Computer Science" },
                { name: "organization", label: "Institution", placeholder: "University Name" },
                { name: "location", label: "Location", placeholder: "City, State" },
                { name: "start", label: "Start", placeholder: "2018" },
                { name: "end", label: "End", placeholder: "2022" },
                { name: "text", label: "Details", placeholder: "Honors, coursework, GPA", textarea: true },
            ],
            experience: [
                { name: "title", label: "Role", placeholder: "Software Engineer" },
                { name: "organization", label: "Company", placeholder: "Acme Corp" },
                { name: "location", label: "Location", placeholder: "City, State / Remote" },
                { name: "start", label: "Start", placeholder: "Jan 2022" },
                { name: "end", label: "End", placeholder: "Present" },
                { name: "text", label: "Summary", placeholder: "What you were responsible for", textarea: true },
                { name: "url", label: "URL", placeholder: "https://..." },
            ],
            projects: [
                { name: "title", label: "Project", placeholder: "Project Name" },
                { name: "organization", label: "Context", placeholder: "Personal, internship, coursework" },
                { name: "text", label: "Description", placeholder: "What you built and why", textarea: true },
                { name: "url", label: "URL", placeholder: "https://github.com/..." },
            ],
            certifications: [
                { name: "title", label: "Certification", placeholder: "AWS Solutions Architect" },
                { name: "organization", label: "Issuer", placeholder: "Amazon Web Services" },
                { name: "start", label: "Date Earned", placeholder: "2023" },
                { name: "url", label: "URL", placeholder: "https://..." },
            ],
            custom: [
                { name: "title", label: "Title", placeholder: "Item Title" },
                { name: "text", label: "Description", placeholder: "Details", textarea: true },
            ],
        };

        function buildResumeFieldHtml(field, value) {
            const maxLength = RESUME_ITEM_FIELD_LIMITS[field.name] || 200;

            return `
                <div class="resume-field">
                    <label>${escapeHTML(field.label)}</label>
                    ${field.textarea
                        ? `<textarea name="${field.name}" maxlength="${maxLength}" placeholder="${escapeHTML(field.placeholder)}">${escapeHTML(value)}</textarea>`
                        : `<input type="text" name="${field.name}" maxlength="${maxLength}" placeholder="${escapeHTML(field.placeholder)}" value="${escapeHTML(value)}">`
                    }
                </div>
            `;
        }

        function buildResumeBulletHtml(bullet) {
            return `
                <div class="resume-bullet-row">
                    <input
                        type="text"
                        name="bullets[]"
                        maxlength="1000"
                        placeholder="Action → Technical work → Result (e.g., Built API with FastAPI, cut latency 40%)"
                        value="${escapeHTML(bullet)}"
                    >
                    <button
                        type="button"
                        class="resume-section-item-btn danger"
                        data-remove-bullet
                        aria-label="Remove bullet"
                        title="Remove bullet"
                    >&times;</button>
                </div>
            `;
        }

        function buildResumeEntryHtml(type, itemData, index) {
            const config = RESUME_ITEM_FIELDS[type] || RESUME_ITEM_FIELDS.custom;
            const data = itemData && typeof itemData === "object" ? itemData : {};
            const bullets = Array.isArray(data.bullets) ? data.bullets : [];

            return `
                <div class="resume-section-fields-item" data-item-index="${index}">

                    ${config
                        .map((field) =>
                            buildResumeFieldHtml(
                                field,
                                data[field.name] || ""
                            )
                        )
                        .join("")}

                    <div class="resume-bullets">
                        ${bullets.map(buildResumeBulletHtml).join("")}

                        <button
                            type="button"
                            class="resume-bullet-add"
                            data-add-bullet
                        >
                            <span aria-hidden="true">+</span> Add Bullet
                        </button>
                    </div>

                    <button
                        type="button"
                        class="resume-section-item-btn danger"
                        data-remove-entry
                        aria-label="Remove entry"
                        title="Remove entry"
                    >&#10005;</button>

                </div>
            `;
        }

        function buildResumeSkillRowHtml(skill) {
            // Reuses the existing bullet row layout: an input beside a remove
            // button. No new CSS is introduced for this.
            return `
                <div class="resume-bullet-row">
                    <input
                        type="text"
                        name="skill[]"
                        maxlength="80"
                        placeholder="JavaScript"
                        value="${escapeHTML(skill)}"
                    >
                    <button
                        type="button"
                        class="resume-section-item-btn danger"
                        data-remove-skill
                        aria-label="Remove skill"
                        title="Remove skill"
                    >&times;</button>
                </div>
            `;
        }

        function buildSkillsFieldHtml(section) {
            // A skills section stores plain strings, not objects. Sending an
            // object here is rejected by the API as "Skill 1 must be text."
            const skills = (Array.isArray(section.items) ? section.items : [])
                .filter((skill) => typeof skill === "string" && skill.trim())
                .map((skill) => skill.trim());

            return `
                <div class="resume-bullets">
                    ${skills.map(buildResumeSkillRowHtml).join("")}
                </div>

                <button
                    type="button"
                    class="resume-bullet-add"
                    data-add-skill
                >
                    <span aria-hidden="true">+</span> Add Skill
                </button>
            `;
        }

        function buildSectionFields(section) {
            const type = section.type;
            const items = Array.isArray(section.items) ? section.items : [];
            const heading =
                typeof section.heading === "string"
                    ? section.heading
                    : "";

            // The section heading is the only supported place for a custom
            // section title, so it is offered for every section type.
            const headingField = `
                <div class="resume-field full-width">
                    <label>Section Heading</label>
                    <input
                        type="text"
                        name="heading"
                        maxlength="120"
                        placeholder="${escapeHTML(
                            RESUME_SECTION_HEADINGS[type] || "Section"
                        )}"
                        value="${escapeHTML(heading)}"
                    >
                </div>
            `;

            if (type === "skills") {
                return headingField + buildSkillsFieldHtml(section);
            }

            const entries = items
                .map(
                    (itemData, index) =>
                        buildResumeEntryHtml(type, itemData, index)
                )
                .join("");

            return `
                ${headingField}

                <div class="resume-section-entries">
                    ${entries}
                </div>

                <button
                    type="button"
                    class="resume-bullet-add"
                    data-add-entry
                >
                    <span aria-hidden="true">+</span> Add Another Entry
                </button>
            `;
        }

        function moveSection(item, direction) {
            const items = Array.from(resumeElements.sectionsContainer.querySelectorAll(".resume-section-item"));
            const index = items.indexOf(item);
            const newIndex = index + direction;
            if (newIndex < 0 || newIndex >= items.length) return;
            if (direction === -1) {
                item.parentNode.insertBefore(item, items[newIndex]);
            } else {
                item.parentNode.insertBefore(item, items[newIndex].nextSibling);
            }
        }

        function updateAddSectionButton() {
            const value = sectionTypeSelect
                ? sectionTypeSelect.getValue()
                : "";

            resumeElements.addSectionBtn.disabled = !value;
        }

        function updateSummaryCount() {
            const count = resumeElements.summaryTextarea.value.length;
            resumeElements.summaryCount.textContent = count;
        }

        function updateTitleCount() {
            const count = resumeElements.titleInput.value.length;
            resumeElements.titleCount.textContent = count;
        }

        // Accessible custom dropdown for the section-type
        // picker. Follows the ARIA listbox pattern: the
        // trigger button opens the menu, focus moves to the
        // listbox while it is open, and arrow keys move an
        // active option tracked with aria-activedescendant.
        // Selecting an option only updates the picker; a
        // section is created solely by the explicit Add
        // button.
        function setupSectionTypeSelect(onChange) {
            const trigger = document.getElementById(
                "add-section-type"
            );
            const menu = document.getElementById(
                "add-section-type-menu"
            );
            const valueText = document.getElementById(
                "add-section-type-text"
            );

            if (!trigger || !menu || !valueText) {
                return {
                    getValue: function () {
                        return "";
                    },
                    setValue: function () {},
                };
            }

            const options = Array.from(
                menu.querySelectorAll('[role="option"]')
            );

            let selectedValue = "";
            let activeIndex = 0;
            let isOpen = false;

            function getSelectedIndex() {
                return options.findIndex(
                    (option) => option.dataset.value === selectedValue
                );
            }

            function setActiveIndex(index) {
                if (!options.length) {
                    return;
                }

                activeIndex = Math.max(
                    0,
                    Math.min(index, options.length - 1)
                );

                options.forEach(function (option, position) {
                    option.classList.toggle(
                        "is-active",
                        position === activeIndex
                    );
                });

                const activeOption = options[activeIndex];

                if (activeOption) {
                    menu.setAttribute(
                        "aria-activedescendant",
                        activeOption.id
                    );

                    if (activeOption.scrollIntoView) {
                        activeOption.scrollIntoView({
                            block: "nearest",
                        });
                    }
                }
            }

            function positionMenu() {
                const rect = trigger.getBoundingClientRect();
                const menuHeight = menu.offsetHeight || 240;
                const spaceBelow =
                    window.innerHeight - rect.bottom;
                const opensUpward =
                    spaceBelow < menuHeight + 8;
                const top = opensUpward
                    ? Math.max(8, rect.top - menuHeight - 4)
                    : rect.bottom + 4;

                menu.style.top = `${top}px`;
                menu.style.left = `${rect.left}px`;
                menu.style.minWidth = `${rect.width}px`;

                const menuRect = menu.getBoundingClientRect();

                if (menuRect.right > window.innerWidth - 8) {
                    menu.style.left = `${Math.max(
                        8,
                        window.innerWidth - menuRect.width - 8
                    )}px`;
                }
            }

            function applySelection(option, shouldNotify) {
                if (!option) {
                    return;
                }

                selectedValue = option.dataset.value || "";

                options.forEach(function (candidate) {
                    const isSelected = candidate === option;

                    candidate.setAttribute(
                        "aria-selected",
                        isSelected ? "true" : "false"
                    );
                    candidate.classList.toggle(
                        "is-selected",
                        isSelected
                    );
                });

                valueText.textContent = option.textContent;
                valueText.classList.toggle(
                    "is-placeholder",
                    !selectedValue
                );

                if (shouldNotify && typeof onChange === "function") {
                    onChange(selectedValue);
                }
            }

            function open() {
                if (isOpen) {
                    return;
                }

                isOpen = true;
                positionMenu();
                menu.classList.add("is-open");
                trigger.setAttribute("aria-expanded", "true");
                setActiveIndex(getSelectedIndex());

                if (menu.focus) {
                    menu.focus();
                }
            }

            function close(returnFocus) {
                if (!isOpen) {
                    return;
                }

                isOpen = false;
                menu.classList.remove("is-open");
                trigger.setAttribute("aria-expanded", "false");
                menu.removeAttribute("aria-activedescendant");

                if (
                    returnFocus ||
                    menu.contains(document.activeElement)
                ) {
                    trigger.focus();
                }
            }

            function selectOption(option) {
                if (!option) {
                    return;
                }

                applySelection(option, true);
                close(true);
            }

            function setValue(value) {
                const option = options.find(
                    (candidate) => candidate.dataset.value === value
                );

                if (option) {
                    applySelection(option, true);
                }
            }

            trigger.addEventListener("click", function () {
                if (isOpen) {
                    close();
                } else {
                    open();
                }
            });

            trigger.addEventListener("keydown", function (event) {
                if (
                    event.key === "ArrowDown" ||
                    event.key === "ArrowUp"
                ) {
                    event.preventDefault();

                    if (!isOpen) {
                        open();
                    } else {
                        setActiveIndex(
                            activeIndex +
                                (event.key === "ArrowDown" ? 1 : -1)
                        );
                    }
                } else if (
                    event.key === "Enter" ||
                    event.key === " "
                ) {
                    if (isOpen) {
                        event.preventDefault();
                        selectOption(options[activeIndex]);
                    }
                } else if (event.key === "Escape") {
                    if (isOpen) {
                        event.preventDefault();
                        close(true);
                    }
                }
            });

            menu.addEventListener("keydown", function (event) {
                if (event.key === "ArrowDown") {
                    event.preventDefault();
                    setActiveIndex(activeIndex + 1);
                } else if (event.key === "ArrowUp") {
                    event.preventDefault();
                    setActiveIndex(activeIndex - 1);
                } else if (
                    event.key === "Home"
                ) {
                    event.preventDefault();
                    setActiveIndex(0);
                } else if (event.key === "End") {
                    event.preventDefault();
                    setActiveIndex(options.length - 1);
                } else if (
                    event.key === "Enter" ||
                    event.key === " "
                ) {
                    event.preventDefault();
                    selectOption(options[activeIndex]);
                } else if (event.key === "Escape") {
                    event.preventDefault();
                    close(true);
                } else if (event.key === "Tab") {
                    close();
                }
            });

            options.forEach(function (option) {
                option.addEventListener("click", function () {
                    selectOption(option);
                });

                option.addEventListener("mousemove", function () {
                    const index = options.indexOf(option);

                    if (index !== -1 && index !== activeIndex) {
                        setActiveIndex(index);
                    }
                });
            });

            document.addEventListener("click", function (event) {
                if (
                    isOpen &&
                    !trigger.contains(event.target) &&
                    !menu.contains(event.target)
                ) {
                    close();
                }
            });

            window.addEventListener(
                "scroll",
                function () {
                    if (isOpen) {
                        positionMenu();
                    }
                },
                true
            );

            window.addEventListener("resize", function () {
                if (isOpen) {
                    positionMenu();
                }
            });

            applySelection(options[0], false);

            return {
                getValue: function () {
                    return selectedValue;
                },
                setValue: setValue,
                close: function () {
                    close();
                },
            };
        }

        function initResumeBuilder() {
            resumeElements.createBtn.addEventListener("click", createResume);
            resumeElements.editBtn.addEventListener("click", editResume);
            resumeElements.cancelBtn.addEventListener("click", cancelEdit);
            resumeElements.saveBtn.addEventListener("click", saveResume);
            resumeElements.deleteBtn.addEventListener("click", deleteResume);
            resumeElements.setDefaultBtn.addEventListener("click", setDefaultResume);
            resumeElements.exportBtn.addEventListener("click", exportResume);

            sectionTypeSelect = setupSectionTypeSelect(
                updateAddSectionButton
            );

            resumeElements.addSectionBtn.addEventListener("click", () => {
                const type = sectionTypeSelect
                    ? sectionTypeSelect.getValue()
                    : "";

                if (type) {
                    addSectionItem({ type, items: [] });
                    sectionTypeSelect.setValue("");
                    updateAddSectionButton();
                }
            });

            resumeElements.addLinkBtn.addEventListener("click", () => addLinkRow());

            resumeElements.summaryTextarea.addEventListener("input", updateSummaryCount);

            setupAutoGrow(resumeElements.summaryTextarea);

            resumeElements.titleInput.addEventListener("input", updateTitleCount);

            resumeElements.sectionsContainer.addEventListener("click", (event) => {
                const target =
                    event.target instanceof Element
                        ? event.target
                        : null;

                if (!target) {
                    return;
                }

                // Adds an entry inside the section that was clicked. Creating a
                // whole new section here duplicated the section instead.
                if (target.closest("[data-add-entry]")) {
                    const sectionItem = target.closest(
                        ".resume-section-item"
                    );

                    if (!sectionItem) {
                        return;
                    }

                    const entries = sectionItem.querySelector(
                        ".resume-section-entries"
                    );

                    if (!entries) {
                        return;
                    }

                    const index = entries.children.length;

                    entries.insertAdjacentHTML(
                        "beforeend",
                        buildResumeEntryHtml(
                            sectionItem.dataset.sectionType,
                            null,
                            index
                        )
                    );

                    const newEntry = entries.lastElementChild;

                    if (newEntry) {
                        newEntry
                            .querySelectorAll("textarea")
                            .forEach(setupAutoGrow);
                    }

                    return;
                }

                if (target.closest("[data-add-bullet]")) {
                    const bullets = target.closest(".resume-bullets");

                    bullets.insertAdjacentHTML(
                        "beforeend",
                        buildResumeBulletHtml("")
                    );

                    return;
                }

                if (target.closest("[data-add-skill]")) {
                    // The Add Skill button is a sibling of the
                    // .resume-bullets container, not a descendant,
                    // so the container must be resolved from the
                    // enclosing section item.
                    const sectionItem = target.closest(
                        ".resume-section-item"
                    );

                    if (!sectionItem) {
                        return;
                    }

                    const skillsList = sectionItem.querySelector(
                        ".resume-bullets"
                    );

                    if (!skillsList) {
                        return;
                    }

                    skillsList.insertAdjacentHTML(
                        "beforeend",
                        buildResumeSkillRowHtml("")
                    );

                    return;
                }

                if (target.closest("[data-remove-entry]")) {
                    const entry = target.closest(
                        ".resume-section-fields-item"
                    );

                    if (entry) {
                        entry.remove();
                    }

                    return;
                }

                if (target.closest("[data-remove-bullet]")) {
                    const row = target.closest(".resume-bullet-row");

                    if (row) {
                        row.remove();
                    }

                    return;
                }

                if (target.closest("[data-remove-skill]")) {
                    const row = target.closest(".resume-bullet-row");

                    if (row) {
                        row.remove();
                    }
                }
            });

            loadResumes();
        }

        initResumeBuilder();
    }
);
