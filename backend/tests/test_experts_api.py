"""
Experts API endpointlari uchun integratsiya testlari.
Testlar: GET /api/experts/, GET /api/experts/{id}, POST, PUT, DELETE
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole
from app.models.expert import Expert
from app.services.auth import hash_password


SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_experts.db"

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
def sample_user(db_session):
    """Test uchun oddiy foydalanuvchi yaratadi."""
    user = User(
        email="testuser@example.com",
        password=hash_password("pass123"),
        role=UserRole.user,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_expert(db_session, sample_user):
    """Test uchun ekspert yaratadi."""
    expert = Expert(
        user_id=sample_user.id,
        full_name="Ali Valiyev",
        bio="Python dasturchisi",
        is_verified=False,
    )
    db_session.add(expert)
    db_session.commit()
    db_session.refresh(expert)
    return expert


class TestGetExperts:
    def test_empty_list_on_fresh_db(self, client):
        response = client.get("/api/experts/")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_list_with_expert(self, client, sample_expert):
        response = client.get("/api/experts/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["full_name"] == "Ali Valiyev"

    def test_returns_multiple_experts(self, client, db_session, sample_user):
        for i in range(3):
            db_session.add(Expert(
                user_id=sample_user.id,
                full_name=f"Ekspert {i}",
            ))
        db_session.commit()
        response = client.get("/api/experts/")
        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_response_contains_required_fields(self, client, sample_expert):
        response = client.get("/api/experts/")
        expert = response.json()[0]
        assert "id" in expert
        assert "full_name" in expert
        assert "user_id" in expert
        assert "is_verified" in expert



class TestGetExpertById:
    def test_get_existing_expert(self, client, sample_expert):
        response = client.get(f"/api/experts/{sample_expert.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_expert.id
        assert data["full_name"] == "Ali Valiyev"

    def test_get_nonexistent_expert_returns_404(self, client):
        response = client.get("/api/experts/9999")
        assert response.status_code == 404
        assert "topilmadi" in response.json()["detail"]

    def test_get_expert_bio_field(self, client, sample_expert):
        response = client.get(f"/api/experts/{sample_expert.id}")
        assert response.json()["bio"] == "Python dasturchisi"


class TestCreateExpert:
    def test_create_expert_success(self, client):
        response = client.post("/api/experts/", json={
            "full_name": "Sarvar Toshmatov",
            "bio": "Backend developer"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Sarvar Toshmatov"
        assert data["bio"] == "Backend developer"
        assert "id" in data

    def test_create_expert_without_optional_fields(self, client):
        response = client.post("/api/experts/", json={
            "full_name": "Minimal Expert"
        })
        assert response.status_code == 200
        assert response.json()["full_name"] == "Minimal Expert"

    def test_create_expert_missing_full_name_returns_422(self, client):
        response = client.post("/api/experts/", json={
            "bio": "Bio without name"
        })
        assert response.status_code == 422

    def test_created_expert_is_not_verified_by_default(self, client):
        response = client.post("/api/experts/", json={
            "full_name": "New Expert"
        })
        assert response.json()["is_verified"] is False


class TestUpdateExpert:
    def test_update_full_name(self, client, sample_expert):
        response = client.put(f"/api/experts/{sample_expert.id}", json={
            "full_name": "Yangi Ism"
        })
        assert response.status_code == 200
        assert response.json()["full_name"] == "Yangi Ism"

    def test_update_bio(self, client, sample_expert):
        response = client.put(f"/api/experts/{sample_expert.id}", json={
            "bio": "Yangilangan bio"
        })
        assert response.status_code == 200
        assert response.json()["bio"] == "Yangilangan bio"

    def test_update_is_verified(self, client, sample_expert):
        response = client.put(f"/api/experts/{sample_expert.id}", json={
            "is_verified": True
        })
        assert response.status_code == 200
        assert response.json()["is_verified"] is True

    def test_update_nonexistent_expert_returns_404(self, client):
        response = client.put("/api/experts/9999", json={"full_name": "Ghost"})
        assert response.status_code == 404



class TestDeleteExpert:
    def test_delete_existing_expert(self, client, sample_expert):
        response = client.delete(f"/api/experts/{sample_expert.id}")
        assert response.status_code == 200
        assert "o'chirildi" in response.json()["message"]

    def test_deleted_expert_not_found_after_delete(self, client, sample_expert):
        client.delete(f"/api/experts/{sample_expert.id}")
        response = client.get(f"/api/experts/{sample_expert.id}")
        assert response.status_code == 404

    def test_delete_nonexistent_expert_returns_404(self, client):
        response = client.delete("/api/experts/9999")
        assert response.status_code == 404