import csv
import json
import re
from pathlib import Path
from urllib.parse import quote_plus

from github_search import search_github, rank_repositories
from ai_advisor import generate_career_advice, safe_error_detail


# ============================================================
# CAREERGAP
# Evidence-Based Career Readiness Engine
# ============================================================


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

RESUME_FILE = BASE_DIR / "resume.txt"
JOB_FILE = BASE_DIR / "job_description.txt"
PROJECTS_FILE = BASE_DIR / "projects.json"
MARKET_FILE = BASE_DIR / "market_data.csv"


# ============================================================
# DEMO DATA
# ============================================================

DEMO_RESUME = """
I am a Python developer with experience in SQL, Pandas,
Git and Machine Learning.
"""

DEMO_JOB = """
We are looking for a Data Scientist with strong Python and SQL skills.
Experience with Pandas is preferred.
Knowledge of Docker is preferred.
"""

DEMO_PROJECTS = [
    {
        "name": "Customer Churn Prediction",
        "description": """
        A machine learning project that predicts whether a customer
        will leave a company using Python, Pandas, SQL and Scikit-learn.
        """
    },
    {
        "name": "Sales Data Analysis",
        "description": """
        A data analysis project using Python, Pandas, NumPy and SQL
        to analyze sales data and generate business insights.
        """
    }
]


# ============================================================
# INPUT / DATA LAYER
# ============================================================

def validate_text_file(path, label):
    """Read and validate a required text input file."""

    if not path.exists():
        raise FileNotFoundError(
            f"{label} file not found: {path.name}"
        )

    if not path.is_file():
        raise ValueError(
            f"{label} path is not a file: {path.name}"
        )

    text = path.read_text(encoding="utf-8").strip()

    if not text:
        raise ValueError(
            f"{label} file is empty: {path.name}"
        )

    return text


def validate_projects(projects):
    """Validate the structure of projects.json."""

    if not isinstance(projects, list):
        raise ValueError(
            "projects.json must contain a JSON list."
        )

    if not projects:
        raise ValueError(
            "projects.json must contain at least one project."
        )

    for index, project in enumerate(projects, start=1):

        if not isinstance(project, dict):
            raise ValueError(
                f"Project {index} must be a JSON object."
            )

        name = project.get("name")
        description = project.get("description")

        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"Project {index} is missing a valid 'name'."
            )

        if (
            not isinstance(description, str)
            or not description.strip()
        ):
            raise ValueError(
                f"Project {index} is missing a valid 'description'."
            )


def load_projects_file():
    """Load and validate projects.json."""

    if not PROJECTS_FILE.exists():
        raise FileNotFoundError(
            "projects.json not found."
        )

    if not PROJECTS_FILE.is_file():
        raise ValueError(
            "projects.json path is not a file."
        )

    try:
        projects = json.loads(
            PROJECTS_FILE.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError as error:
        raise ValueError(
            f"projects.json contains invalid JSON: {error}"
        ) from error

    validate_projects(projects)

    return projects


def load_careergap_input():
    """
    Load either demo data or complete user input.

    DEMO MODE:
        None of the three input files exist.

    USER MODE:
        At least one input file exists.
        In that case all three are required.
    """

    files = [
        RESUME_FILE,
        JOB_FILE,
        PROJECTS_FILE
    ]

    any_input_exists = any(
        path.exists()
        for path in files
    )

    if not any_input_exists:

        print("\n===== CAREERGAP INPUT =====")
        print("Mode: DEMO")
        print("Resume: demo data")
        print("Job description: demo data")
        print("Projects: demo data")
        print(
            "Tip: create resume.txt, "
            "job_description.txt and projects.json "
            "to analyze your own data."
        )

        return (
            DEMO_RESUME,
            DEMO_JOB,
            DEMO_PROJECTS,
            "DEMO"
        )

    missing_files = [
        path.name
        for path in files
        if not path.exists()
    ]

    if missing_files:
        raise FileNotFoundError(
            "USER MODE requires all three input files. "
            f"Missing: {', '.join(missing_files)}"
        )

    resume_text = validate_text_file(
        RESUME_FILE,
        "Resume"
    )

    job_text = validate_text_file(
        JOB_FILE,
        "Job description"
    )

    projects = load_projects_file()

    print("\n===== CAREERGAP INPUT =====")
    print("Mode: USER")
    print("Resume: resume.txt")
    print("Job description: job_description.txt")
    print(
        f"Projects: projects.json "
        f"({len(projects)} projects)"
    )
    print("Input validation: PASSED")

    return (
        resume_text,
        job_text,
        projects,
        "USER"
    )


# ============================================================
# KNOWN SKILLS
# ============================================================

known_skills = [

    # Programming languages
    "Python",
    "C",
    "C++",
    "Java",
    "JavaScript",
    "TypeScript",
    "Go",
    "Rust",
    "R",

    # Data / ML
    "SQL",
    "Pandas",
    "NumPy",
    "Scikit-learn",
    "Machine Learning",
    "Deep Learning",
    "TensorFlow",
    "PyTorch",
    "Keras",
    "Matplotlib",
    "Seaborn",
    "Power BI",
    "Tableau",
    "Excel",

    # Backend / APIs
    "FastAPI",
    "Flask",
    "Django",
    "REST API",
    "GraphQL",

    # Databases
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "SQLite",
    "Redis",

    # Cloud / DevOps
    "Docker",
    "Kubernetes",
    "AWS",
    "Azure",
    "Google Cloud",
    "Git",
    "GitHub",
    "Linux",

    # Web / frontend
    "HTML",
    "CSS",
    "React",
    "Node.js",

    # Core CS / engineering
    "Data Structures",
    "Algorithms",
    "Object-Oriented Programming",
    "OOP",
    "GitHub Actions"
]


# ============================================================
# SKILL ALIASES
# ============================================================

skill_aliases = {

    "sklearn": "Scikit-learn",
    "scikit learn": "Scikit-learn",

    "machine learning": "Machine Learning",
    "ml": "Machine Learning",

    "deep learning": "Deep Learning",

    "np": "NumPy",
    "pd": "Pandas",

    "fast api": "FastAPI",

    "restful api": "REST API",
    "restful apis": "REST API",

    "postgres": "PostgreSQL",
    "postgre sql": "PostgreSQL",

    "mongo": "MongoDB",

    "amazon web services": "AWS",

    "google cloud platform": "Google Cloud",
    "gcp": "Google Cloud",

    "object oriented programming":
        "Object-Oriented Programming",

    "object oriented":
        "Object-Oriented Programming",

    "data structures and algorithms":
        "Data Structures",

    "dsa":
        "Data Structures"
}


# ============================================================
# SKILL EXTRACTION
# ============================================================

def extract_skills(text):
    """Extract known skills while handling aliases and tech names."""

    if not isinstance(text, str):
        return []

    text_lower = text.lower()
    found_skills = []

    def contains_term(term):
        term_lower = term.lower()

        # C needs special handling because it appears
        # inside many normal words.
        if term_lower == "c":
            return bool(
                re.search(
                    r"(?<![a-z0-9+#])c(?![a-z0-9+#])",
                    text_lower
                )
            )

        # Technology names containing punctuation.
        if any(
            character in term_lower
            for character in "+.#-"
        ):
            normalized_text = re.sub(
                r"\s+",
                " ",
                text_lower
            )

            normalized_term = re.sub(
                r"\s+",
                " ",
                term_lower
            ).strip()

            return normalized_term in normalized_text

        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(term_lower)
            + r"(?![a-z0-9])"
        )

        return bool(
            re.search(pattern, text_lower)
        )

    skills_to_check = sorted(
        known_skills,
        key=len,
        reverse=True
    )

    for skill in skills_to_check:

        if (
            contains_term(skill)
            and skill not in found_skills
        ):
            found_skills.append(skill)

    for alias, main_skill in sorted(
        skill_aliases.items(),
        key=lambda item: len(item[0]),
        reverse=True
    ):

        if (
            contains_term(alias)
            and main_skill not in found_skills
        ):
            found_skills.append(main_skill)

    found_skills.sort(
        key=lambda skill:
        known_skills.index(skill)
        if skill in known_skills
        else len(known_skills)
    )

    return found_skills


# ============================================================
# SKILL GAP ANALYSIS
# ============================================================

def analyze_skills(
    resume_skills,
    job_skills
):
    """Find matched and missing job skills."""

    matched = [
        skill
        for skill in job_skills
        if skill in resume_skills
    ]

    missing = [
        skill
        for skill in job_skills
        if skill not in resume_skills
    ]

    return matched, missing


# ============================================================
# SKILL IMPORTANCE
# ============================================================

def determine_importance(
    job_text,
    skill
):
    """Determine job-skill importance using section-aware parsing."""
    if not isinstance(job_text, str) or not isinstance(skill, str):
        return "Mentioned"
    required_headers = {"required", "requirements", "required skills", "must have", "must-have", "mandatory", "essential"}
    preferred_headers = {"preferred", "preferred skills", "nice to have", "nice-to-have", "desired", "bonus", "good to have"}
    current_section = "Mentioned"
    skill_lower = skill.lower()
    for raw_line in job_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        normalized = re.sub(r"^[\s*\-•]+", "", line).strip().lower()
        normalized = re.sub(r"\s*:+\s*$", "", normalized)
        if normalized in required_headers:
            current_section = "Required"
            continue
        if normalized in preferred_headers:
            current_section = "Preferred"
            continue
        if skill_lower in line.lower():
            return current_section
    sentences = re.split(r"[.!?]", job_text)
    for sentence in sentences:
        sentence_lower = sentence.lower()
        position = sentence_lower.find(skill_lower)
        if position == -1:
            continue
        required_positions = [m.start() for m in re.finditer(r"\brequired\b", sentence_lower)]
        preferred_positions = [m.start() for m in re.finditer(r"\bpreferred\b", sentence_lower)]
        if preferred_positions and preferred_positions[-1] <= position:
            return "Preferred"
        if required_positions and required_positions[-1] <= position:
            return "Required"
    return "Mentioned"


# ============================================================
# MARKET EVIDENCE
# ============================================================

def get_market_data():
    """Load market demand from market_data.csv."""

    market_data = {}

    try:

        with MARKET_FILE.open(
            "r",
            newline="",
            encoding="utf-8"
        ) as file:

            reader = csv.DictReader(file)

            if reader.fieldnames is None:
                print(
                    "market_data.csv has no header."
                )
                return market_data

            required_columns = [
                "skill",
                "market_demand"
            ]

            for column in required_columns:

                if column not in reader.fieldnames:

                    print(
                        "market_data.csv is missing "
                        f"'{column}' column."
                    )

                    print(
                        "Found columns:",
                        reader.fieldnames
                    )

                    return market_data

            for row in reader:

                skill = (
                    row.get("skill", "")
                    .strip()
                )

                try:

                    demand = float(
                        row[
                            "market_demand"
                        ].strip()
                    )

                    if skill:
                        market_data[
                            skill.lower()
                        ] = demand

                except (
                    ValueError,
                    AttributeError
                ):
                    continue

    except FileNotFoundError:

        print(
            "market_data.csv not found."
        )

    return market_data


def get_market_demand(
    skill,
    market_data
):
    """Return market demand when available."""

    return market_data.get(
        skill.lower()
    )


# ============================================================
# CAREERGAP SCORE
# ============================================================

def calculate_score(
    resume_skills,
    job_skills
):
    """Calculate deterministic skill match percentage."""

    if not job_skills:
        return 0

    matched = len(
        set(resume_skills)
        & set(job_skills)
    )

    return round(
        (matched / len(job_skills)) * 100,
        2
    )


# ============================================================
# MISSING SKILL PRIORITY
# ============================================================

def calculate_skill_priority(
    skill,
    job_text,
    market_data
):
    """
    Combine job importance and available market evidence.

    This does not invent arbitrary skill weights.
    """

    importance = determine_importance(
        job_text,
        skill
    )

    demand = get_market_demand(
        skill,
        market_data
    )

    if importance == "Required":
        priority = "HIGH"

    elif importance == "Preferred":
        priority = "MEDIUM"

    else:
        priority = "LOW"

    # Strong market evidence can raise priority.
    if demand is not None and demand >= 50:

        if priority == "MEDIUM":
            priority = "HIGH"

        elif priority == "LOW":
            priority = "MEDIUM"

    return {
        "skill": skill,
        "importance": importance,
        "market_demand": demand,
        "priority": priority
    }


# ============================================================
# PROJECT SKILLS
# ============================================================

def analyze_project_skills(project):
    """Extract demonstrated skills from a project."""

    return extract_skills(
        project["description"]
    )


# ============================================================
# PROJECT CHARACTERISTICS
# ============================================================

project_characteristics = {

    "Machine Learning": [
        "machine learning",
        "prediction",
        "model",
        "scikit-learn",
        "classification",
        "regression"
    ],

    "Data Analysis": [
        "data analysis",
        "business insights",
        "analysis",
        "analytics"
    ],

    "API/Application": [
        "api", "rest api", "restful api", "backend",
        "web application", "web service", "service endpoint",
        "endpoint", "fastapi", "flask", "django"
    ],

    "Database": [
        "database",
        "postgresql",
        "mysql",
        "mongodb",
        "sql database"
    ],

    "Deployment": [
        "deployment",
        "deploy",
        "production",
        "server",
        "hosting"
    ]
}


# ============================================================
# PROJECT CHARACTERISTIC DETECTION
# ============================================================

def detect_project_characteristics(project):
    """Detect high-level characteristics from project description."""

    description = project[
        "description"
    ].lower()

    detected = []

    for characteristic, signals in (
        project_characteristics.items()
    ):

        for signal in signals:

            if signal in description:

                detected.append(
                    characteristic
                )

                break

    return detected


# ============================================================
# PROJECT UPGRADE INTELLIGENCE
# ============================================================

def check_project_compatibility(
    project,
    missing_skill,
    demonstrated_skills=None
):
    """
    Determine whether a missing job skill can meaningfully
    strengthen an existing project.

    Demonstrated project skills are checked FIRST.
    """

    if demonstrated_skills is None:
        demonstrated_skills = (
            analyze_project_skills(project)
        )

    # --------------------------------------------------------
    # ALREADY DEMONSTRATED
    # --------------------------------------------------------

    if missing_skill in demonstrated_skills:

        return {
            "compatibility":
                "ALREADY DEMONSTRATED",

            "reason": (
                f"This project already demonstrates "
                f"{missing_skill}. No upgrade is needed "
                f"to add this skill."
            ),

            "upgrade": None,

            "resume_evidence": []
        }

    characteristics = (
        detect_project_characteristics(
            project
        )
    )

    # --------------------------------------------------------
    # DOCKER
    # --------------------------------------------------------

    if missing_skill == "Docker":

        useful_characteristics = [
            "Machine Learning",
            "API/Application",
            "Database",
            "Deployment"
        ]

        matches = [
            characteristic
            for characteristic in characteristics
            if characteristic
            in useful_characteristics
        ]

        if len(matches) >= 2:

            return {
                "compatibility": "HIGH",

                "reason": (
                    "Docker can meaningfully improve "
                    "this project because it involves "
                    + ", ".join(matches)
                    + "."
                ),

                "upgrade": (
                    "Containerize the project and create "
                    "a reproducible Docker environment."
                ),

                "resume_evidence": [
                    "Docker",
                    "Containerized application",
                    "Reproducible deployment environment"
                ]
            }

        if len(matches) == 1:

            return {
                "compatibility": "MEDIUM",

                "reason": (
                    "Docker could be integrated into "
                    "the project, but its value may "
                    "be limited."
                ),

                "upgrade": (
                    "Add Docker to create a reproducible "
                    "environment for the project."
                ),

                "resume_evidence": [
                    "Docker",
                    "Containerized project"
                ]
            }

        return {
            "compatibility": "LOW",

            "reason": (
                "There is currently little evidence "
                "that Docker would meaningfully "
                "improve this project."
            ),

            "upgrade": None,

            "resume_evidence": []
        }

    # --------------------------------------------------------
    # UNKNOWN SKILL
    # --------------------------------------------------------

    return {
        "compatibility": "UNKNOWN",

        "reason": (
            "CareerGap does not yet have enough "
            "evidence to determine whether this "
            "skill fits the project."
        ),

        "upgrade": None,

        "resume_evidence": []
    }


def generate_project_upgrade_recommendations(
    projects,
    missing_skills
):
    """
    Generate project recommendations using both
    demonstrated skills and project characteristics.
    """

    recommendations = []

    for skill in missing_skills:

        for project in projects:

            demonstrated_skills = (
                analyze_project_skills(
                    project
                )
            )

            result = (
                check_project_compatibility(
                    project,
                    skill,
                    demonstrated_skills
                )
            )

            recommendations.append({
                "skill": skill,
                "project": project["name"],
                "compatibility":
                    result["compatibility"],
                "reason":
                    result["reason"],
                "upgrade":
                    result["upgrade"],
                "resume_evidence":
                    result["resume_evidence"]
            })

    return recommendations


# ============================================================
# CURATED LEARNING RESOURCES
# ============================================================

CANONICAL_SKILL_RESOURCES = {
    # Programming languages
    "Python": (
        "Python Official Documentation", "https://docs.python.org/3/", "Official language tutorial, standard library documentation, and language reference.",
        "Exercism Python Track", "https://exercism.org/tracks/python", "Free hands-on coding exercises with test suites and guided concept progression."
    ),
    "C": (
        "cppreference C Documentation", "https://en.cppreference.com/w/c", "Comprehensive reference for the C standard library and language specification.",
        "Exercism C Track", "https://exercism.org/tracks/c", "Test-driven programming exercises focusing on pointers, memory, and C idioms."
    ),
    "C++": (
        "cppreference C++ Documentation", "https://en.cppreference.com/w/cpp", "Standard library reference and language specifications for modern C++.",
        "Exercism C++ Track", "https://exercism.org/tracks/cpp", "Hands-on coding challenges covering modern C++, classes, and templates."
    ),
    "Java": (
        "Oracle Java Documentation", "https://docs.oracle.com/en/java/", "Official Java SE documentation, API specification, and developer guides.",
        "Exercism Java Track", "https://exercism.org/tracks/java", "Interactive coding exercises covering Java OOP, data structures, and APIs."
    ),
    "JavaScript": (
        "MDN Web Docs — JavaScript", "https://developer.mozilla.org/en-US/docs/Web/JavaScript", "Authoritative guide and reference for modern JavaScript from Mozilla.",
        "Exercism JavaScript Track", "https://exercism.org/tracks/javascript", "Practice JavaScript fundamentals, array methods, async/await, and DOM logic."
    ),
    "TypeScript": (
        "TypeScript Handbook & Documentation", "https://www.typescriptlang.org/docs/", "Official TypeScript language handbook, type system guide, and compiler reference.",
        "TypeScript Playground", "https://www.typescriptlang.org/play", "Official interactive in-browser playground for testing types, generics, and compiler options."
    ),
    "Go": (
        "Go Documentation & Standard Library", "https://go.dev/doc/", "Official documentation, effective Go guide, and standard library reference.",
        "A Tour of Go", "https://go.dev/tour/", "Interactive guided tour with executable in-browser exercises covering Go fundamentals."
    ),
    "Rust": (
        "The Rust Programming Language Book", "https://doc.rust-lang.org/book/", "The official book on Rust covering ownership, borrowing, lifetimes, and concurrency.",
        "Rustlings Practice Exercises", "https://github.com/rust-lang/rustlings", "Small guided exercises to get familiar with reading and writing Rust code."
    ),
    "R": (
        "The R Project Official Documentation", "https://www.r-project.org/other-docs.html", "Official manuals and reference documentation for the R statistical computing environment.",
        "W3Schools R Tutorial & Exercises", "https://www.w3schools.com/r/", "Hands-on exercises and examples for statistical programming and data analysis in R."
    ),

    # Data / ML
    "SQL": (
        "PostgreSQL SQL Commands Reference", "https://www.postgresql.org/docs/current/sql-commands.html", "Standard SQL command guide, syntax diagrams, and query structure reference.",
        "SQLZoo Interactive Tutorials", "https://sqlzoo.net/", "Interactive live SQL practice with instant query execution and feedback."
    ),
    "Pandas": (
        "Pandas User Guide & API Reference", "https://pandas.pydata.org/docs/", "Official user guide and API reference for data manipulation and DataFrame operations.",
        "Pandas Getting Started Tutorials", "https://pandas.pydata.org/docs/getting_started/intro_tutorials/", "Hands-on walkthroughs for data reshaping, filtering, grouping, and statistical summaries."
    ),
    "NumPy": (
        "NumPy User Guide & API Reference", "https://numpy.org/doc/stable/", "Official documentation for N-dimensional arrays, vectorization, and mathematical functions.",
        "NumPy Tutorials Gallery", "https://numpy.org/numpy-tutorials/", "Practical numerical computing exercises and guided notebooks."
    ),
    "Scikit-learn": (
        "Scikit-learn User Guide", "https://scikit-learn.org/stable/user_guide.html", "Official guide for supervised and unsupervised algorithms, pipelines, and model evaluation.",
        "Scikit-learn Examples Gallery", "https://scikit-learn.org/stable/auto_examples/", "Code walkthroughs showing end-to-end classification, regression, and clustering workflows."
    ),
    "Machine Learning": (
        "Google Machine Learning Crash Course", "https://developers.google.com/machine-learning/crash-course", "Google's fast-paced, practical introduction to foundational machine learning concepts.",
        "Kaggle Learn — Intro to Machine Learning", "https://www.kaggle.com/learn/intro-to-machine-learning", "Hands-on micro-course building decision trees, random forests, and validating models."
    ),
    "Deep Learning": (
        "Dive into Deep Learning (D2L.ai)", "https://d2l.ai/", "Open-source interactive deep learning textbook with complete runnable code implementations.",
        "Kaggle Learn — Intro to Deep Learning", "https://www.kaggle.com/learn/intro-to-deep-learning", "Interactive notebooks building and training neural networks with Keras and TensorFlow."
    ),
    "TensorFlow": (
        "TensorFlow Core Documentation", "https://www.tensorflow.org/api_docs", "Official API documentation and guides for training and deploying machine learning models.",
        "TensorFlow Tutorials", "https://www.tensorflow.org/tutorials", "Hands-on beginner and intermediate machine learning projects with step-by-step code."
    ),
    "PyTorch": (
        "PyTorch Official Documentation", "https://pytorch.org/docs/stable/", "Official API documentation, autograd engine, and neural network building blocks.",
        "PyTorch Interactive Tutorials", "https://pytorch.org/tutorials/", "Step-by-step guides for computer vision, NLP, and model training in PyTorch."
    ),
    "Keras": (
        "Keras Developer Guides & API", "https://keras.io/api/", "Official API reference and developer guides for the high-level neural network framework.",
        "Keras Code Examples", "https://keras.io/examples/", "Curated collection of runnable deep learning examples for vision, text, and structured data."
    ),
    "Matplotlib": (
        "Matplotlib Documentation", "https://matplotlib.org/stable/contents.html", "Official guide and API reference for Python data visualization and plotting.",
        "Matplotlib Examples & Tutorials", "https://matplotlib.org/stable/tutorials/index.html", "Interactive plotting walkthroughs from basic figures to advanced custom charts."
    ),
    "Seaborn": (
        "Seaborn Documentation & User Guide", "https://seaborn.pydata.org/", "Official guide and API reference for statistical data visualization in Python.",
        "Seaborn Tutorial Gallery", "https://seaborn.pydata.org/tutorial.html", "Practical guides for categorical plots, distribution analysis, and regression plots."
    ),
    "Power BI": (
        "Microsoft Power BI Documentation", "https://learn.microsoft.com/en-us/power-bi/", "Official documentation for creating reports, DAX calculations, and interactive dashboards.",
        "Microsoft Learn — Power BI Modules", "https://learn.microsoft.com/en-us/training/powerplatform/power-bi", "Free interactive learning paths and guided exercises for building Power BI reports."
    ),
    "Tableau": (
        "Tableau Help & Documentation", "https://help.tableau.com/current/pro/desktop/en-us/default.htm", "Official user guide for Tableau Desktop, calculations, and data visualization.",
        "Tableau Free Training Resources", "https://www.tableau.com/learn/training/20204", "Guided tutorials, sample workbooks, and exercises for dashboard development."
    ),
    "Excel": (
        "Microsoft Excel Help & Function Reference", "https://support.microsoft.com/en-us/excel", "Official reference guide for Excel formulas, functions, and data analysis tools.",
        "Excel Easy Interactive Tutorials", "https://www.excel-easy.com/", "Step-by-step practical exercises for formulas, PivotTables, and data visualization."
    ),

    # Backend / APIs
    "FastAPI": (
        "FastAPI Official Documentation", "https://fastapi.tiangolo.com/", "Official guide and interactive tutorial for building modern Python web APIs.",
        "FastAPI User Guide Tutorial", "https://fastapi.tiangolo.com/tutorial/", "Step-by-step hands-on guide building endpoints, validation, and database connections."
    ),
    "Flask": (
        "Flask Documentation & User Guide", "https://flask.palletsprojects.com/", "Official user guide and API reference for the Flask lightweight web framework.",
        "Flask Tutorial (Flaskr)", "https://flask.palletsprojects.com/tutorial/", "Official tutorial building a working database-backed blogging application."
    ),
    "Django": (
        "Django Documentation", "https://docs.djangoproject.com/", "Official documentation for the batteries-included Python web framework and ORM.",
        "Writing Your First Django App", "https://docs.djangoproject.com/en/stable/intro/tutorial01/", "Official hands-on walkthrough building a complete poll web application."
    ),
    "REST API": (
        "MDN Web Docs — REST Architectural Style", "https://developer.mozilla.org/en-US/docs/Glossary/REST", "Foundational architectural concepts, stateless communication, and HTTP methods in REST.",
        "Postman API Learning Center", "https://www.postman.com/api-platform/api-learning/", "Interactive hands-on guides for sending requests, inspecting responses, and testing APIs."
    ),
    "GraphQL": (
        "GraphQL Official Documentation", "https://graphql.org/learn/", "Official introduction to the GraphQL query language, schemas, resolvers, and types.",
        "How to GraphQL Free Fullstack Tutorial", "https://www.howtographql.com/", "Free fullstack tutorial teaching GraphQL fundamentals with hands-on examples."
    ),

    # Databases
    "PostgreSQL": (
        "PostgreSQL Official Documentation", "https://www.postgresql.org/docs/", "Authoritative manual for the world's most advanced open source relational database.",
        "PGExercises Interactive Queries", "https://pgexercises.com/", "Targeted SQL exercises with live evaluation against real PostgreSQL schemas."
    ),
    "MySQL": (
        "MySQL Reference Manual", "https://dev.mysql.com/doc/refman/en/", "Official reference manual for MySQL database administration, SQL syntax, and indexing.",
        "W3Schools MySQL Exercises", "https://www.w3schools.com/mysql/mysql_exercises.asp", "Interactive query challenges and syntax exercises for MySQL databases."
    ),
    "MongoDB": (
        "MongoDB Official Documentation", "https://www.mongodb.com/docs/", "Official guides for document data modeling, CRUD operations, and aggregation pipelines.",
        "MongoDB University Free Courses", "https://learn.mongodb.com/", "Free interactive training courses and hands-on lab environments from MongoDB."
    ),
    "SQLite": (
        "SQLite Documentation & SQL Reference", "https://www.sqlite.org/docs.html", "Official documentation, C/C++ interface, and SQL syntax reference for SQLite.",
        "SQL Practice with SQLite", "https://www.sql-practice.com/", "In-browser live query challenges designed around SQLite databases."
    ),
    "Redis": (
        "Redis Official Documentation", "https://redis.io/docs/latest/", "Official guides, architecture overviews, and command references for in-memory data storage.",
        "Redis University", "https://university.redis.com/", "Free interactive courses and hands-on labs covering Redis data structures and caching."
    ),

    # Cloud / DevOps
    "Docker": (
        "Docker Official Documentation", "https://docs.docker.com/", "Official user guides, Dockerfile reference, and container orchestration concepts.",
        "Docker Get Started Guide", "https://docs.docker.com/get-started/", "Hands-on walkthrough containerizing sample applications and writing Dockerfiles."
    ),
    "Kubernetes": (
        "Kubernetes Official Documentation", "https://kubernetes.io/docs/", "Official architecture guides, API reference, and kubectl command manual.",
        "Kubernetes Interactive Tutorials", "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "Browser-based interactive terminal tutorials deploying and scaling container pods."
    ),
    "AWS": (
        "AWS Official Documentation", "https://docs.aws.amazon.com/", "Official developer guides and API references for Amazon Web Services cloud products.",
        "AWS Skill Builder Free Tier", "https://explore.skillbuilder.aws/", "Free digital training courses and hands-on learning plans from Amazon."
    ),
    "Azure": (
        "Microsoft Azure Documentation", "https://learn.microsoft.com/en-us/azure/", "Official cloud architecture guides, service documentation, and CLI references.",
        "Microsoft Learn Azure Modules", "https://learn.microsoft.com/en-us/training/azure/", "Free hands-on sandbox labs and structured learning paths for Azure services."
    ),
    "Google Cloud": (
        "Google Cloud Documentation", "https://cloud.google.com/docs", "Official documentation, architecture frameworks, and quickstarts for Google Cloud.",
        "Google Cloud Skills Boost", "https://www.cloudskillsboost.google/", "Interactive learning paths and foundational cloud computing labs."
    ),
    "Git": (
        "Pro Git Book & Official Reference", "https://git-scm.com/doc", "Official reference documentation and the complete free Pro Git book by Scott Chacon.",
        "Learn Git Branching", "https://learngitbranching.js.org/", "Interactive visual and command-line sandbox for mastering Git workflows and branches."
    ),
    "GitHub": (
        "GitHub Docs", "https://docs.github.com/", "Official documentation for repository management, pull requests, and collaboration.",
        "GitHub Skills Interactive Courses", "https://skills.github.com/", "Interactive courses that teach Git and GitHub directly inside live repositories."
    ),
    "Linux": (
        "The Linux Documentation Project", "https://tldp.org/", "Comprehensive documentation, HOWTOs, and system administration guides for Linux.",
        "Linux Journey", "https://linuxjourney.com/", "Free interactive, structured learning for mastering the Linux command line and system."
    ),

    # Web / frontend
    "HTML": (
        "MDN Web Docs — HTML", "https://developer.mozilla.org/en-US/docs/Web/HTML", "Authoritative standard reference and guides for HTML5 semantic elements and accessibility.",
        "freeCodeCamp Responsive Web Design", "https://www.freecodecamp.org/learn/2022/responsive-web-design/", "Interactive step-by-step challenges building accessible web pages from scratch."
    ),
    "CSS": (
        "MDN Web Docs — CSS", "https://developer.mozilla.org/en-US/docs/Web/CSS", "Official guides and property reference for Cascading Style Sheets.",
        "Flexbox Froggy & Grid Garden", "https://flexboxfroggy.com/", "Hands-on browser games for mastering modern CSS Flexbox and Grid layouts."
    ),
    "React": (
        "React Official Documentation", "https://react.dev/", "Modern React guides, component lifecycle, state management, and hooks reference.",
        "React Interactive Tutorial", "https://react.dev/learn", "Hands-on coding challenges in browser sandboxes teaching thinking in React."
    ),
    "Node.js": (
        "Node.js Official Documentation", "https://nodejs.org/en/docs", "Official runtime documentation, standard libraries, and server-side JavaScript APIs.",
        "NodeSchool Open Source Workshops", "https://nodeschool.io/", "Terminal-based interactive workshops covering Node.js core modules and streams."
    ),

    # Core CS / engineering
    "Data Structures": (
        "Open Data Structures", "https://opendatastructures.org/", "Free, peer-reviewed textbook covering arrays, linked lists, trees, and hash tables.",
        "NeetCode Practice Roadmap", "https://neetcode.io/practice", "Interactive problem roadmap covering foundational data structures."
    ),
    "Algorithms": (
        "GeeksforGeeks Algorithms Guide", "https://www.geeksforgeeks.org/fundamentals-of-algorithms/", "Explanations and complexity analysis of sorting, searching, DP, and graph algorithms.",
        "LeetCode Explore — Algorithms", "https://leetcode.com/explore/", "Free interactive study modules and coding challenges for standard algorithms."
    ),
    "Object-Oriented Programming": (
        "MDN Object-Oriented Programming Guide", "https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Advanced_JavaScript_objects/Object-oriented_programming", "Core concepts of encapsulation, inheritance, classes, and polymorphism.",
        "Exercism Object-Oriented Exercises", "https://exercism.org/tracks/java/concepts/classes", "Hands-on exercises for modeling domains and class hierarchies."
    ),
    "OOP": (
        "MDN Object-Oriented Programming Guide", "https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Advanced_JavaScript_objects/Object-oriented_programming", "Core concepts of encapsulation, inheritance, classes, and polymorphism.",
        "Exercism Object-Oriented Exercises", "https://exercism.org/tracks/java/concepts/classes", "Hands-on exercises for modeling domains and class hierarchies."
    ),
    "GitHub Actions": (
        "GitHub Actions Documentation", "https://docs.github.com/en/actions", "Official guides, workflow syntax, and trigger events for CI/CD automation.",
        "GitHub Actions Quickstart Tutorial", "https://docs.github.com/en/actions/quickstart", "Hands-on walkthrough creating and running your first automated GitHub workflow."
    )
}


def _resolve_canonical_skill(skill):
    """Safely match a skill string against known canonical skills or aliases."""
    if not isinstance(skill, str):
        return None
    trimmed = skill.strip()
    if not trimmed:
        return None
    if trimmed in CANONICAL_SKILL_RESOURCES:
        return trimmed
    trimmed_lower = trimmed.lower()
    for key in CANONICAL_SKILL_RESOURCES:
        if key.lower() == trimmed_lower:
            return key
    alias_target = skill_aliases.get(trimmed_lower)
    if alias_target and alias_target in CANONICAL_SKILL_RESOURCES:
        return alias_target
    return None


def get_curated_resources(missing_skills):
    """
    Return curated learning resources (Documentation, Practice, YouTube Search)
    for missing skills. Safe against unknown skills, empty input, and duplicates.
    """
    if not missing_skills or not isinstance(missing_skills, list):
        return []

    resources = []
    seen_skills = set()

    for raw_skill in missing_skills:
        canonical = _resolve_canonical_skill(raw_skill)
        if not canonical or canonical in seen_skills:
            continue
        seen_skills.add(canonical)

        data = CANONICAL_SKILL_RESOURCES.get(canonical)
        if not data:
            continue

        doc_title, doc_url, doc_desc, practice_title, practice_url, practice_desc = data

        # 1. Official Documentation
        resources.append({
            "skill": canonical,
            "type": "Documentation",
            "title": doc_title,
            "url": doc_url,
            "description": doc_desc
        })

        # 2. Hands-on Practice
        resources.append({
            "skill": canonical,
            "type": "Practice",
            "title": practice_title,
            "url": practice_url,
            "description": practice_desc
        })

        # 3. YouTube Tutorial Search (explicitly labelled as a search query)
        query = quote_plus(f"{canonical} tutorial")
        resources.append({
            "skill": canonical,
            "type": "YouTube Tutorial Search",
            "title": f"{canonical} Tutorial Search",
            "url": f"https://www.youtube.com/results?search_query={query}",
            "description": f"Search results for {canonical} tutorials and video walk-throughs on YouTube."
        })

    return resources


# ============================================================
# GITHUB RESOURCE INTELLIGENCE
# ============================================================

def normalize_github_recommendation(
    item,
    missing_skill
):
    """Normalize GitHub ranking output."""

    # Current github_search.py format.
    if (
        isinstance(item, dict)
        and "repo" not in item
    ):

        repo = {
            "full_name":
                item.get(
                    "name",
                    "Unknown repository"
                ),

            "stargazers_count":
                item.get(
                    "stars",
                    0
                ),

            "description":
                item.get(
                    "description",
                    ""
                ),

            "html_url":
                item.get(
                    "url",
                    ""
                )
        }

        analysis = {
            "skill_mentions":
                item.get(
                    "skill_mentions",
                    0
                ),

            "readme_length":
                item.get(
                    "readme_length",
                    0
                )
        }

        file_evidence = {
            "dockerfile":
                item.get(
                    "dockerfile",
                    False
                ),

            "docker_compose":
                item.get(
                    "docker_compose",
                    False
                ),

            "requirements_or_config":
                item.get(
                    "requirements",
                    False
                ),

            "python_file_count":
                item.get(
                    "python_file_count",
                    0
                ),

            "python_files":
                item.get(
                    "python_files",
                    []
                ),

            "api_files":
                item.get(
                    "api_files",
                    []
                ),

            "database_files":
                item.get(
                    "database_files",
                    []
                ),

            "deployment_files":
                item.get(
                    "deployment_files",
                    []
                )
        }

        return {
            "skill": missing_skill,
            "score":
                item.get(
                    "score",
                    0
                ),
            "repo": repo,
            "analysis": analysis,
            "file_evidence":
                file_evidence,
            "readme":
                item.get(
                    "readme",
                    ""
                ),
            "context_fit":
                item.get(
                    "context_fit",
                    0
                ),
            "matched_domains":
                item.get(
                    "matched_domains",
                    []
                ),
            "unrelated_domains":
                item.get(
                    "unrelated_domains",
                    []
                ),
            "resource_intent_fit":
                item.get(
                    "resource_intent_fit",
                    0
                )
        }

    # Older nested format.
    if isinstance(item, dict):

        return {
            "skill": missing_skill,

            "score":
                item.get(
                    "resource_score",
                    item.get(
                        "score",
                        0
                    )
                ),

            "repo":
                item.get(
                    "repo",
                    {}
                ),

            "analysis":
                item.get(
                    "analysis",
                    {}
                ),

            "file_evidence":
                item.get(
                    "file_evidence",
                    {}
                ),

            "readme":
                item.get(
                    "readme",
                    ""
                ),

            "context_fit":
                item.get(
                    "context_fit",
                    0
                ),

            "matched_domains":
                item.get(
                    "matched_domains",
                    []
                ),

            "unrelated_domains":
                item.get(
                    "unrelated_domains",
                    []
                ),

            "resource_intent_fit":
                item.get(
                    "resource_intent_fit",
                    0
                )
        }

    # Legacy tuple format.
    (
        resource_score,
        repo,
        readme,
        analysis,
        file_evidence
    ) = item

    return {
        "skill": missing_skill,
        "score": resource_score,
        "repo": repo,
        "analysis": analysis,
        "file_evidence": file_evidence,
        "readme": readme,
        "context_fit": 0,
        "matched_domains": [],
        "unrelated_domains": [],
        "resource_intent_fit": 0
    }


def get_github_recommendations(
    missing_skills,
    resume_skills,
    project_context=None,
    limit=5
):
    """Search, rank, deduplicate, and select GitHub resources."""
    all_recommendations = []
    seen_repositories = set()
    for missing_skill in missing_skills:
        try:
            print(f"\nGitHub: finding relevant resources for {missing_skill}...")
            repositories = search_github(missing_skill, resume_skills)
            ranked_repositories = rank_repositories(
                repositories,
                missing_skill,
                resume_skills=resume_skills,
                project_context=project_context
            )
            for item in ranked_repositories[:3]:
                recommendation = normalize_github_recommendation(item, missing_skill)
                repo = recommendation.get("repo") or {}
                repository_name = repo.get("full_name") or repo.get("name")
                if not repository_name:
                    continue
                repository_key = repository_name.lower()
                if repository_key in seen_repositories:
                    continue
                seen_repositories.add(repository_key)
                all_recommendations.append(recommendation)
        except Exception as error:
            print(f"\nGitHub search failed for {missing_skill}: {error}")
    ranked_all = sorted(all_recommendations, key=lambda item: item.get("score", 0), reverse=True)
    selected = []
    selected_skills = set()
    for recommendation in ranked_all:
        skill = recommendation.get("skill")
        if skill in selected_skills:
            continue
        selected.append(recommendation)
        selected_skills.add(skill)
        if len(selected) >= limit:
            return selected
    for recommendation in ranked_all:
        if recommendation in selected:
            continue
        selected.append(recommendation)
        if len(selected) >= limit:
            break
    return selected


def display_github_recommendations(
    recommendations,
    limit=5
):
    """Display GitHub resources grouped by missing skill."""

    if not recommendations:
        print("\nNo suitable GitHub projects found.")
        return

    grouped = {}
    for recommendation in recommendations[:limit]:
        skill = recommendation.get("skill") or "Other"
        grouped.setdefault(skill, []).append(recommendation)

    print("\n===== RESOURCES BY SKILL =====")

    index = 1
    for skill, items in grouped.items():
        print(f"\n{skill.upper()}")
        for recommendation in items:
            repo = recommendation.get("repo") or {}
            evidence = recommendation.get("file_evidence") or {}
            name = repo.get("full_name") or repo.get("name") or "Unknown repository"
            stars = repo.get("stargazers_count", repo.get("stars", 0))
            if not isinstance(stars, (int, float)):
                stars = 0
            print(f"\n{index}. {name}")
            print(f"   Score: {recommendation.get('score', 0)}")
            print(f"   ⭐ {int(stars):,}")
            evidence_line = []
            if evidence.get("dockerfile") or evidence.get("dockerfile_present"): evidence_line.append("Dockerfile ✓")
            if evidence.get("docker_compose") or evidence.get("docker_compose_present"): evidence_line.append("Compose ✓")
            if evidence.get("python_file_count", 0) > 0: evidence_line.append("Python ✓")
            if evidence.get("requirements_or_config") or evidence.get("requirements"): evidence_line.append("Dependencies ✓")
            if evidence.get("api_files"): evidence_line.append("API ✓")
            if evidence.get("database_files"): evidence_line.append("Database ✓")
            if evidence.get("deployment_files"): evidence_line.append("Deployment ✓")
            if evidence_line: print("   " + " | ".join(evidence_line))
            print("   " + (recommendation.get("description") or repo.get("description") or "No description available."))
            url = repo.get("html_url") or repo.get("url") or recommendation.get("url")
            if url: print(f"   {url}")
            index += 1


# ============================================================
# MAIN CAREERGAP ENGINE
# ============================================================

def run_careergap(resume_text, job_text, projects):
    """Execute the deterministic CareerGap pipeline."""

    resume_skills = extract_skills(resume_text)
    job_skills = extract_skills(job_text)

    matched_skills, missing_skills = analyze_skills(resume_skills, job_skills)
    score = calculate_score(resume_skills, job_skills)

    market_data = get_market_data()
    priorities = [
        calculate_skill_priority(skill, job_text, market_data)
        for skill in missing_skills
    ]

    project_analysis = []
    for project in projects:
        project_analysis.append({
            "name": project["name"],
            "skills": analyze_project_skills(project),
            "characteristics": detect_project_characteristics(project)
        })

    project_recommendations = generate_project_upgrade_recommendations(
        projects, missing_skills
    )

    # Give GitHub ranking context from ALL existing projects.
    # The GitHub ranker expects one project-context dictionary, so we
    # combine the evidence from all projects instead of passing a list.
    combined_project_skills = []
    combined_project_characteristics = []

    for project in project_analysis:
        for skill in project["skills"]:
            if skill not in combined_project_skills:
                combined_project_skills.append(skill)
        for characteristic in project["characteristics"]:
            if characteristic not in combined_project_characteristics:
                combined_project_characteristics.append(characteristic)

    github_project_context = {
        "name": "All Existing Projects",
        "skills": combined_project_skills,
        "characteristics": combined_project_characteristics
    }

    github_recommendations = get_github_recommendations(
        missing_skills,
        resume_skills,
        project_context=github_project_context
    )

    curated_resources = get_curated_resources(missing_skills)

    return {
        "resume_skills": resume_skills,
        "job_skills": job_skills,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "score": score,
        "skill_priorities": priorities,
        "project_analysis": project_analysis,
        "project_recommendations": project_recommendations,
        "github_recommendations": github_recommendations,
        "curated_resources": curated_resources
    }


# ============================================================
# AI ADVISOR DATA
# ============================================================

def build_ai_advisor_data(results):
    """Convert deterministic results into AI evidence."""

    project_recommendations = (
        results[
            "project_recommendations"
        ]
    )

    projects_for_ai = []

    for project in results[
        "project_analysis"
    ]:

        recommendations = [
            recommendation
            for recommendation
            in project_recommendations
            if recommendation["project"]
            == project["name"]
        ]

        projects_for_ai.append({
            "name":
                project["name"],

            "skills":
                project["skills"],

            "characteristics":
                project["characteristics"],

            "recommendations": [

                {
                    "missing_skill":
                        recommendation[
                            "skill"
                        ],

                    "compatibility":
                        recommendation[
                            "compatibility"
                        ],

                    "reason":
                        recommendation[
                            "reason"
                        ],

                    "upgrade":
                        recommendation[
                            "upgrade"
                        ],

                    "resume_evidence":
                        recommendation[
                            "resume_evidence"
                        ]
                }

                for recommendation
                in recommendations
            ]
        })

    return {

        "career_gap_score":
            results["score"],

        "resume_skills":
            results["resume_skills"],

        "job_skills":
            results["job_skills"],

        "matched_skills":
            results["matched_skills"],

        "missing_skills":
            results["missing_skills"],

        "missing_skill_priority":
            results["skill_priorities"],

        "market_evidence_note": (
            "Use market demand only when evidence exists. "
            "Missing market data is unknown, not zero demand."
        ),

        "projects":
            projects_for_ai,

        "github_resources": [

            {
                "skill":
                    recommendation[
                        "skill"
                    ],

                "score":
                    recommendation[
                        "score"
                    ],

                "repository":
                    recommendation[
                        "repo"
                    ].get(
                        "full_name",
                        "Unknown repository"
                    ),

                "description":
                    recommendation[
                        "repo"
                    ].get(
                        "description",
                        ""
                    ),

                "stars":
                    recommendation[
                        "repo"
                    ].get(
                        "stargazers_count",
                        0
                    ),

                "url":
                    recommendation[
                        "repo"
                    ].get(
                        "html_url",
                        ""
                    ),

                "analysis":
                    recommendation[
                        "analysis"
                    ],

                "file_evidence":
                    recommendation[
                        "file_evidence"
                    ]
            }

            for recommendation
            in results[
                "github_recommendations"
            ]
        ]
    }


# ============================================================
# DISPLAY RESULTS
# ============================================================

def display_results(
    results,
    job_text
):
    """Display the complete CareerGap report."""

    print(
        "\n===== SKILL IMPORTANCE ====="
    )

    for skill in results[
        "job_skills"
    ]:

        importance = determine_importance(
            job_text,
            skill
        )

        print(
            f"{skill} → {importance}"
        )

    print(
        "\n===== MARKET DEMAND ====="
    )

    for priority in results[
        "skill_priorities"
    ]:

        demand = priority["market_demand"]
        demand_text = "No market data" if demand is None else f"{demand} %"
        print(
            f"{priority['skill']} → "
            f"{demand_text}"
        )

    print(
        "\n===== CAREERGAP ANALYSIS ====="
    )

    print(
        "Resume skills:",
        results["resume_skills"]
    )

    print(
        "Job skills:",
        results["job_skills"]
    )

    print(
        "Matched skills:",
        results["matched_skills"]
    )

    print(
        "Missing skills:",
        results["missing_skills"]
    )

    print(
        "CareerGap score:",
        results["score"],
        "%"
    )

    print(
        "\n===== MISSING SKILL PRIORITY ====="
    )

    if not results[
        "skill_priorities"
    ]:

        print(
            "No missing skills detected."
        )

    for priority in results[
        "skill_priorities"
    ]:

        print(
            f"{priority['skill']} → "
            f"{priority['priority']} priority "
            f"(Job: {priority['importance']}, "
            f"Market: "
            f"{'No market data' if priority['market_demand'] is None else str(priority['market_demand']) + '%'} )"
        )

    print(
        "\n===== EXISTING PROJECT ANALYSIS ====="
    )

    for project in results[
        "project_analysis"
    ]:

        print(
            f"\nProject: "
            f"{project['name']}"
        )

        print(
            "Demonstrated skills:",
            project["skills"]
        )

        print(
            "Characteristics:",
            project["characteristics"]
        )

    print(
        "\n===== PROJECT UPGRADE RECOMMENDATIONS ====="
    )

    if not results[
        "project_recommendations"
    ]:

        print(
            "No project upgrades required."
        )

    for recommendation in results[
        "project_recommendations"
    ]:

        print(
            f"\nMissing skill: "
            f"{recommendation['skill']}"
        )

        print(
            f"Project: "
            f"{recommendation['project']}"
        )

        print(
            f"Compatibility: "
            f"{recommendation['compatibility']}"
        )

        print(
            f"Why: "
            f"{recommendation['reason']}"
        )

        if recommendation["upgrade"]:

            print(
                "Suggested upgrade: "
                f"{recommendation['upgrade']}"
            )

            print(
                "Resume evidence:",
                recommendation[
                    "resume_evidence"
                ]
            )

        else:

            print(
                "Recommendation: "
                "DO NOT FORCE THIS SKILL."
            )

    display_github_recommendations(
        results[
            "github_recommendations"
        ]
    )

    # --------------------------------------------------------
    # AI CAREER ADVICE
    # --------------------------------------------------------

    print(
        "\n===== AI CAREER ADVICE ====="
    )

    try:

        advisor_data = (
            build_ai_advisor_data(
                results
            )
        )

        advice = (
            generate_career_advice(
                advisor_data
            )
        )

        print(advice)

    except Exception as error:

        print(
            f"AI advisor unavailable: "
            f"{safe_error_detail(error)}"
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        (
            resume_text,
            job_text,
            projects,
            mode
        ) = load_careergap_input()

        results = run_careergap(
            resume_text,
            job_text,
            projects
        )

        display_results(
            results,
            job_text
        )

    except Exception as error:

        print(
            "\n===== CAREERGAP ERROR ====="
        )

        print(error)