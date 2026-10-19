import json
from unittest.mock import Mock, patch

import pytest

import github_search


class TestSearchGitHubDiagnostics:
    """Tests for search_github diagnostic logging."""

    @patch("github_search.requests.get")
    def test_search_github_logs_skill_and_queries(self, mock_get, capsys):
        """Verify search_github logs the skill and queries used."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_get.return_value = mock_response

        github_search.search_github("FastAPI", ["Python"])

        captured = capsys.readouterr()
        assert "[GitHub] Searching for skill: FastAPI" in captured.out
        assert "[GitHub] Queries for FastAPI:" in captured.out
        assert "FastAPI" in captured.out
        assert "tutorial" in captured.out

    @patch("github_search.requests.get")
    def test_search_github_logs_http_error_status(self, mock_get, capsys):
        """Verify search_github logs HTTP error status codes."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        github_search.search_github("Docker", ["Python"])

        captured = capsys.readouterr()
        assert "[GitHub] HTTP 403 for Docker" in captured.out

    @patch("github_search.requests.get")
    def test_search_github_logs_request_exception(self, mock_get, capsys):
        """Verify search_github logs request exception type without raw message."""
        import requests
        mock_get.side_effect = requests.RequestException("connection timeout")

        github_search.search_github("Docker", ["Python"])

        captured = capsys.readouterr()
        assert "[GitHub] Request failed for Docker" in captured.out
        assert "RequestException" in captured.out
        assert "connection timeout" not in captured.out

    @patch("github_search.requests.get")
    def test_search_github_logs_repo_counts(self, mock_get, capsys):
        """Verify search_github logs API repo count and post-classification count."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"full_name": "user/repo1", "name": "repo1", "description": "A FastAPI tutorial", "owner": {"login": "user"}},
                {"full_name": "user/repo2", "name": "repo2", "description": "Another FastAPI example", "owner": {"login": "user"}},
                {"full_name": "user/portfolio", "name": "portfolio", "description": "My portfolio", "owner": {"login": "user"}},
            ]
        }
        mock_get.return_value = mock_response

        github_search.search_github("FastAPI", ["Python"])

        captured = capsys.readouterr()
        assert "[GitHub] API returned" in captured.out
        assert "repositories for FastAPI" in captured.out
        assert "[GitHub] After classification filter for FastAPI:" in captured.out
        assert "->" in captured.out

    @patch("github_search.requests.get")
    def test_search_github_logs_invalid_json(self, mock_get, capsys):
        """Verify search_github logs invalid JSON responses."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        mock_get.return_value = mock_response

        github_search.search_github("FastAPI", ["Python"])

        captured = capsys.readouterr()
        assert "[GitHub] Invalid JSON response for FastAPI" in captured.out


class TestRankRepositoriesDiagnostics:
    """Tests for rank_repositories diagnostic logging."""

    @patch("github_search.get_readme")
    @patch("github_search.get_project_files")
    def test_rank_repositories_logs_stats(self, mock_get_files, mock_get_readme, capsys):
        """Verify rank_repositories logs candidate counts at each gate."""
        mock_get_readme.return_value = "This is a FastAPI tutorial for beginners. Learn FastAPI step by step."
        mock_get_files.return_value = ["main.py", "requirements.txt"]

        repos = [
            {
                "full_name": "user/fastapi-tutorial",
                "name": "fastapi-tutorial",
                "description": "A FastAPI tutorial for beginners",
                "owner": {"login": "user"},
                "stargazers_count": 100,
                "language": "Python",
                "updated_at": "2024-01-01T00:00:00Z",
                "html_url": "https://github.com/user/fastapi-tutorial",
            }
        ]

        github_search.rank_repositories(repos, "FastAPI", resume_skills=["Python"], project_context={})

        captured = capsys.readouterr()
        assert "[GitHub] Ranking repositories for skill: FastAPI" in captured.out
        assert "[GitHub] Ranking stats for FastAPI:" in captured.out
        assert "total_candidates" in captured.out
        assert "ranked" in captured.out

    @patch("github_search.get_readme")
    @patch("github_search.get_project_files")
    def test_rank_repositories_logs_filtered_counts(self, mock_get_files, mock_get_readme, capsys):
        """Verify rank_repositories logs each filter stage count."""
        mock_get_readme.return_value = "This is a component library for React."
        mock_get_files.return_value = ["index.js", "package.json"]

        repos = [
            {
                "full_name": "user/react-ui-lib",
                "name": "react-ui-lib",
                "description": "A component library for React",
                "owner": {"login": "user"},
                "stargazers_count": 500,
                "language": "JavaScript",
                "updated_at": "2024-01-01T00:00:00Z",
                "html_url": "https://github.com/user/react-ui-lib",
            }
        ]

        github_search.rank_repositories(repos, "React", resume_skills=["JavaScript"], project_context={})

        captured = capsys.readouterr()
        assert "non_resource_filtered" in captured.out
        assert "skill_relevance_failed" in captured.out
        assert "resource_intent_failed" in captured.out
        assert "meaningful_evidence_failed" in captured.out


class TestGetGitHubRecommendationsDiagnostics:
    """Tests for get_github_recommendations diagnostic logging."""

    @patch("career_gap.search_github")
    @patch("career_gap.rank_repositories")
    def test_get_github_recommendations_logs_counts(self, mock_rank, mock_search, capsys):
        """Verify get_github_recommendations logs search, rank, and final counts."""
        import career_gap

        mock_search.return_value = [
            {"full_name": "user/repo1", "name": "repo1", "description": "FastAPI tutorial", "owner": {"login": "user"}},
            {"full_name": "user/repo2", "name": "repo2", "description": "FastAPI example", "owner": {"login": "user"}},
        ]
        mock_rank.return_value = [
            {
                "name": "user/repo1",
                "score": 85,
                "description": "FastAPI tutorial",
                "stars": 100,
                "skill_mentions": 5,
                "readme_length": 1000,
                "total_files": 10,
                "dockerfile": False,
                "docker_compose": False,
                "requirements": True,
                "python_file_count": 5,
                "python_files": ["main.py"],
                "api_files": ["api.py"],
                "database_files": [],
                "deployment_files": [],
                "aws_files": [],
                "context_fit": 5,
                "matched_domains": ["web_development"],
                "unrelated_domains": [],
                "resource_intent_fit": 8,
                "updated_at": "2024-01-01T00:00:00Z",
                "url": "https://github.com/user/repo1",
            }
        ]

        result = career_gap.get_github_recommendations(
            missing_skills=["FastAPI", "Docker"],
            resume_skills=["Python"],
            project_context={"skills": ["Python"], "characteristics": ["API/Application"]},
            limit=5
        )

        captured = capsys.readouterr()
        assert "[GitHub] Found 2 repositories for FastAPI after search" in captured.out
        assert "[GitHub] Ranked 1 repositories for FastAPI" in captured.out
        assert "[GitHub] Total recommendations before deduplication:" in captured.out
        assert "[GitHub] Final selected recommendations:" in captured.out
        assert "skills:" in captured.out


class TestSearchGitHubBehavior:
    """Behavioral tests for search_github (non-diagnostic)."""

    @patch("github_search.requests.get")
    def test_search_github_returns_empty_on_404(self, mock_get):
        """search_github returns empty list on 404."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = github_search.search_github("NonExistentSkill", ["Python"])
        assert result == []

    @patch("github_search.requests.get")
    def test_search_github_deduplicates_by_full_name(self, mock_get):
        """search_github deduplicates repositories by full_name."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"full_name": "user/repo1", "name": "repo1", "description": "A tutorial", "owner": {"login": "user"}},
                {"full_name": "user/repo1", "name": "repo1", "description": "A tutorial", "owner": {"login": "user"}},
            ]
        }
        mock_get.return_value = mock_response

        result = github_search.search_github("FastAPI", ["Python"])
        assert len(result) == 1

    @patch("github_search.requests.get")
    def test_search_github_filters_profile_repos(self, mock_get):
        """search_github filters out profile-type repositories."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"full_name": "user/portfolio", "name": "portfolio", "description": "My portfolio", "owner": {"login": "user"}},
                {"full_name": "user/awesome-list", "name": "awesome-list", "description": "Awesome resources", "owner": {"login": "user"}},
                {"full_name": "user/real-project", "name": "real-project", "description": "A real project", "owner": {"login": "user"}},
            ]
        }
        mock_get.return_value = mock_response

        result = github_search.search_github("Python", ["Python"])
        assert len(result) == 1
        assert result[0]["full_name"] == "user/real-project"


class TestRankRepositoriesBehavior:
    """Behavioral tests for rank_repositories (non-diagnostic)."""

    @patch("github_search.get_readme")
    @patch("github_search.get_project_files")
    def test_rank_repositories_respects_limit(self, mock_get_files, mock_get_readme):
        """rank_repositories returns at most 3 repositories."""
        mock_get_readme.return_value = "FastAPI tutorial for beginners. Learn FastAPI step by step with examples."
        mock_get_files.return_value = ["main.py", "requirements.txt", "api.py"]

        repos = [
            {
                "full_name": f"user/repo{i}",
                "name": f"repo{i}",
                "description": "FastAPI tutorial",
                "owner": {"login": "user"},
                "stargazers_count": 100,
                "language": "Python",
                "updated_at": "2024-01-01T00:00:00Z",
                "html_url": f"https://github.com/user/repo{i}",
            }
            for i in range(10)
        ]

        result = github_search.rank_repositories(repos, "FastAPI", resume_skills=["Python"], project_context={})
        assert len(result) <= 3


class TestPostgreSQLRelevance:
    """Regression tests for PostgreSQL-specific relevance filtering."""

    def _make_repo(self, name, description, readme, files):
        """Create a mock repo with analysis and file_analysis."""
        repo = {
            "full_name": f"user/{name}",
            "name": name,
            "description": description,
            "owner": {"login": "user"},
            "stargazers_count": 100,
            "language": "Python",
            "updated_at": "2024-01-01T00:00:00Z",
            "html_url": f"https://github.com/user/{name}",
        }
        # Use actual analysis functions
        analysis = github_search.analyze_repository(repo, readme, "PostgreSQL")
        file_analysis = github_search.analyze_project_files(files)
        return repo, readme, analysis, file_analysis

    def test_postgresql_tutorial_passes(self):
        """A genuine PostgreSQL tutorial should pass all gates."""
        repo, readme, analysis, file_analysis = self._make_repo(
            name="postgresql-tutorial",
            description="PostgreSQL tutorial for beginners",
            readme="PostgreSQL tutorial. Learn PostgreSQL step by step. PostgreSQL exercises included. PostgreSQL guide for beginners.",
            files=["postgresql/schema.sql", "postgresql/setup.sql", "README.md"]
        )
        assert github_search.has_skill_relevance(repo, readme, analysis, file_analysis, "PostgreSQL") is True
        assert github_search.has_resource_intent(repo, readme, analysis, file_analysis, "PostgreSQL") is True
        assert github_search.has_meaningful_project_evidence(repo, readme, analysis, file_analysis) is True

    def test_postgres_abbreviation_passes(self):
        """A PostgreSQL tutorial using 'Postgres' abbreviation should pass."""
        repo, readme, analysis, file_analysis = self._make_repo(
            name="postgres-guide",
            description="Postgres guide for developers",
            readme="Postgres tutorial. Learn Postgres step by step. Postgres exercises and examples.",
            files=["postgres/schema.sql", "postgres/setup.sql", "README.md"]
        )
        assert github_search.has_skill_relevance(repo, readme, analysis, file_analysis, "PostgreSQL") is True
        assert github_search.has_resource_intent(repo, readme, analysis, file_analysis, "PostgreSQL") is True

    def test_cockroachdb_only_fails_postgresql(self):
        """A CockroachDB-only project mentioning PostgreSQL compatibility should fail."""
        repo, readme, analysis, file_analysis = self._make_repo(
            name="cockroach",
            description="CockroachDB distributed SQL database",
            readme="CockroachDB is a distributed SQL database. Compatible with PostgreSQL wire protocol. PostgreSQL compatible.",
            files=["pkg/sql/driver.go", "pkg/sql/parser.go", "README.md"]
        )
        # Should fail has_skill_relevance for PostgreSQL (no pg-specific files, no direct_identity)
        assert github_search.has_skill_relevance(repo, readme, analysis, file_analysis, "PostgreSQL") is False

    def test_spring_boot_only_fails_postgresql(self):
        """A Spring Boot project using H2 and generic SQL migrations should not qualify."""
        repo, readme, analysis, file_analysis = self._make_repo(
            name="spring-boot-tutorial",
            description="Spring Boot tutorial for beginners",
            readme="Spring Boot tutorial. Learn Spring Boot with JPA and H2 database. Spring Boot example.",
            files=["src/main/resources/db/migration/V1__init.sql", "pom.xml", "README.md"]
        )
        # Generic SQL migration file should not count as PostgreSQL-specific
        assert github_search.has_skill_relevance(repo, readme, analysis, file_analysis, "PostgreSQL") is False

    def test_hibernate_orm_fails_postgresql(self):
        """A Hibernate repository with PostgreSQL dialect but no learning content should fail resource intent."""
        repo, readme, analysis, file_analysis = self._make_repo(
            name="hibernate-orm",
            description="Hibernate ORM framework",
            readme="Hibernate ORM documentation. Object-relational mapping for Java. PostgreSQL dialect support.",
            files=["hibernate-core/src/main/java/org/hibernate/dialect/PostgreSQLDialect.java", "README.md"]
        )
        # Single dialect file should not pass resource intent without teaching content
        # The file path contains 'postgresql' so skill_relevance passes, but resource_intent should fail
        assert github_search.has_skill_relevance(repo, readme, analysis, file_analysis, "PostgreSQL") is True
        assert github_search.has_resource_intent(repo, readme, analysis, file_analysis, "PostgreSQL") is False

    def test_fastapi_postgresql_project_passes(self):
        """A genuine FastAPI/PostgreSQL project should remain eligible."""
        repo, readme, analysis, file_analysis = self._make_repo(
            name="fastapi-postgresql-example",
            description="FastAPI with PostgreSQL example",
            readme="FastAPI PostgreSQL tutorial. Learn to build APIs with PostgreSQL. PostgreSQL examples included.",
            files=["app/main.py", "app/database.py", "migrations/postgresql/001_init.sql", "requirements.txt"]
        )
        assert github_search.has_skill_relevance(repo, readme, analysis, file_analysis, "PostgreSQL") is True
        assert github_search.has_resource_intent(repo, readme, analysis, file_analysis, "PostgreSQL") is True

    def test_postgresql_tutorial_comparing_databases_passes(self):
        """A PostgreSQL tutorial comparing PostgreSQL with CockroachDB should pass."""
        repo, readme, analysis, file_analysis = self._make_repo(
            name="postgresql-vs-cockroachdb",
            description="PostgreSQL vs CockroachDB comparison tutorial",
            readme="PostgreSQL tutorial comparing PostgreSQL and CockroachDB. Learn PostgreSQL features. PostgreSQL vs CockroachDB differences explained. PostgreSQL exercises included.",
            files=["postgresql/schema.sql", "postgresql/comparison.sql", "README.md"]
        )
        # Should pass - PostgreSQL is the main subject, CockroachDB is only mentioned for comparison
        assert github_search.has_skill_relevance(repo, readme, analysis, file_analysis, "PostgreSQL") is True
        assert github_search.has_resource_intent(repo, readme, analysis, file_analysis, "PostgreSQL") is True

    def test_postgresql_hibernate_integration_passes(self):
        """A PostgreSQL resource demonstrating Hibernate/JPA integration should pass."""
        repo, readme, analysis, file_analysis = self._make_repo(
            name="postgresql-hibernate-guide",
            description="PostgreSQL with Hibernate ORM guide",
            readme="PostgreSQL tutorial with Hibernate ORM. Learn PostgreSQL with JPA and Hibernate. PostgreSQL examples using Spring Data JPA.",
            files=["src/main/java/com/example/PostgreSQLConfig.java", "src/main/resources/postgresql/schema.sql", "README.md"]
        )
        # Should pass - PostgreSQL is the subject, Hibernate/JPA are just the framework
        assert github_search.has_skill_relevance(repo, readme, analysis, file_analysis, "PostgreSQL") is True
        assert github_search.has_resource_intent(repo, readme, analysis, file_analysis, "PostgreSQL") is True

    def test_incidental_postgresql_mentions_rejected(self):
        """A repository with 3+ incidental PostgreSQL mentions but unrelated subject should be rejected."""
        repo, readme, analysis, file_analysis = self._make_repo(
            name="random-python-app",
            description="A random Python application",
            readme="PostgreSQL is a database. PostgreSQL is popular. PostgreSQL has many features. This app uses SQLite for storage.",
            files=["app/main.py", "app/db.py", "requirements.txt"]
        )
        # 3+ mentions in README but no PostgreSQL-specific files or identity
        # Should pass skill_relevance (mentions >= 3) but fail resource_intent
        assert github_search.has_skill_relevance(repo, readme, analysis, file_analysis, "PostgreSQL") is True
        assert github_search.has_resource_intent(repo, readme, analysis, file_analysis, "PostgreSQL") is False

    def test_other_skills_unaffected(self):
        """Other skills should not be affected by PostgreSQL changes."""
        repo, readme, analysis, file_analysis = self._make_repo(
            name="fastapi-tutorial",
            description="FastAPI tutorial for beginners",
            readme="FastAPI tutorial. Learn FastAPI step by step. FastAPI examples included.",
            files=["main.py", "requirements.txt", "api.py"]
        )
        # FastAPI should still work
        analysis_fastapi = github_search.analyze_repository(repo, readme, "FastAPI")
        assert github_search.has_skill_relevance(repo, readme, analysis_fastapi, file_analysis, "FastAPI") is True

        # Docker should still work
        analysis_docker = github_search.analyze_repository(repo, readme, "Docker")
        file_analysis_docker = github_search.analyze_project_files(["Dockerfile", "docker-compose.yml", "main.py"])
        assert github_search.has_skill_relevance(repo, readme, analysis_docker, file_analysis_docker, "Docker") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])