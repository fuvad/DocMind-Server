import pytest
from unittest.mock import patch, MagicMock
from tests.integration.conftest import make_supabase_response, FAKE_CLERK_ID


class TestHealthAndRoot:

    def test_root_endpoint(self, authenticated_client):
        response = authenticated_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Docmind API"
        assert data["status"] == "running"

    def test_health_endpoint(self, authenticated_client):
        response = authenticated_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestGetProjects:

    @patch("src.routes.projectRoutes.supabase")
    def test_get_projects_authenticated(self, mock_supabase, authenticated_client):
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            make_supabase_response(data=[
                {"id": "proj-1", "name": "My Project", "clerk_id": FAKE_CLERK_ID}
            ])
        )
        response = authenticated_client.get("/api/projects")
        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "Projects retrieved successfully"
        assert len(body["data"]) == 1
        assert body["data"][0]["name"] == "My Project"

    @patch("src.routes.projectRoutes.supabase")
    def test_get_projects_returns_empty_list(self, mock_supabase, authenticated_client):
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            make_supabase_response(data=[])
        )
        response = authenticated_client.get("/api/projects")
        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_get_projects_unauthenticated(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/projects")
        assert response.status_code == 401


class TestGetProject:

    @patch("src.routes.projectRoutes.supabase")
    def test_get_project_success(self, mock_supabase, authenticated_client):
        fake_project = {"id": "proj-1", "name": "My Project", "clerk_id": FAKE_CLERK_ID}
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            make_supabase_response(data=[fake_project])
        )
        response = authenticated_client.get("/api/projects/proj-1")
        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "Project retrieved successfully"
        assert body["data"]["name"] == "My Project"

    @patch("src.routes.projectRoutes.supabase")
    def test_get_project_not_found(self, mock_supabase, authenticated_client):
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            make_supabase_response(data=[])
        )
        response = authenticated_client.get("/api/projects/proj-missing")
        assert response.status_code == 404

    def test_get_project_unauthenticated(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/projects/proj-1")
        assert response.status_code == 401


class TestCreateProject:

    @patch("src.routes.projectRoutes.supabase")
    def test_create_project_success(self, mock_supabase, authenticated_client):
        fake_project = {"id": "proj-new", "name": "Test Project", "clerk_id": FAKE_CLERK_ID}
        fake_settings = {"id": "set-1", "project_id": "proj-new", "embedding_model": "text-embedding-3-large"}

        def mock_table(table_name):
            mock_tbl = MagicMock()
            if table_name == "projects":
                mock_tbl.insert.return_value.execute.return_value = make_supabase_response(data=[fake_project])
            elif table_name == "project_settings":
                mock_tbl.insert.return_value.execute.return_value = make_supabase_response(data=[fake_settings])
            return mock_tbl

        mock_supabase.table.side_effect = mock_table

        response = authenticated_client.post(
            "/api/projects",
            json={"name": "Test Project", "description": "A test project"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "Project created successfully"
        assert body["data"]["name"] == "Test Project"

    def test_create_project_missing_name(self, authenticated_client):
        response = authenticated_client.post(
            "/api/projects",
            json={"description": "no name field"}
        )
        assert response.status_code == 422

    def test_create_project_unauthenticated(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/projects",
            json={"name": "Should Fail"}
        )
        assert response.status_code == 401


class TestDeleteProject:

    @patch("src.routes.projectRoutes.supabase")
    def test_delete_project_success(self, mock_supabase, authenticated_client):
        select_mock = MagicMock()
        select_mock.eq.return_value.eq.return_value.execute.return_value = make_supabase_response(data=[{"id": "proj-1"}])
        
        delete_mock = MagicMock()
        delete_mock.eq.return_value.eq.return_value.execute.return_value = make_supabase_response(data=[{"id": "proj-1", "name": "My Project"}])

        def table_router(table_name):
            mock = MagicMock()
            mock.select.return_value = select_mock
            mock.delete.return_value = delete_mock
            return mock

        mock_supabase.table.side_effect = table_router

        response = authenticated_client.delete("/api/projects/proj-1")
        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "Project deleted successfully"
        assert body["data"]["name"] == "My Project"

    @patch("src.routes.projectRoutes.supabase")
    def test_delete_project_not_found(self, mock_supabase, authenticated_client):
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            make_supabase_response(data=[])
        )
        response = authenticated_client.delete("/api/projects/nonexistent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_project_unauthenticated(self, unauthenticated_client):
        response = unauthenticated_client.delete("/api/projects/some-id")
        assert response.status_code == 401
