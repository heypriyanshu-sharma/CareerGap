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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])