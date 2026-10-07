import pytest
from unittest.mock import patch, MagicMock
from tests.integration.conftest import make_supabase_response, FAKE_CLERK_ID


class TestCreateChat:

    @patch("src.routes.chatRoutes.supabase")
    def test_create_chat_success(self, mock_supabase, authenticated_client):
        fake_chat = {"id": "chat-1", "title": "My Chat", "project_id": "proj-1", "clerk_id": FAKE_CLERK_ID}
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            make_supabase_response(data=[fake_chat])
        )
        response = authenticated_client.post(
            "/api/chats",
            json={"title": "My Chat", "project_id": "proj-1"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "Chat created successfully"
        assert body["data"]["title"] == "My Chat"

    def test_create_chat_missing_title(self, authenticated_client):
        response = authenticated_client.post(
            "/api/chats",
            json={"project_id": "proj-1"}
        )
        assert response.status_code == 422

    def test_create_chat_missing_project_id(self, authenticated_client):
        response = authenticated_client.post(
            "/api/chats",
            json={"title": "No Project"}
        )
        assert response.status_code == 422

    def test_create_chat_unauthenticated(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/chats",
            json={"title": "Should Fail", "project_id": "proj-1"}
        )
        assert response.status_code == 401


class TestGetChat:

    @patch("src.routes.chatRoutes.supabase")
    def test_get_chat_success(self, mock_supabase, authenticated_client):
        fake_chat = {"id": "chat-1", "title": "My Chat", "project_id": "proj-1", "clerk_id": FAKE_CLERK_ID}
        fake_messages = [{"id": "msg-1", "content": "Hello", "role": "user"}]

        def mock_table(table_name):
            mock_tbl = MagicMock()
            if table_name == "chats":
                mock_tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = make_supabase_response(data=[fake_chat])
            elif table_name == "messages":
                mock_tbl.select.return_value.eq.return_value.order.return_value.execute.return_value = make_supabase_response(data=fake_messages)
            return mock_tbl

        mock_supabase.table.side_effect = mock_table

        response = authenticated_client.get("/api/chats/chat-1")
        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "Chat retrieved successfully"
        assert body["data"]["title"] == "My Chat"
        assert len(body["data"]["messages"]) == 1
        assert body["data"]["messages"][0]["content"] == "Hello"

    @patch("src.routes.chatRoutes.supabase")
    def test_get_chat_not_found(self, mock_supabase, authenticated_client):
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            make_supabase_response(data=[])
        )
        response = authenticated_client.get("/api/chats/nonexistent-chat-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_chat_unauthenticated(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/chats/some-chat-id")
        assert response.status_code == 401


class TestDeleteChat:

    @patch("src.routes.chatRoutes.supabase")
    def test_delete_chat_success(self, mock_supabase, authenticated_client):
        # First call: select to get project_id
        select_mock = MagicMock()
        select_mock.eq.return_value.eq.return_value.execute.return_value = make_supabase_response(data=[{"project_id": "proj-1"}])
        # Second call: delete
        delete_mock = MagicMock()
        delete_mock.eq.return_value.eq.return_value.execute.return_value = make_supabase_response(data=[{"id": "chat-1", "title": "My Chat"}])

        def table_router(table_name):
            mock = MagicMock()
            mock.select.return_value = select_mock
            mock.delete.return_value = delete_mock
            return mock

        mock_supabase.table.side_effect = table_router

        response = authenticated_client.delete("/api/chats/chat-1")
        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "Chat deleted successfully"
        assert body["data"]["title"] == "My Chat"

    @patch("src.routes.chatRoutes.supabase")
    def test_delete_chat_not_found(self, mock_supabase, authenticated_client):
        # First call: select to get project_id
        select_mock = MagicMock()
        select_mock.eq.return_value.eq.return_value.execute.return_value = make_supabase_response(data=[])
        # Second call: delete
        delete_mock = MagicMock()
        delete_mock.eq.return_value.eq.return_value.execute.return_value = make_supabase_response(data=[])

        def table_router(table_name):
            mock = MagicMock()
            mock.select.return_value = select_mock
            mock.delete.return_value = delete_mock
            return mock

        mock_supabase.table.side_effect = table_router
        response = authenticated_client.delete("/api/chats/nonexistent-chat-id")
        assert response.status_code == 404

    def test_delete_chat_unauthenticated(self, unauthenticated_client):
        response = unauthenticated_client.delete("/api/chats/some-chat-id")
        assert response.status_code == 401
