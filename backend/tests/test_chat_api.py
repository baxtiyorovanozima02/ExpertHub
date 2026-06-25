"""
Chat API endpointlari uchun integratsiya testlari.
Testlar: POST /api/chat/, POST /api/chat/{id}/message, GET /api/chat/{id}/history
LLM chaqiruvi (generate_answer) mock qilinadi.
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.auth import hash_password, create_access_token


SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_chat.db"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def user(db_session):
    u = User(
        email="chatuser@example.com",
        password=hash_password("pass123"),
        role=UserRole.user,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def other_user(db_session):
    u = User(
        email="otheruser@example.com",
        password=hash_password("pass123"),
        role=UserRole.user,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def token(user):
    return create_access_token({"sub": str(user.id), "role": "user"})


@pytest.fixture
def other_token(other_user):
    return create_access_token({"sub": str(other_user.id), "role": "user"})


@pytest.fixture
def category(db_session):
    c = Category(name="Huquq")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def conversation(db_session, user, category):
    conv = Conversation(user_id=user.id, category_id=category.id)
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)
    return conv


class TestCreateConversation:
    def test_create_conversation_success(self, client, token, category):
        response = client.post(
            "/api/chat/",
            json={"category_id": category.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["category_id"] == category.id
        assert "id" in data

    def test_create_conversation_without_category(self, client, token):
        response = client.post(
            "/api/chat/",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["category_id"] is None

    def test_create_conversation_unauthenticated_returns_401(self, client):
        response = client.post("/api/chat/", json={})
        assert response.status_code == 401

    def test_conversation_belongs_to_current_user(self, client, token, user):
        response = client.post("/api/chat/", json={}, headers={"Authorization": f"Bearer {token}"})
        assert response.json()["user_id"] == user.id


class TestSendMessage:
    def test_send_message_success(self, client, token, conversation):
        with patch("app.api.chat.generate_answer", return_value="Mock javob"):
            response = client.post(
                f"/api/chat/{conversation.id}/message",
                json={"content": "Salom, savolim bor"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "assistant"
        assert data["content"] == "Mock javob"

    def test_send_message_creates_user_and_assistant_messages(self, client, db_session, token, conversation):
        with patch("app.api.chat.generate_answer", return_value="Javob matni"):
            client.post(
                f"/api/chat/{conversation.id}/message",
                json={"content": "Test savol"},
                headers={"Authorization": f"Bearer {token}"},
            )
        messages = (
            db_session.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
            .all()
        )
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Test savol"
        assert messages[1].role == "assistant"
        assert messages[1].content == "Javob matni"

    def test_send_message_calls_generate_answer_with_correct_args(self, client, conversation, token, category):
        with patch("app.api.chat.generate_answer", return_value="Javob") as mock_generate:
            client.post(
                f"/api/chat/{conversation.id}/message",
                json={"content": "Qanday savol"},
                headers={"Authorization": f"Bearer {token}"},
            )
        mock_generate.assert_called_once()
        _, kwargs = mock_generate.call_args
        assert kwargs["question"] == "Qanday savol"
        assert kwargs["category_id"] == category.id

    def test_send_message_to_nonexistent_conversation_returns_404(self, client, token):
        with patch("app.api.chat.generate_answer", return_value="Javob"):
            response = client.post(
                "/api/chat/9999/message",
                json={"content": "Savol"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 404

    def test_send_message_to_other_users_conversation_returns_404(self, client, conversation, other_token):
        with patch("app.api.chat.generate_answer", return_value="Javob"):
            response = client.post(
                f"/api/chat/{conversation.id}/message",
                json={"content": "Begona savol"},
                headers={"Authorization": f"Bearer {other_token}"},
            )
        assert response.status_code == 404

    def test_send_message_missing_content_returns_422(self, client, token, conversation):
        response = client.post(
            f"/api/chat/{conversation.id}/message",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_send_message_unauthenticated_returns_401(self, client, conversation):
        response = client.post(
            f"/api/chat/{conversation.id}/message",
            json={"content": "Savol"},
        )
        assert response.status_code == 401


class TestGetHistory:
    def test_get_history_empty(self, client, token, conversation):
        response = client.get(
            f"/api/chat/{conversation.id}/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == []
        assert data["conversation"]["id"] == conversation.id

    def test_get_history_with_messages(self, client, db_session, token, conversation):
        db_session.add(Message(conversation_id=conversation.id, role="user", content="Savol 1"))
        db_session.add(Message(conversation_id=conversation.id, role="assistant", content="Javob 1"))
        db_session.commit()

        response = client.get(
            f"/api/chat/{conversation.id}/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["content"] == "Savol 1"
        assert data["messages"][1]["content"] == "Javob 1"

    def test_get_history_messages_ordered_by_created_at(self, client, db_session, token, conversation):
        for i in range(3):
            db_session.add(Message(conversation_id=conversation.id, role="user", content=f"Xabar {i}"))
            db_session.commit()

        response = client.get(
            f"/api/chat/{conversation.id}/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        contents = [m["content"] for m in response.json()["messages"]]
        assert contents == ["Xabar 0", "Xabar 1", "Xabar 2"]

    def test_get_history_nonexistent_conversation_returns_404(self, client, token):
        response = client.get(
            "/api/chat/9999/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_get_history_other_users_conversation_returns_404(self, client, conversation, other_token):
        response = client.get(
            f"/api/chat/{conversation.id}/history",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert response.status_code == 404

    def test_get_history_unauthenticated_returns_401(self, client, conversation):
        response = client.get(f"/api/chat/{conversation.id}/history")
        assert response.status_code == 401