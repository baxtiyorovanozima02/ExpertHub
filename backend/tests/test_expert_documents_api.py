"""
Expert Documents API endpointlari uchun integratsiya testlari.
Testlar: GET /me, GET /, GET /{id}/status,
         POST /text, POST /upload, DELETE /{id}

storage, celery task va qdrant_client — mock qilinadi.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import io

from main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole
from app.models.expert import Expert
from app.models.expert_document import ExpertDocument, DocumentFileType
from app.services.auth import hash_password, create_access_token

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_expert_docs.db"

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
def expert_user(db_session):
    user = User(
        email="expert@test.com",
        password=hash_password("pass"),
        role=UserRole.expert,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def regular_user(db_session):
    user = User(
        email="noexpert@test.com",
        password=hash_password("pass"),
        role=UserRole.user,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def expert_profile(db_session, expert_user):
    expert = Expert(user_id=expert_user.id, full_name="Sardor Usmonov")
    db_session.add(expert)
    db_session.commit()
    db_session.refresh(expert)
    return expert


@pytest.fixture
def expert_token(expert_user):
    return create_access_token({"sub": str(expert_user.id), "role": "expert"})


@pytest.fixture
def regular_token(regular_user):
    return create_access_token({"sub": str(regular_user.id), "role": "user"})


@pytest.fixture
def sample_document(db_session, expert_profile):
    doc = ExpertDocument(
        expert_id=expert_profile.id,
        content="Bu test hujjati matni",
        source="manual_text",
        file_type=DocumentFileType.document,
        parse_status="done",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc



class TestGetMyProfile:
    def test_expert_can_get_own_profile(self, client, expert_token, expert_profile):
        response = client.get(
            "/api/expert/documents/me",
            headers={"Authorization": f"Bearer {expert_token}"},
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == "Sardor Usmonov"

    def test_non_expert_user_returns_404(self, client, regular_token):
        response = client.get(
            "/api/expert/documents/me",
            headers={"Authorization": f"Bearer {regular_token}"},
        )
        assert response.status_code == 404
        assert "ro'yxatdan o'tmagansiz" in response.json()["detail"]

    def test_no_auth_returns_401(self, client):
        response = client.get("/api/expert/documents/me")
        assert response.status_code == 401


class TestGetMyDocuments:
    def test_empty_list_on_no_documents(self, client, expert_token, expert_profile):
        with patch("app.api.expert_documents.storage.get_file_url", return_value=None):
            response = client.get(
                "/api/expert/documents/",
                headers={"Authorization": f"Bearer {expert_token}"},
            )
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_own_documents(self, client, expert_token, sample_document):
        with patch("app.api.expert_documents.storage.get_file_url", return_value=None):
            response = client.get(
                "/api/expert/documents/",
                headers={"Authorization": f"Bearer {expert_token}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["source"] == "manual_text"

    def test_no_auth_returns_401(self, client):
        response = client.get("/api/expert/documents/")
        assert response.status_code == 401

    def test_non_expert_returns_404(self, client, regular_token):
        response = client.get(
            "/api/expert/documents/",
            headers={"Authorization": f"Bearer {regular_token}"},
        )
        assert response.status_code == 404


class TestGetDocumentStatus:
    def test_get_status_of_own_document(self, client, expert_token, sample_document):
        response = client.get(
            f"/api/expert/documents/{sample_document.id}/status",
            headers={"Authorization": f"Bearer {expert_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_document.id
        assert data["parse_status"] == "done"
        assert data["has_content"] is True

    def test_status_of_nonexistent_document_returns_404(self, client, expert_token, expert_profile):
        response = client.get(
            "/api/expert/documents/9999/status",
            headers={"Authorization": f"Bearer {expert_token}"},
        )
        assert response.status_code == 404

    def test_no_auth_returns_401(self, client, sample_document):
        response = client.get(f"/api/expert/documents/{sample_document.id}/status")
        assert response.status_code == 401


class TestAddTextDocument:
    def test_add_text_document_success(self, client, expert_token, expert_profile):
        with patch("app.api.expert_documents.generate_document_embedding_task") as mock_task:
            mock_task.delay = MagicMock()
            response = client.post(
                "/api/expert/documents/text",
                data={"content": "Bu yangi matn hujjati", "source": "manual"},
                headers={"Authorization": f"Bearer {expert_token}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "manual"
        assert data["parse_status"] == "done"

    def test_text_document_triggers_embedding_task(self, client, expert_token, expert_profile):
        with patch("app.api.expert_documents.generate_document_embedding_task") as mock_task:
            mock_task.delay = MagicMock()
            client.post(
                "/api/expert/documents/text",
                data={"content": "Embedding test matni"},
                headers={"Authorization": f"Bearer {expert_token}"},
            )
            mock_task.delay.assert_called_once()

    def test_empty_content_returns_400(self, client, expert_token, expert_profile):
        response = client.post(
            "/api/expert/documents/text",
            data={"content": "   "},
            headers={"Authorization": f"Bearer {expert_token}"},
        )
        assert response.status_code == 400
        assert "bo'sh" in response.json()["detail"]

    def test_missing_content_returns_422(self, client, expert_token, expert_profile):
        response = client.post(
            "/api/expert/documents/text",
            data={"source": "only_source"},
            headers={"Authorization": f"Bearer {expert_token}"},
        )
        assert response.status_code == 422

    def test_non_expert_cannot_add_text(self, client, regular_token):
        response = client.post(
            "/api/expert/documents/text",
            data={"content": "Some text"},
            headers={"Authorization": f"Bearer {regular_token}"},
        )
        assert response.status_code == 404

    def test_default_source_is_manual_text(self, client, expert_token, expert_profile):
        with patch("app.api.expert_documents.generate_document_embedding_task") as mock_task:
            mock_task.delay = MagicMock()
            response = client.post(
                "/api/expert/documents/text",
                data={"content": "Manba ko'rsatilmagan matn"},
                headers={"Authorization": f"Bearer {expert_token}"},
            )
        assert response.json()["source"] == "manual_text"


class TestUploadDocument:
    def _upload(self, client, token, content=b"test content", filename="test.pdf",
                content_type="application/pdf"):
        with patch("app.api.expert_documents.storage.build_object_name", return_value="obj/key"):
            with patch("app.api.expert_documents.storage.upload_file"):
                with patch("app.api.expert_documents.storage.get_file_url", return_value="http://url"):
                    with patch("app.api.expert_documents.parse_and_embed_document_task") as mock_task:
                        mock_task.delay = MagicMock()
                        return client.post(
                            "/api/expert/documents/upload",
                            files={"file": (filename, io.BytesIO(content), content_type)},
                            headers={"Authorization": f"Bearer {token}"},
                        )

    def test_upload_pdf_success(self, client, expert_token, expert_profile):
        response = self._upload(client, expert_token)
        assert response.status_code == 200
        data = response.json()
        assert data["parse_status"] == "pending"
        assert data["original_filename"] == "test.pdf"

    def test_upload_unsupported_type_returns_400(self, client, expert_token, expert_profile):
        with patch("app.api.expert_documents.storage.build_object_name", return_value="obj"):
            with patch("app.api.expert_documents.storage.upload_file"):
                response = client.post(
                    "/api/expert/documents/upload",
                    files={"file": ("test.exe", io.BytesIO(b"exe"), "application/x-msdownload")},
                    headers={"Authorization": f"Bearer {expert_token}"},
                )
        assert response.status_code == 400
        assert "Qo'llab-quvvatlanmaydigan" in response.json()["detail"]

    def test_upload_empty_file_returns_400(self, client, expert_token, expert_profile):
        response = self._upload(client, expert_token, content=b"")
        assert response.status_code == 400
        assert "Bo'sh fayl" in response.json()["detail"]

    def test_upload_triggers_parse_task(self, client, expert_token, expert_profile):
        with patch("app.api.expert_documents.storage.build_object_name", return_value="obj/key"):
            with patch("app.api.expert_documents.storage.upload_file"):
                with patch("app.api.expert_documents.storage.get_file_url", return_value=None):
                    with patch("app.api.expert_documents.parse_and_embed_document_task") as mock_task:
                        mock_task.delay = MagicMock()
                        client.post(
                            "/api/expert/documents/upload",
                            files={"file": ("doc.pdf", io.BytesIO(b"data"), "application/pdf")},
                            headers={"Authorization": f"Bearer {expert_token}"},
                        )
                        mock_task.delay.assert_called_once()

    def test_no_auth_returns_401(self, client):
        response = client.post(
            "/api/expert/documents/upload",
            files={"file": ("f.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
        assert response.status_code == 401



class TestDeleteDocument:
    def test_delete_own_document(self, client, expert_token, sample_document):
        with patch("app.api.expert_documents.storage.delete_file"):
            with patch("app.api.expert_documents.qdrant_client.delete_document_centroid"):
                response = client.delete(
                    f"/api/expert/documents/{sample_document.id}",
                    headers={"Authorization": f"Bearer {expert_token}"},
                )
        assert response.status_code == 200
        assert "o'chirildi" in response.json()["message"]

    def test_deleted_document_not_found(self, client, expert_token, sample_document, db_session):
        with patch("app.api.expert_documents.storage.delete_file"):
            with patch("app.api.expert_documents.qdrant_client.delete_document_centroid"):
                client.delete(
                    f"/api/expert/documents/{sample_document.id}",
                    headers={"Authorization": f"Bearer {expert_token}"},
                )
        from app.models.expert_document import ExpertDocument as ED
        doc = db_session.query(ED).filter(ED.id == sample_document.id).first()
        assert doc is None

    def test_delete_nonexistent_document_returns_404(self, client, expert_token, expert_profile):
        response = client.delete(
            "/api/expert/documents/9999",
            headers={"Authorization": f"Bearer {expert_token}"},
        )
        assert response.status_code == 404

    def test_no_auth_returns_401(self, client, sample_document):
        response = client.delete(f"/api/expert/documents/{sample_document.id}")
        assert response.status_code == 401