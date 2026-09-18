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

        const resultsSection =
            document.getElementById("results");

        const resultsContent =
            document.getElementById("results-content");

        const loadingSection =
            document.getElementById("loading");


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
                            × Remove
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
        // API
        // =================================================

        async function analyzeCareerGap(
            careerGapData
        ) {

            const response =
                await fetch(
                    "http://127.0.0.1:8000/analyze",
                    {

                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
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

            if (value === null ||
                value === undefined) {

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
                            <span class="card-icon">◎</span>
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
                            ◎
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
                                                        ? "✓"
                                                        : "•"
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
                            ◎
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
                                    ◇
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
                                                                ✓ No upgrade needed
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
                                    → ${escapeHTML(upgrade)}
                                </div>
                            `
                            : `
                                <div class="upgrade-action">
                                    ✓ Already demonstrated
                                </div>
                            `
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
                                ◫
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
                                                ★ ${formatStars(
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
                                            View on GitHub ↗
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
                            →
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
        // DISPLAY COMPLETE DASHBOARD
        // =================================================

        function displayResults(
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


            resultsContent.innerHTML =
                top +
                projects +
                `<div class="dashboard-bottom">
                    <div>
                        ${resources}
                    </div>

                    <div>
                        ${nextSteps}
                    </div>
                </div>`;


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
                        "Please enter your resume."
                    );

                    return;

                }


                if (!data.job_description) {

                    alert(
                        "Please enter the target job description."
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


                    displayResults(
                        result
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
                        <span>→</span>
                    `;

            }
        );

    }
);