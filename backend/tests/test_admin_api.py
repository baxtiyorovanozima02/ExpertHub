"""
Admin API endpointlari uchun integratsiya testlari.
Testlar: GET /api/admin/experts/, PUT /api/admin/experts/{id}/verify/, GET /api/admin/stats/
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole
from app.models.expert import Expert
from app.models.category import Category
from app.models.expert_document import ExpertDocument
from app.services.auth import hash_password, create_access_token


SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_admin.db"

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
def admin_user(db_session):
    user = User(
        email="admin@example.com",
        password=hash_password("pass123"),
        role=UserRole.admin,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def regular_user(db_session):
    user = User(
        email="user@example.com",
        password=hash_password("pass123"),
        role=UserRole.user,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def expert_user(db_session):
    user = User(
        email="expert@example.com",
        password=hash_password("pass123"),
        role=UserRole.expert,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    return create_access_token({"sub": str(admin_user.id), "role": "admin"})


@pytest.fixture
def regular_token(regular_user):
    return create_access_token({"sub": str(regular_user.id), "role": "user"})


@pytest.fixture
def sample_expert(db_session, expert_user):
    expert = Expert(
        user_id=expert_user.id,
        full_name="Ali Valiyev",
        is_verified=False,
    )
    db_session.add(expert)
    db_session.commit()
    db_session.refresh(expert)
    return expert


class TestListExperts:
    def test_admin_can_list_experts(self, client, admin_token, sample_expert):
        response = client.get(
            "/api/admin/experts/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["full_name"] == "Ali Valiyev"

    def test_empty_list_on_fresh_db(self, client, admin_token):
        response = client.get(
            "/api/admin/experts/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_non_admin_cannot_list_experts(self, client, regular_token):
        response = client.get(
            "/api/admin/experts/",
            headers={"Authorization": f"Bearer {regular_token}"},
        )
        assert response.status_code == 403

    def test_unauthenticated_cannot_list_experts(self, client):
        response = client.get("/api/admin/experts/")
        assert response.status_code == 401


class TestVerifyExpert:
    def test_admin_can_verify_expert(self, client, admin_token, sample_expert):
        response = client.put(
            f"/api/admin/experts/{sample_expert.id}/verify/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["is_verified"] is True

    def test_verify_nonexistent_expert_returns_404(self, client, admin_token):
        response = client.put(
            "/api/admin/experts/9999/verify/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404
        assert "topilmadi" in response.json()["detail"]

    def test_non_admin_cannot_verify_expert(self, client, regular_token, sample_expert):
        response = client.put(
            f"/api/admin/experts/{sample_expert.id}/verify/",
            headers={"Authorization": f"Bearer {regular_token}"},
        )
        assert response.status_code == 403

    def test_verify_is_persisted(self, client, db_session, admin_token, sample_expert):
        client.put(
            f"/api/admin/experts/{sample_expert.id}/verify/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        db_session.refresh(sample_expert)
        assert sample_expert.is_verified is True


class TestAdminStats:
    def test_stats_on_fresh_db(self, client, admin_token):
        response = client.get(
            "/api/admin/stats/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 1
        assert data["total_experts"] == 0
        assert data["verified_experts"] == 0
        assert data["total_categories"] == 0
        assert data["total_documents"] == 0

    def test_stats_count_experts_and_verified(self, client, admin_token, sample_expert, db_session, expert_user):
        sample_expert.is_verified = True
        db_session.commit()

        response = client.get(
            "/api/admin/stats/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        assert data["total_experts"] == 1
        assert data["verified_experts"] == 1

    def test_stats_count_categories(self, client, db_session, admin_token):
        db_session.add(Category(name="Huquq"))
        db_session.add(Category(name="Tibbiyot"))
        db_session.commit()

        response = client.get(
            "/api/admin/stats/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.json()["total_categories"] == 2

    def test_stats_count_documents(self, client, db_session, admin_token, sample_expert):
        db_session.add(ExpertDocument(
            expert_id=sample_expert.id,
            source="manual_text",
            content="Test hujjat matni",
        ))
        db_session.commit()

        response = client.get(
            "/api/admin/stats/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.json()["total_documents"] == 1

    def test_non_admin_cannot_view_stats(self, client, regular_token):
        response = client.get(
            "/api/admin/stats/",
            headers={"Authorization": f"Bearer {regular_token}"},
        )
        assert response.status_code == 403

    def test_unauthenticated_cannot_view_stats(self, client):
        response = client.get("/api/admin/stats/")
        assert response.status_code == 401