import requests
import base64
import os
from datetime import datetime, timezone

GITHUB_API = "https://api.github.com"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

HEADERS = {
    "Accept": "application/vnd.github+json"
}

if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

IGNORED_DIRECTORIES = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "site-packages",
    "dist",
    "build",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "vendor",
    "third_party",
    "third-party",
    "generated",
    "gen"
}

TECHNOLOGY_ECOSYSTEMS = {

    "docker": [
        "python",
        "machine learning",
        "pandas",
        "numpy",
        "scikit-learn",
        "sql",
        "postgresql",
        "mysql",
        "sqlite",
        "fastapi",
        "flask",
        "api",
        "jupyter"
    ],

    "python": [
        "pandas",
        "numpy",
        "machine learning",
        "scikit-learn",
        "sql",
        "fastapi",
        "flask",
        "jupyter"
    ],

    "sql": [
        "postgresql",
        "mysql",
        "sqlite",
        "database",
        "pandas",
        "python"
    ],

    "pandas": [
        "python",
        "numpy",
        "jupyter",
        "machine learning",
        "sql"
    ],

    "machine learning": [
        "python",
        "pandas",
        "numpy",
        "scikit-learn",
        "jupyter",
        "sql",
        "tensorflow",
        "pytorch"
    ]
}

PROJECT_DOMAIN_SIGNALS = {

    "customer_analytics": [
        "customer",
        "customers",
        "churn",
        "retention",
        "customer analytics",
        "customer behavior",
        "customer segmentation",
        "customer prediction",
        "customer lifetime",
        "clv"
    ],

    "machine_learning": [
        "machine learning",
        "machine-learning",
        "ml",
        "predictive",
        "prediction",
        "classification",
        "regression",
        "model training",
        "model inference",
        "scikit-learn",
        "tensorflow",
        "pytorch"
    ],

    "data_science": [
        "data science",
        "data analysis",
        "data analytics",
        "pandas",
        "numpy",
        "jupyter",
        "visualization",
        "data preprocessing",
        "exploratory data analysis",
        "eda"
    ],

    "finance": [
        "trading",
        "stock",
        "stocks",
        "forex",
        "finance",
        "financial",
        "algorithmic trading",
        "crypto",
        "cryptocurrency",
        "portfolio"
    ],

    "cybersecurity": [
        "cybersecurity",
        "security",
        "intrusion",
        "ids",
        "ips",
        "malware",
        "network security",
        "threat detection"
    ],

    "web_development": [
        "web application",
        "web app",
        "django",
        "flask",
        "fastapi",
        "frontend",
        "backend",
        "rest api",
        "website"
    ],

    "computer_vision": [
        "computer vision",
        "image classification",
        "image recognition",
        "object detection",
        "opencv",
        "image processing"
    ],

    "nlp": [
        "natural language processing",
        "nlp",
        "text classification",
        "sentiment analysis",
        "text analysis",
        "transformers",
        "language model",
        "llm"
    ],

    "devops": [
        "devops",
        "ci/cd",
        "continuous integration",
        "continuous deployment",
        "kubernetes",
        "terraform",
        "jenkins",
        "infrastructure"
    ],

    "gaming": [
        "game",
        "gaming",
        "unity",
        "unreal engine",
        "game engine",
        "minecraft"
    ],

    "virtualization": [
        "virtual machine",
        "virtualization",
        "kvm",
        "vmware",
        "virtualbox",
        "macos vm",
        "osx",
        "operating system",
        "kernel"
    ]
}

# ============================================================
# GitHub API and repository discovery
# ============================================================

def search_github(skill, user_skills):
    """Discover repositories strongly related to the target skill."""
    skill = str(skill).strip()
    skill_lower = skill.lower()

    # Avoid broad queries such as "skill python" because they return
    # popular generic repositories that only mention the skill incidentally.
    query_map = {
        "fastapi": [
            '"FastAPI" in:name,description,readme',
            '"FastAPI" backend API language:python'
        ],
        "postgresql": [
            '"PostgreSQL" in:name,description,readme',
            '"PostgreSQL" backend database'
        ],
        "docker": [
            '"Docker" in:name,description,readme',
            '"Docker" containerized application'
        ],
        "aws": [
            '"AWS" in:name,description,readme',
            '"AWS" deployment backend'
        ],
        "javascript": [
            '"JavaScript" in:name,description,readme language:JavaScript',
            '"JavaScript" frontend application'
        ],
        "typescript": [
            '"TypeScript" in:name,description,readme language:TypeScript',
            '"TypeScript" frontend application'
        ],
        "html": [
            '"HTML" in:name,description,readme language:HTML',
            '"HTML" frontend website'
        ],
        "css": [
            '"CSS" in:name,description,readme language:CSS',
            '"CSS" frontend styling'
        ],
        "react": [
            '"React" in:name,description,readme',
            '"React" frontend application language:JavaScript'
        ]
    }

    queries = query_map.get(
        skill_lower,
        [f'"{skill}" in:name,description,readme']
    )

    repositories = []
    seen = set()

    for query in queries:
        url = f'{GITHUB_API}/search/repositories'
        params = {
            'q': query,
            'per_page': 10,
            'sort': 'stars',
            'order': 'desc'
        }
        try:
            response = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=10
            )
        except requests.RequestException:
            continue

        if response.status_code != 200:
            continue

        try:
            data = response.json()
        except ValueError:
            continue

        for repo in data.get('items', []):
            full_name = repo.get('full_name')
            if full_name and full_name not in seen:
                repositories.append(repo)
                seen.add(full_name)

    # Remove obvious non-project resources before expensive README/tree calls.
    repositories = [
        repo for repo in repositories
        if classify_repository(repo) == 'project'
    ]

    # Prefer repositories whose name or description directly identifies the skill.
    def discovery_key(repo):
        name = (repo.get('name') or '').lower()
        description = (repo.get('description') or '').lower()
        direct = int(skill_lower in name or skill_lower in description)
        stars = repo.get('stargazers_count', 0)
        return (direct, stars)

    repositories.sort(key=discovery_key, reverse=True)
    return repositories[:10]


def get_readme(repo):
    owner = repo.get('owner', {}).get('login')
    name = repo.get('name')
    if not owner or not name:
        return ''
    url = f'{GITHUB_API}/repos/{owner}/{name}/readme'
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
    except requests.RequestException:
        return ''
    if response.status_code != 200:
        return ''
    try:
        data = response.json()
    except ValueError:
        return ''
    content = data.get('content', '')
    if not content:
        return ''
    try:
        return base64.b64decode(content).decode('utf-8', errors='ignore')
    except Exception:
        return ''

def get_default_branch_sha(repo):
    owner = repo.get('owner', {}).get('login')
    name = repo.get('name')
    branch = repo.get('default_branch')
    if not owner or not name or (not branch):
        return None
    url = f'{GITHUB_API}/repos/{owner}/{name}/git/ref/heads/{branch}'
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    return data.get('object', {}).get('sha')

def get_project_files(repo):
    owner = repo.get('owner', {}).get('login')
    name = repo.get('name')
    if not owner or not name:
        return []
    sha = get_default_branch_sha(repo)
    if not sha:
        return []
    url = f'{GITHUB_API}/repos/{owner}/{name}/git/trees/{sha}'
    try:
        response = requests.get(url, params={'recursive': '1'}, headers=HEADERS, timeout=20)
    except requests.RequestException:
        return []
    if response.status_code != 200:
        return []
    try:
        data = response.json()
    except ValueError:
        return []
    files = []
    for item in data.get('tree', []):
        if item.get('type') != 'blob':
            continue
        path = item.get('path', '')
        if path:
            files.append(path)
    return files

def filter_project_files(files):
    result = []
    for path in files:
        parts = path.lower().split('/')
        if any((directory in IGNORED_DIRECTORIES for directory in parts)):
            continue
        result.append(path)
    return result

def classify_repository(repo):
    name = repo.get('name', '').lower()
    description = (repo.get('description') or '').lower()
    owner = repo.get('owner', {}).get('login', '').lower()
    combined = name + ' ' + description
    if name == owner:
        return 'profile'
    if name in {'portfolio', 'resume', 'cv', 'personal-website', 'personal-site'}:
        return 'profile'
    if name.startswith('awesome-') or any((word in combined for word in ['roadmap', 'cheatsheet', 'cheat sheet', 'awesome list', 'collection of resources', 'resource collection', 'book collection', 'interview questions'])):
        return 'collection'
    return 'project'

# ============================================================
# Repository analysis
# ============================================================

def analyze_repository(repo, readme, skill):
    skill_lower = skill.lower()
    name = repo.get('name', '').lower()
    description = (repo.get('description') or '').lower()
    readme_lower = readme.lower()
    skill_mentions = readme_lower.count(skill_lower) + description.count(skill_lower)
    learning_signals = [signal for signal in ['learn', 'learning', 'beginner', 'guide', 'tutorial', 'documentation', 'step by step', 'getting started', 'example', 'explained'] if signal in readme_lower]
    project_signals = [signal for signal in ['project', 'application', 'implementation', 'example', 'build', 'deployment', 'installation', 'usage', 'configuration', 'setup', 'getting started', 'run locally', 'features'] if signal in readme_lower]
    return {'skill_mentions': skill_mentions, 'skill_in_name': skill_lower in name, 'skill_in_description': skill_lower in description, 'learning_signals': learning_signals, 'project_signals': project_signals, 'readme_length': len(readme)}

def analyze_project_files(files):
    files = filter_project_files(files)
    lower_files = [path.lower() for path in files]
    dockerfile = any((path.split('/')[-1] == 'dockerfile' for path in lower_files))
    docker_compose = any((path.endswith('docker-compose.yml') or path.endswith('docker-compose.yaml') or path.endswith('compose.yml') or path.endswith('compose.yaml') for path in lower_files))
    dependency_names = {'requirements.txt', 'pyproject.toml', 'pipfile', 'environment.yml', 'package.json', 'pom.xml', 'build.gradle'}
    requirements = any((path.split('/')[-1] in dependency_names for path in lower_files))
    python_files = [path for path in files if path.lower().endswith('.py')]
    api_names = {'app.py', 'main.py', 'api.py', 'server.py', 'routes.py', 'router.py'}
    api_directories = {'api', 'routes', 'routers', 'endpoints', 'server'}
    api_files = []
    for path in files:
        parts = path.lower().split('/')
        if parts[-1] in api_names or any((directory in api_directories for directory in parts[:-1])):
            api_files.append(path)
    database_files = []
    database_names = {'schema', 'database', 'db', 'models', 'migration', 'migrations'}
    database_technologies = {'postgres', 'postgresql', 'mysql', 'mongodb', 'sqlite'}
    for path in files:
        lower_path = path.lower()
        parts = lower_path.split('/')
        filename = parts[-1]
        if filename.endswith('.sql'):
            database_files.append(path)
        elif any((directory in database_names for directory in parts[:-1])):
            database_files.append(path)
        elif any((technology in lower_path for technology in database_technologies)):
            database_files.append(path)
    deployment_files = []
    deployment_names = {'dockerfile', 'docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml'}
    deployment_directories = {'deployment', 'deploy', 'kubernetes', 'k8s', 'helm', 'terraform'}
    for path in files:
        lower_path = path.lower()
        parts = lower_path.split('/')
        filename = parts[-1]
        if filename in deployment_names:
            deployment_files.append(path)
        elif any((directory in deployment_directories for directory in parts[:-1])):
            deployment_files.append(path)
    return {'files': files, 'total_files': len(files), 'dockerfile_present': dockerfile, 'docker_compose_present': docker_compose, 'requirements_present': requirements, 'python_file_count': len(python_files), 'python_files': python_files[:10], 'api_files': api_files[:10], 'database_files': database_files[:10], 'deployment_files': deployment_files[:10]}

# ============================================================
# Technology and project-domain detection
# ============================================================

def _normalise(value):
    return str(value).lower().strip()

def count_technology_matches(searchable_text, technologies):
    matches = 0
    for technology in technologies:
        if technology in searchable_text:
            matches += 1
    return matches

def detect_project_domains(project_context):
    text_parts = []
    name = project_context.get('name', '')
    description = project_context.get('description', '')
    characteristics = project_context.get('characteristics', [])
    skills = project_context.get('skills', [])
    text_parts.append(_normalise(name))
    text_parts.append(_normalise(description))
    for item in characteristics:
        text_parts.append(_normalise(item))
    for item in skills:
        text_parts.append(_normalise(item))
    project_text = ' '.join(text_parts)
    detected_domains = []
    for domain, signals in PROJECT_DOMAIN_SIGNALS.items():
        signal_count = 0
        for signal in signals:
            if signal in project_text:
                signal_count += 1
        if signal_count > 0:
            detected_domains.append(domain)
    return detected_domains

def detect_repository_domains(repo, readme):
    repo_text = _normalise(repo.get('name', '')) + ' ' + _normalise(repo.get('description', '')) + ' ' + _normalise(readme)
    detected_domains = []
    for domain, signals in PROJECT_DOMAIN_SIGNALS.items():
        signal_count = 0
        for signal in signals:
            if signal in repo_text:
                signal_count += 1
        if signal_count > 0:
            detected_domains.append(domain)
    return detected_domains

def calculate_project_context_fit(repo, readme, project_context=None):
    """
    Measures how closely a GitHub resource matches the
    user's existing project context.

    This is deliberately separate from technical skill
    relevance. A repository can teach Docker very well while
    still being a poor contextual match for the user's project.
    """
    if not project_context:
        return {'score': 0, 'matched_domains': [], 'unrelated_domains': []}
    repo_domains = set(detect_repository_domains(repo, readme))
    project_domains = set(detect_project_domains(project_context))
    matched_domains = sorted(project_domains.intersection(repo_domains))
    unrelated_domains = sorted(repo_domains.intersection({'finance', 'cybersecurity', 'gaming', 'virtualization'}))
    score = 0
    if len(matched_domains) >= 3:
        score = 10
    elif len(matched_domains) == 2:
        score = 8
    elif len(matched_domains) == 1:
        score = 5
    if unrelated_domains and (not matched_domains):
        score = 0
    return {'score': score, 'matched_domains': matched_domains, 'unrelated_domains': unrelated_domains}

def calculate_resource_intent_fit(repo, readme, skill, project_context=None):
    """
    Determines whether the resource makes sense for learning
    the missing skill in the context of the existing project.
    """
    if not project_context:
        return 0
    text = _normalise(repo.get('name', '')) + ' ' + _normalise(repo.get('description', '')) + ' ' + _normalise(readme)
    skill_lower = _normalise(skill)
    project_skills = [_normalise(item) for item in project_context.get('skills', [])]
    project_domains = detect_project_domains(project_context)
    score = 0
    if skill_lower in text:
        score += 3
    technology_matches = 0
    for project_skill in project_skills:
        if project_skill in text:
            technology_matches += 1
    if technology_matches >= 4:
        score += 4
    elif technology_matches >= 2:
        score += 3
    elif technology_matches >= 1:
        score += 1
    context_fit = calculate_project_context_fit(repo, readme, project_context)
    if context_fit['score'] >= 8:
        score += 3
    elif context_fit['score'] >= 5:
        score += 2
    return min(score, 10)

# ============================================================
# Repository scoring
# Each helper calculates one independent evidence category.
# ============================================================

def _score_basic_relevance(analysis):
    score_delta = 0
    relevance = 0
    if analysis.get('skill_in_name'):
        relevance += 8
    if analysis.get('skill_in_description'):
        relevance += 5
    mentions = analysis.get('skill_mentions', 0)
    if mentions >= 10:
        relevance += 7
    elif mentions >= 5:
        relevance += 5
    elif mentions >= 2:
        relevance += 3
    elif mentions >= 1:
        relevance += 2
    score_delta += min(relevance, 20)
    return score_delta

def _score_project_fit(searchable_text, target_skill, project_context, file_analysis):
    score_delta = 0
    project_fit = 0
    project_skills = [_normalise(item) for item in project_context.get('skills', [])]
    project_characteristics = [_normalise(item) for item in project_context.get('characteristics', [])]
    project_matches = count_technology_matches(searchable_text, project_skills)
    if project_matches >= 5:
        project_fit += 13
    elif project_matches >= 4:
        project_fit += 11
    elif project_matches >= 3:
        project_fit += 9
    elif project_matches >= 2:
        project_fit += 6
    elif project_matches >= 1:
        project_fit += 3
    related_technologies = TECHNOLOGY_ECOSYSTEMS.get(target_skill, [])
    ecosystem_matches = count_technology_matches(searchable_text, related_technologies)
    if ecosystem_matches >= 7:
        project_fit += 8
    elif ecosystem_matches >= 5:
        project_fit += 6
    elif ecosystem_matches >= 3:
        project_fit += 4
    elif ecosystem_matches >= 2:
        project_fit += 3
    elif ecosystem_matches >= 1:
        project_fit += 1
    characteristic_matches = count_technology_matches(searchable_text, project_characteristics)
    if characteristic_matches >= 2:
        project_fit += 3
    elif characteristic_matches == 1:
        project_fit += 2
    if 'python' in project_skills and file_analysis.get('python_file_count', 0) > 0:
        project_fit += 2
    if 'sql' in project_skills and file_analysis.get('database_files'):
        project_fit += 2
    score_delta += min(project_fit, 25)
    return score_delta

def _score_domain_fit(repo, project_context, searchable_text):
    score_delta = 0
    domain_fit = 0
    project_domains = detect_project_domains(project_context)
    repository_domains = detect_repository_domains(repo, repo.get('_readme_text', ''))
    matching_domains = set(project_domains).intersection(repository_domains)
    if len(matching_domains) >= 3:
        domain_fit += 15
    elif len(matching_domains) == 2:
        domain_fit += 11
    elif len(matching_domains) == 1:
        domain_fit += 7
    unrelated_domains = {'finance', 'cybersecurity', 'gaming', 'virtualization'}
    unrelated_matches = set(repository_domains).intersection(unrelated_domains)
    project_is_data_or_ml = 'machine_learning' in project_domains or 'data_science' in project_domains or 'customer_analytics' in project_domains
    if project_is_data_or_ml and unrelated_matches and (not matching_domains):
        domain_fit -= 8
    score_delta += max(0, min(domain_fit, 15))
    return score_delta

def _score_ecosystem_fit(resume_skills, searchable_text, file_analysis):
    score_delta = 0
    ecosystem_fit = 0
    resume_normalised = [_normalise(item) for item in resume_skills]
    resume_matches = count_technology_matches(searchable_text, resume_normalised)
    if resume_matches >= 5:
        ecosystem_fit += 9
    elif resume_matches >= 4:
        ecosystem_fit += 8
    elif resume_matches >= 3:
        ecosystem_fit += 6
    elif resume_matches >= 2:
        ecosystem_fit += 4
    elif resume_matches >= 1:
        ecosystem_fit += 2
    if file_analysis.get('python_file_count', 0) > 0 and 'python' in resume_normalised:
        ecosystem_fit += 2
    if file_analysis.get('database_files') and 'sql' in resume_normalised:
        ecosystem_fit += 2
    if file_analysis.get('requirements_present'):
        ecosystem_fit += 1
    score_delta += min(ecosystem_fit, 15)
    return score_delta

def _score_learning(analysis):
    score_delta = 0
    learning = 0
    readme_length = analysis.get('readme_length', 0)
    if readme_length >= 5000:
        learning += 3
    elif readme_length >= 2000:
        learning += 2
    elif readme_length >= 500:
        learning += 1
    learning_signal_count = len(analysis.get('learning_signals', []))
    if learning_signal_count >= 4:
        learning += 4
    elif learning_signal_count >= 2:
        learning += 3
    elif learning_signal_count >= 1:
        learning += 2
    project_signal_count = len(analysis.get('project_signals', []))
    if project_signal_count >= 3:
        learning += 3
    elif project_signal_count >= 1:
        learning += 2
    score_delta += min(learning, 10)
    return score_delta

def _score_technical(target_skill, file_analysis):
    score_delta = 0
    technical = 0
    if target_skill == 'docker':
        if file_analysis.get('dockerfile_present'):
            technical += 4
        if file_analysis.get('docker_compose_present'):
            technical += 3
    if file_analysis.get('requirements_present'):
        technical += 1
    if file_analysis.get('api_files'):
        technical += 1
    if file_analysis.get('database_files'):
        technical += 1
    score_delta += min(technical, 10)
    return score_delta

def _score_context_and_intent(repo, skill, project_context):
    score_delta = 0
    context_fit = calculate_project_context_fit(repo, repo.get('_readme_text', ''), project_context)
    score_delta += context_fit['score']
    resource_intent_fit = calculate_resource_intent_fit(repo, repo.get('_readme_text', ''), skill, project_context)
    score_delta += resource_intent_fit
    return score_delta

def _score_freshness_popularity(repo):
    score_delta = 0
    updated_at = repo.get('updated_at')
    if updated_at:
        try:
            updated_date = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            days = (datetime.now(timezone.utc) - updated_date).days
            if days <= 30:
                score_delta += 3
            elif days <= 90:
                score_delta += 2
            elif days <= 365:
                score_delta += 1
        except (ValueError, TypeError):
            pass
    stars = repo.get('stargazers_count', 0)
    if stars >= 10000:
        score_delta += 2
    elif stars >= 1000:
        score_delta += 1
    return score_delta

def calculate_repository_score(
    repo,
    analysis,
    file_analysis,
    skill,
    resume_skills=None,
    project_context=None,
):
    return _calculate_repository_score_impl(
        repo,
        analysis,
        file_analysis,
        skill,
        resume_skills,
        project_context,
    )

def _calculate_repository_score_impl(repo, analysis, file_analysis, skill, resume_skills=None, project_context=None):
    """
    Context-aware CareerGap score.

    Maximum = 100

    Direct skill relevance : 20
    Project technology fit : 25
    Project domain fit     : 15
    Resume ecosystem fit   : 15
    Learning value         : 10
    Technical evidence     : 10
    Maintenance            : 3
    Popularity             : 2
    Project context fit    : 10
    Resource intent fit    : 10

    The contextual signals are used to distinguish resources
    that merely teach the missing technology from resources
    that teach it in a way relevant to the user's existing
    project.
    """
    resume_skills = resume_skills or []
    project_context = project_context or {}
    score = 0
    target_skill = _normalise(skill)
    repo_name = _normalise(repo.get('name', ''))
    repo_description = _normalise(repo.get('description', ''))
    readme_text = _normalise(repo.get('_readme_text', ''))
    searchable_text = repo_name + ' ' + repo_description + ' ' + readme_text
    score += _score_basic_relevance(analysis)
    score += _score_project_fit(searchable_text, target_skill, project_context, file_analysis)
    score += _score_domain_fit(repo, project_context, searchable_text)
    score += _score_ecosystem_fit(resume_skills, searchable_text, file_analysis)
    score += _score_learning(analysis)
    score += _score_technical(target_skill, file_analysis)
    score += _score_context_and_intent(repo, skill, project_context)
    score += _score_freshness_popularity(repo)
    return min(score, 100)

# ============================================================
# Filtering, ranking, and display
# ============================================================

def has_skill_relevance(repo, readme, analysis, file_analysis, skill):
    """Require concrete evidence that a repository actually uses the target skill."""
    skill_lower = _normalise(skill)
    name = _normalise(repo.get("name", ""))
    description = _normalise(repo.get("description", ""))
    text = _normalise(readme)
    language = _normalise(repo.get("language", ""))
    skill_mentions = analysis.get("skill_mentions", 0)
    files = [str(path).lower() for path in file_analysis.get("files", [])]

    direct_identity = skill_lower in name or skill_lower in description

    if skill_lower == "javascript":
        return (language == "javascript" or any(path.endswith((".js", ".jsx", ".mjs", ".cjs")) for path in files) or (skill_mentions >= 2 and ("frontend" in text or "javascript" in text or "node" in text)))
    if skill_lower == "typescript":
        return (language == "typescript" or any(path.endswith((".ts", ".tsx", ".mts", ".cts")) for path in files) or (skill_mentions >= 2 and "typescript" in text))
    if skill_lower == "html":
        return (language == "html" or any(path.endswith(".html") for path in files) or (skill_mentions >= 2 and "html" in text))
    if skill_lower == "css":
        return (language == "css" or any(path.endswith((".css", ".scss", ".sass", ".less")) for path in files) or (skill_mentions >= 2 and "css" in text))
    if skill_lower == "react":
        return ((skill_mentions >= 2 and language in {"javascript", "typescript"}) or any(path.endswith((".jsx", ".tsx")) for path in files) or (direct_identity and skill_mentions >= 2 and "frontend" in text))
    return bool(direct_identity or skill_mentions >= 2)


def has_meaningful_project_evidence(repo, readme, analysis, file_analysis):
    description = (repo.get('description') or '').strip()
    if file_analysis.get('total_files', 0) > 0:
        return True
    if len(readme) >= 300:
        return True
    if len(analysis.get('project_signals', [])) >= 2:
        return True
    if len(description) >= 120:
        return True
    return False

def rank_repositories(
    repositories,
    skill,
    resume_skills=None,
    project_context=None
):
    """
    Analyze and rank a limited set of strong GitHub candidates.

    Expensive API calls are capped to the top 5 candidates. This keeps
    CareerGap responsive while preserving repository evidence analysis.
    """
    ranked = []

    # Search results are already ordered by popularity. Inspect only the
    # strongest candidates instead of every returned repository.
    candidates = repositories[:5]

    for repo in candidates:

        if classify_repository(repo) in {'profile', 'collection'}:
            continue

        readme = get_readme(repo)
        analysis = analyze_repository(
            repo,
            readme,
            skill
        )

        files = get_project_files(repo)
        file_analysis = analyze_project_files(files)

        if not has_skill_relevance(repo, readme, analysis, file_analysis, skill):
            continue

        if not has_meaningful_project_evidence(
            repo,
            readme,
            analysis,
            file_analysis
        ):
            continue

        repo_for_scoring = dict(repo)
        repo_for_scoring['_readme_text'] = readme

        score = calculate_repository_score(
            repo_for_scoring,
            analysis,
            file_analysis,
            skill,
            resume_skills=resume_skills,
            project_context=project_context
        )

        context_fit = calculate_project_context_fit(
            repo,
            readme,
            project_context
        )

        resource_intent_fit = calculate_resource_intent_fit(
            repo,
            readme,
            skill,
            project_context
        )

        ranked.append({
            'name': repo.get('full_name'),
            'score': score,
            'description': repo.get('description') or '',
            'stars': repo.get('stargazers_count', 0),
            'skill_mentions': analysis.get('skill_mentions', 0),
            'readme_length': analysis.get('readme_length', 0),
            'total_files': file_analysis.get('total_files', 0),
            'dockerfile': file_analysis.get(
                'dockerfile_present',
                False
            ),
            'docker_compose': file_analysis.get(
                'docker_compose_present',
                False
            ),
            'requirements': file_analysis.get(
                'requirements_present',
                False
            ),
            'python_file_count': file_analysis.get(
                'python_file_count',
                0
            ),
            'python_files': file_analysis.get(
                'python_files',
                []
            ),
            'api_files': file_analysis.get(
                'api_files',
                []
            ),
            'database_files': file_analysis.get(
                'database_files',
                []
            ),
            'deployment_files': file_analysis.get(
                'deployment_files',
                []
            ),
            'context_fit': context_fit.get(
                'score',
                0
            ),
            'matched_domains': context_fit.get(
                'matched_domains',
                []
            ),
            'unrelated_domains': context_fit.get(
                'unrelated_domains',
                []
            ),
            'resource_intent_fit': resource_intent_fit,
            'updated_at': repo.get('updated_at'),
            'url': repo.get('html_url')
        })

    def ranking_key(item):
        matched_count = len(
            item.get('matched_domains', [])
        )
        unrelated_count = len(
            item.get('unrelated_domains', [])
        )

        return (
            item.get('context_fit', 0),
            matched_count,
            -unrelated_count,
            item.get('resource_intent_fit', 0),
            item.get('score', 0),
            item.get('skill_mentions', 0),
            item.get('stars', 0)
        )

    ranked.sort(
        key=ranking_key,
        reverse=True
    )

    return ranked


def display_recommendations(ranked, discovered_count):
    print(f'\nFound {discovered_count} repositories')
    print(f'Analyzed {len(ranked)} suitable projects')
    print('\n===== TOP GITHUB RESOURCES =====')
    if not ranked:
        print('No suitable GitHub projects found.')
        return
    for index, repo in enumerate(ranked[:5], start=1):
        evidence = []
        if repo.get('dockerfile'):
            evidence.append('Dockerfile ✓')
        if repo.get('docker_compose'):
            evidence.append('Compose ✓')
        if repo.get('python_file_count', 0) > 0:
            evidence.append('Python ✓')
        if repo.get('requirements'):
            evidence.append('Dependencies ✓')
        if repo.get('api_files'):
            evidence.append('API ✓')
        if repo.get('database_files'):
            evidence.append('Database ✓')
        if repo.get('deployment_files'):
            evidence.append('Deployment ✓')
        print(f"\n{index}. {repo.get('name', 'Unknown repository')}")
        print(f"   Relevance Score: {repo.get('score', 0)}/100")
        print(f"   ⭐ {repo.get('stars', 0):,}")
        description = repo.get('description', '')
        if description:
            print(f'   {description}')
        if evidence:
            print('   ' + ' | '.join(evidence))
        print(f"   Context Fit: {repo.get('context_fit', 0)}/10")
        matched_domains = repo.get('matched_domains', [])
        if matched_domains:
            print('   Matched Domains: ' + ', '.join(matched_domains))
        unrelated_domains = repo.get('unrelated_domains', [])
        if unrelated_domains:
            print('   Unrelated Domains: ' + ', '.join(unrelated_domains))
        print(f"   Resource Intent Fit: {repo.get('resource_intent_fit', 0)}/10")
        print(f"   {repo.get('url', '')}")
if __name__ == '__main__':
    skill = 'Docker'
    resume_skills = ['Python', 'SQL', 'Pandas', 'Git', 'Machine Learning']
    project_context = {'name': 'Customer Churn Prediction', 'description': 'A machine learning project that predicts customer churn using Python, SQL, Pandas and Machine Learning.', 'skills': ['Python', 'SQL', 'Pandas', 'Machine Learning'], 'characteristics': ['Machine Learning']}
    print(f'Searching GitHub for: {skill}')
    repositories = search_github(skill, resume_skills)
    ranked = rank_repositories(repositories, skill, resume_skills=resume_skills, project_context=project_context)
    display_recommendations(ranked, len(repositories))
