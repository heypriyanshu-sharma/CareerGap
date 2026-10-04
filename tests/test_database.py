import json
import logging
from unittest.mock import Mock, patch

import pytest
import requests

import database
from database import DatabaseRequestError


class TestCallResumeFunctionResponseShapes:
    """Regression tests for _call_resume_function handling PostgREST RPC response shapes."""

    @patch("database.requests.post")
    def test_single_object_response(self, mock_post):
        """PostgREST returns a single object when function returns one row."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"id": "uuid-1", "title": "Test Resume"}
        mock_post.return_value = mock_response

        result = database._call_resume_function(
            "token", "create_resume", {}, "Unable to save."
        )

        assert result == {"id": "uuid-1", "title": "Test Resume"}

    @patch("database.requests.post")
    def test_list_response_with_one_item(self, mock_post):
        """PostgREST returns a list when function returns SETOF (one item)."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = [{"id": "uuid-1", "title": "Test Resume"}]
        mock_post.return_value = mock_response

        result = database._call_resume_function(
            "token", "create_resume", {}, "Unable to save."
        )

        assert result == {"id": "uuid-1", "title": "Test Resume"}

    @patch("database.requests.post")
    def test_list_response_with_multiple_items(self, mock_post):
        """PostgREST returns a list with multiple items (first is returned)."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = [
            {"id": "uuid-1", "title": "First"},
            {"id": "uuid-2", "title": "Second"},
        ]
        mock_post.return_value = mock_response

        result = database._call_resume_function(
            "token", "create_resume", {}, "Unable to save."
        )

        assert result == {"id": "uuid-1", "title": "First"}

    @patch("database.requests.post")
    def test_empty_list_response_raises(self, mock_post):
        """Empty list response is treated as failure, not success."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = []
        mock_post.return_value = mock_response

        with pytest.raises(DatabaseRequestError) as exc:
            database._call_resume_function(
                "token", "create_resume", {}, "Unable to save."
            )
        assert "Unable to save" in str(exc.value)

    @patch("database.requests.post")
    def test_null_response_raises(self, mock_post):
        """Null response is treated as failure."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = None
        mock_post.return_value = mock_response

        with pytest.raises(DatabaseRequestError) as exc:
            database._call_resume_function(
                "token", "create_resume", {}, "Unable to save."
            )
        assert "Unable to save" in str(exc.value)

    @patch("database.requests.post")
    def test_non_dict_non_list_response_raises(self, mock_post):
        """Unexpected response type (e.g., string, number) raises."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = "unexpected-string"
        mock_post.return_value = mock_response

        with pytest.raises(DatabaseRequestError) as exc:
            database._call_resume_function(
                "token", "create_resume", {}, "Unable to save."
            )
        assert "Unable to save" in str(exc.value)


class TestResumeTableGrants:
    """Verify the migration includes explicit table grants to authenticated."""

    def test_migration_contains_table_grants(self):
        """Migration should grant SELECT, INSERT, UPDATE, DELETE on resumes to authenticated."""
        with open("supabase/migrations/0001_create_resumes.sql") as f:
            content = f.read()

        assert "grant select, insert, update, delete on public.resumes to authenticated" in content.lower()


class TestDatabaseRequestErrorHandling:
    """Ensure error handling still works correctly after response shape changes."""

    @patch("database.requests.post")
    def test_postgrest_error_still_raises(self, mock_post):
        """PostgREST errors (non-ok) are still converted to DatabaseRequestError."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 403
        mock_response.json.return_value = {"code": "42501", "message": "Not authorized"}
        mock_post.return_value = mock_response

        with pytest.raises(DatabaseRequestError) as exc:
            database._call_resume_function(
                "token", "create_resume", {}, "Unable to save."
            )
        assert exc.value.status_code == 403
        assert "Not authorized" in str(exc.value)


class TestDeleteResumeResponseHandling:
    """Regression tests for delete_resume which uses a different response path."""

    @patch("database.requests.delete")
    def test_delete_returns_representation(self, mock_delete):
        """Delete with return=representation returns the deleted row."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = [{"id": "uuid-1"}]
        mock_delete.return_value = mock_response

        # Should not raise
        database.delete_resume("token", "user-1", "uuid-1")

    @patch("database.requests.delete")
    def test_delete_empty_response_raises_not_found(self, mock_delete):
        """Empty delete response raises 404."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = []
        mock_delete.return_value = mock_response

        with pytest.raises(DatabaseRequestError) as exc:
            database.delete_resume("token", "user-1", "uuid-1")
        assert exc.value.status_code == 404
        assert "not found" in str(exc.value).lower()


class TestListResumesResponseHandling:
    """Regression tests for list_resumes which uses GET."""

    @patch("database.requests.get")
    def test_list_returns_list(self, mock_get):
        """GET returns a list of resume summaries."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = [
            {"id": "uuid-1", "title": "Resume 1"},
            {"id": "uuid-2", "title": "Resume 2"},
        ]
        mock_get.return_value = mock_response

        result = database.list_resumes("token", "user-1")

        assert isinstance(result, list)
        assert len(result) == 2

    @patch("database.requests.get")
    def test_list_empty_returns_empty_list(self, mock_get):
        """Empty GET response returns empty list, not error."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = database.list_resumes("token", "user-1")

        assert result == []


class TestGetResumeResponseHandling:
    """Regression tests for get_resume which uses GET with single row expectation."""

    @patch("database.requests.get")
    def test_get_returns_single_resume(self, mock_get):
        """GET with id filter returns the resume object."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = [{"id": "uuid-1", "title": "Test"}]
        mock_get.return_value = mock_response

        result = database.get_resume("token", "user-1", "uuid-1")

        assert result == {"id": "uuid-1", "title": "Test"}

    @patch("database.requests.get")
    def test_get_not_found_returns_none(self, mock_get):
        """Empty GET response returns None."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = database.get_resume("token", "user-1", "uuid-1")

        assert result is None


class TestPostgrestErrorCodeMapping:
    """Tests for PostgREST-specific error code handling (M2)."""

    @patch("database.requests.post")
    def test_pgrst202_missing_rpc_function_maps_to_500(self, mock_post, caplog):
        """PGRST202 (missing RPC function) maps to 500 with generic message, logs server-side."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "code": "PGRST202",
            "message": "Could not find the function",
        }
        mock_post.return_value = mock_response

        with pytest.raises(DatabaseRequestError) as exc:
            database._call_resume_function(
                "token", "nonexistent_function", {}, "Unable to save."
            )
        assert exc.value.status_code == 500
        assert exc.value.detail == "Database function unavailable."

        # Verify logging: status and code only, no raw response body
        assert any(
            "PostgREST missing RPC function" in record.message
            and "status=404" in record.message
            and "code=PGRST202" in record.message
            for record in caplog.records
        )

    @patch("database.requests.post")
    def test_pgrst203_function_call_failed_maps_to_500(self, mock_post, caplog):
        """PGRST203 (function call failed) maps to 500 and logs server-side."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "code": "PGRST203",
            "message": "Function call failed",
        }
        mock_post.return_value = mock_response

        with pytest.raises(DatabaseRequestError) as exc:
            database._call_resume_function(
                "token", "create_resume", {}, "Unable to save."
            )
        assert exc.value.status_code == 500
        assert "Unable to save" in str(exc.value)

        # Verify logging: status and code only
        assert any(
            "PostgREST function call failed" in record.message
            and "status=500" in record.message
            and "code=PGRST203" in record.message
            for record in caplog.records
        )

    @patch("database.requests.post")
    def test_5xx_error_logs_server_side_sanitized(self, mock_post, caplog):
        """Generic 5xx errors are logged server-side with sanitized details (status, code)."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "code": "XX000",
            "message": "Internal server error with sensitive data",
        }
        mock_post.return_value = mock_response

        with pytest.raises(DatabaseRequestError) as exc:
            database._call_resume_function(
                "token", "create_resume", {}, "Unable to save."
            )
        assert exc.value.status_code == 500

        # Verify logging: status and code only, no raw response body
        assert any(
            "Database error" in record.message
            and "status=500" in record.message
            and "code=XX000" in record.message
            for record in caplog.records
        )
        # Verify sensitive data from response body is NOT in logs
        log_messages = [r.message for r in caplog.records]
        assert not any("Internal server error" in msg for msg in log_messages)
        assert not any("sensitive data" in msg for msg in log_messages)


class TestListResumesLimit:
    """Tests for limit parameter in list_resumes (M4)."""

    @patch("database.requests.get")
    def test_list_resumes_default_limit(self, mock_get):
        """Default limit of 50 is sent to PostgREST."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = [{"id": "uuid-1"}]
        mock_get.return_value = mock_response

        database.list_resumes("token", "user-1")

        # Verify the limit parameter was passed
        call_args = mock_get.call_args
        params = call_args[1]["params"]
        assert params["limit"] == "50"

    @patch("database.requests.get")
    def test_list_resumes_custom_limit(self, mock_get):
        """Custom limit is sent to PostgREST."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = [{"id": "uuid-1"}]
        mock_get.return_value = mock_response

        database.list_resumes("token", "user-1", limit=25)

        call_args = mock_get.call_args
        params = call_args[1]["params"]
        assert params["limit"] == "25"

    @patch("database.requests.get")
    def test_list_resumes_limit_clamped_to_max(self, mock_get):
        """Limit above MAX_RESUME_LIMIT is clamped."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = [{"id": "uuid-1"}]
        mock_get.return_value = mock_response

        database.list_resumes("token", "user-1", limit=200)

        call_args = mock_get.call_args
        params = call_args[1]["params"]
        assert params["limit"] == "100"

    @patch("database.requests.get")
    def test_list_resumes_limit_clamped_to_min(self, mock_get):
        """Limit below 1 is clamped to 1."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = [{"id": "uuid-1"}]
        mock_get.return_value = mock_response

        database.list_resumes("token", "user-1", limit=0)

        call_args = mock_get.call_args
        params = call_args[1]["params"]
        assert params["limit"] == "1"

    @patch("database.requests.get")
    def test_list_resumes_negative_limit_clamped(self, mock_get):
        """Negative limit is clamped to 1."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = [{"id": "uuid-1"}]
        mock_get.return_value = mock_response

        database.list_resumes("token", "user-1", limit=-10)

        call_args = mock_get.call_args
        params = call_args[1]["params"]
        assert params["limit"] == "1"