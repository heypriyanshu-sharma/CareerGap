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

        const authActionButton =
            document.getElementById(
                "auth-action-button"
            );

        const userIdentityLabel =
            document.getElementById(
                "user-email"
            );

        let analysisHistoryData = [];
        let currentAnalysis = null;

        // =================================================
        // AUTH ACTION
        // =================================================

        function resolveUserIdentity(
            user
        ) {

            if (!user) {
                return "";
            }

            const metadata =
                user.user_metadata &&
                typeof user.user_metadata ===
                    "object"
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

        function displayUserIdentity(
            user
        ) {

            if (!userIdentityLabel) {
                return;
            }

            const identity =
                resolveUserIdentity(
                    user
                );

            userIdentityLabel.textContent =
                identity;

            userIdentityLabel.title =
                identity;

            userIdentityLabel.classList.toggle(
                "is-empty",
                !identity
            );
        }

        async function setupAuthAction() {

            if (!authActionButton) {
                return;
            }

            const { data, error } =
                await careerGapSupabase.auth.getSession();

            if (error || !data.session) {

                displayUserIdentity(
                    null
                );

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

                return;
            }

            displayUserIdentity(
                data.session.user
            );

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

                    displayUserIdentity(
                        null
                    );

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

                        displayUserIdentity(
                            data.session.user
                        );

                        return;
                    }

                    window.location.replace(
                        "login.html"
                    );

                }
            );
        }

        setupAuthAction();

        // =================================================
        // API CONFIGURATION
        // =================================================

        const API_BASE_URL =
    window.location.protocol === "file:" ||
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1"
        ? "http://127.0.0.1:8000"
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

            return await response.json();
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

            const advice =
                result.ai_advice;

            if (!advice) {
                return "";
            }

            return `
                <section
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
                        ${renderAdviceMarkdown(
                            advice
                        )}
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

    if (resultsSection) {
        resultsSection.classList.toggle(
            "hidden",
            view !== "current"
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
}

        // =================================================
        // BUILD COMPLETE DASHBOARD
        // =================================================

        function buildAnalysisMarkup(
            result
        ) {

            const top = `
                <div
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

            return (
                top +
                projects +
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

        function displaySavedAnalysis(
    savedAnalysis
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

                        displaySavedAnalysis(
                            savedAnalysis.analysis
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

        setAnalysisView(
            "history"
        );
    }
);