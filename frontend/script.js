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

            document.getElementById("job-description-upload-button");

        const resumeUploadStatus =

            document.getElementById("resume-upload-status");

        const jobDescriptionUploadStatus =

            document.getElementById("job-description-upload-status");

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

const analysisHistorySection =
    document.getElementById(
        "analysis-history"
    );

const savedAnalysisSection =
    document.getElementById(
        "saved-analysis"
    );

const savedResultsContent =
    document.getElementById(
        "saved-results-content"
    );

        const resultsContent =

            document.getElementById("results-content");

        const loadingSection =

            document.getElementById("loading");

        const analysisHistoryList =

            document.getElementById("analysis-history-list");

        const authActionButton =
    document.getElementById(
        "auth-action-button"
    );

async function setupAuthAction() {

    if (!authActionButton) {
        return;
    }

    const { data, error } =
        await careerGapSupabase.auth.getSession();

    if (error || !data.session) {

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

setupAuthAction();

        let analysisHistoryData = [];
        let currentAnalysis = null;
        // =================================================

        // API CONFIGURATION

        // =================================================

        const API_BASE_URL =

              "https://careergap.onrender.com";

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

        if (!analyses.length) {

            analysisHistoryList.innerHTML = `
                <div class="empty-state">
                    No previous analyses yet.
                </div>
            `;

            return;
        }
        analysisHistoryData = analyses;

        analysisHistoryList.innerHTML =
            analyses.map(
                function (item,index) {

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

                            <div class="analysis-history-actions">

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
        data-analysis-id="${escapeHTML(
            String(item.id)
        )}"
        aria-label="Delete analysis"
        title="Delete analysis"
    >
        ×
    </button>

</div>
                        <div>

                        </article>
                    `;

                }
            ).join("");
            analysisHistoryList
    .querySelectorAll(".history-view-button")
    .forEach(
        function (button) {

            button.addEventListener(
                "click",
                function () {

                    const index =
                        Number(
                            button.dataset.historyIndex
                        );

                    const savedAnalysis =
                        analysisHistoryData[index];

                    if (!savedAnalysis) {
                        return;
                    }

                    displaySavedAnalysis(
    savedAnalysis.analysis
);

analysisHistoryList
    .querySelectorAll(
        ".history-delete-button"
    )
    .forEach(
        function (button) {

            button.addEventListener(
                "click",
                async function () {

                    const analysisId =
                        button.dataset.analysisId;

                    if (!analysisId) {
                        return;
                    }

                    const confirmed =
                        window.confirm(
                            "Delete this analysis? This cannot be undone."
                        );

                    if (!confirmed) {
                        return;
                    }

                    button.disabled = true;

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
                                    method: "DELETE",
                                    headers: {
                                        Authorization:
                                            `Bearer ${accessToken}`,
                                    },
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

                            throw new Error(message);
                        }

                        analysisHistoryData =
                            analysisHistoryData.filter(
                                function (item) {
                                    return (
                                        String(item.id) !==
                                        String(analysisId)
                                    );
                                }
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

                        button.disabled = false;
                    }
                }
            );
        }
);
setAnalysisView(
    "saved"
);

                }
            );

        }
    );

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

                textarea.scrollHeight > TEXTAREA_MAX_HEIGHT

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

        setupAutoGrow(jobDescriptionInput);


        projectsContainer

            .querySelectorAll(".project-description")

            .forEach(setupAutoGrow);


        projectsContainer.addEventListener(

            "input",

            function (event) {

                if (

                    event.target.matches(

                        ".project-description"

                    )

                ) {

                    autoGrowTextarea(event.target);

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

            button.disabled = uploading;

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

                    if (!uploadButton.disabled) {

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


                    /*

                     * Reset the file input so selecting

                     * the same file again triggers change.

                     */

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

                    .querySelector(".remove-project-button")

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

                .replaceAll("&", "&amp;")

                .replaceAll("<", "&lt;")

                .replaceAll(">", "&gt;")

                .replaceAll('"', "&quot;")

                .replaceAll("'", "&#039;");

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

                            ${escapeHTML(message.title)}

                        </h3>

                        <p>

                            ${escapeHTML(message.text)}

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

                    <article class="dashboard-card skill-card">

                        <div class="card-title">

                            <span class="card-icon">&#9678;</span>

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

                                    matched.includes(skill);


                                return `

                                    <div class="skill-row">

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

                                                ${escapeHTML(skill)}

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

            const matched =

                result.matched_skills || [];

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

                    skill => skill.toLowerCase()

                );


            if (

                skills.includes("fastapi") ||

                skills.includes("django") ||

                skills.includes("flask")

            ) {

                return "Backend Developer";

            }


            if (

                skills.includes("react") ||

                skills.includes("html") ||

                skills.includes("css")

            ) {

                return "Frontend Developer";

            }


            if (

                skills.includes("machine learning") ||

                skills.includes("scikit-learn") ||

                skills.includes("pandas")

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


            if (analyses.length === 0) {

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

                                                (project.skills || [])

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

                                                                âœ“ No upgrade needed

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

                <div class="upgrade-item">

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

                                <div class="upgrade-action">

                                    &rarr; ${escapeHTML(upgrade)}

                                </div>

                            `

                            : compatibility === "ALREADY DEMONSTRATED"

                                ? `

                                    <div class="upgrade-action">

                                        âœ“ Already demonstrated

                                    </div>

                                `

                                : ""

                    }

                </div>

            `;

        }


        // =================================================

        // GITHUB RESOURCES

        // =================================================

        function createResources(

            result

        ) {

            const resources =

                result.github_recommendations || [];


            if (!resources.length) {

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

                            GitHub

                        </span>

                    </div>


                    <div class="resource-grid">

                        ${resources.map(

                            function (resource) {

                                const repo =

                                    resource.repo ||

                                    {};

                                const skill =

                                    resource.skill ||

                                    "Resource";

                                const name =

                                    repo.full_name ||

                                    "GitHub Repository";                                const description =

                                    repo.description ||

                                    "A relevant learning resource.";

                                const stars =

                                    Number(

                                        repo.stargazers_count ||

                                        0

                                    );

                                const url =

                                    repo.html_url ||

                                    "#";


                                return `

                                    <article

                                        class="resource-card"

                                    >

                                        <span

                                            class="resource-skill"

                                        >

                                            ${escapeHTML(

                                                skill

                                            )}

                                        </span>


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

                                                â˜… ${formatStars(

                                                    stars

                                                )}

                                            </span>

                                            <span>

                                                Relevance ${

                                                    resource.score || 0

                                                }

                                            </span>

                                        </div>


                                        <a

                                            class="resource-link"

                                            href="${escapeHTML(url)}"

                                            target="_blank"

                                            rel="noopener noreferrer"

                                        >

                                            View on GitHub &#8599;

                                        </a>

                                    </article>

                                `;

                            }

                        ).join("")}

                    </div>

                </section>

            `;

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

                        .replace(".0", "") +

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

                            priority.importance === "HIGH"

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

                            function (step, index) {

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

        function renderAdviceMarkdown(text) {

    if (!text) {
        return "";
    }

    return escapeHTML(text)
        .split("\n")
        .map(function (line) {

            const formattedLine =
                line.replace(
                    /\*\*(.*?)\*\*/g,
                    "<strong>$1</strong>"
                );

            if (line.startsWith("### ")) {
                return (
                    "<h4>" +
                    formattedLine.slice(4) +
                    "</h4>"
                );
            }

            if (line.startsWith("## ")) {
                return (
                    "<h4>" +
                    formattedLine.slice(3) +
                    "</h4>"
                );
            }

            if (
                line.startsWith("* ") ||
                line.startsWith("- ")
            ) {
                return (
                    "<li>" +
                    formattedLine.slice(2) +
                    "</li>"
                );
            }

            if (/^\d+\. /.test(line)) {
                return (
                    '<div class="advice-step">' +
                    formattedLine +
                    "</div>"
                );
            }

            return formattedLine
                ? "<p>" + formattedLine + "</p>"
                : '<div class="advice-spacer"></div>';

        })
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
// DISPLAY COMPLETE DASHBOARD
// =================================================
function setAnalysisView(
    view
) {
    const sections = [
        resultsSection,
        analysisHistorySection,
        savedAnalysisSection
    ];

    sections.forEach(
        function (section) {
            if (section) {
                section.classList.add(
                    "hidden"
                );
            }
        }
    );

    const tabs = [
        currentAnalysisTab,
        historyTab,
        savedAnalysisTab
    ];

    tabs.forEach(
        function (tab) {
            if (tab) {
                tab.classList.remove(
                    "active"
                );
            }
        }
    );

    if (view === "current") {
        resultsSection.classList.remove(
            "hidden"
        );

        currentAnalysisTab.classList.add(
            "active"
        );
    }

    if (view === "history") {
        analysisHistorySection.classList.remove(
            "hidden"
        );

        historyTab.classList.add(
            "active"
        );
    }

    if (view === "saved") {
        savedAnalysisSection.classList.remove(
            "hidden"
        );

        savedAnalysisTab.classList.add(
            "active"
        );
    }
}
function buildAnalysisMarkup(
    result
) {
    const top = `
        <div class="dashboard-top">
            ${createScoreCard(result)}
            ${createSkillBreakdown(result)}
            ${createRoleInsights(result)}
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
            <div class="dashboard-bottom">
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


function displayResults(
    result
) {
    resultsContent.innerHTML =
        buildAnalysisMarkup(
            result
        );

    resultsSection.classList.remove(
        "hidden"
    );

    loadingSection.classList.add(
        "hidden"
    );
}


function displaySavedAnalysis(
    result
) {

    const top =
        `
            <div
                class="dashboard-top"
            >

                ${createScoreCard(result)}

                ${createSkillBreakdown(result)}

                ${createRoleInsights(result)}

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

    savedResultsContent.innerHTML =
        `
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

            ${top}

            ${projects}

            ${aiAdvice}

            <div class="dashboard-bottom">

                <div>
                    ${resources}
                </div>

                <div>
                    ${nextSteps}
                </div>

            </div>
        `;

    savedAnalysisSection.classList.remove(
        "hidden"
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


                // Basic frontend validation

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

                currentAnalysis = result;

currentAnalysisTab.disabled =
    false;

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

                    <div class="result-error">

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

            }


            analyzeButton.disabled =

                false;

            analyzeButton.innerHTML =

                `

                    Analyze My Career Gap

                    <span>&rarr;</span>

                `;

            }

        );

        loadAnalysisHistory();

setAnalysisView(
    "history"
);
    }
);
