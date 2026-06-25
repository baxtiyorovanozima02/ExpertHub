"""
Categories API endpointlari uchun integratsiya testlari.
Testlar: GET /api/categories/, GET /api/categories/{id}, POST, PUT, DELETE
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole
from app.models.category import Category
from app.services.auth import hash_password, create_access_token


SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_categories.db"

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
def admin_token(admin_user):
    return create_access_token({"sub": str(admin_user.id), "role": "admin"})


@pytest.fixture
def regular_token(regular_user):
    return create_access_token({"sub": str(regular_user.id), "role": "user"})


@pytest.fixture
def sample_category(db_session):
    category = Category(
        name="Huquq",
        icon="law-icon",
        description="Huquqiy savollar bo'yicha kategoriya",
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


class TestGetCategories:
    def test_empty_list_on_fresh_db(self, client):
        response = client.get("/api/categories/")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_list_with_category(self, client, sample_category):
        response = client.get("/api/categories/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Huquq"

    def test_returns_multiple_categories(self, client, db_session):
        for i in range(3):
            db_session.add(Category(name=f"Kategoriya {i}"))
        db_session.commit()
        response = client.get("/api/categories/")
        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_response_contains_required_fields(self, client, sample_category):
        response = client.get("/api/categories/")
        category = response.json()[0]
        assert "id" in category
        assert "name" in category
        assert "icon" in category
        assert "description" in category


class TestGetCategoryById:
    def test_get_existing_category(self, client, sample_category):
        response = client.get(f"/api/categories/{sample_category.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_category.id
        assert data["name"] == "Huquq"

    def test_get_nonexistent_category_returns_404(self, client):
        response = client.get("/api/categories/9999")
        assert response.status_code == 404
        assert "topilmadi" in response.json()["detail"]

    def test_get_category_description_field(self, client, sample_category):
        response = client.get(f"/api/categories/{sample_category.id}")
        assert response.json()["description"] == "Huquqiy savollar bo'yicha kategoriya"


class TestCreateCategory:
    def test_create_category_success_as_admin(self, client, admin_token):
        response = client.post(
            "/api/categories/",
            json={"name": "Tibbiyot", "icon": "med-icon", "description": "Tibbiy savollar"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Tibbiyot"
        assert data["icon"] == "med-icon"
        assert "id" in data

    def test_create_category_without_optional_fields(self, client, admin_token):
        response = client.post(
            "/api/categories/",
            json={"name": "Moliya"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Moliya"

    def test_create_category_missing_name_returns_422(self, client, admin_token):
        response = client.post(
            "/api/categories/",
            json={"icon": "no-name"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    def test_create_duplicate_name_returns_400(self, client, admin_token, sample_category):
        response = client.post(
            "/api/categories/",
            json={"name": "Huquq"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 400

    def test_non_admin_cannot_create_category(self, client, regular_token):
        response = client.post(
            "/api/categories/",
            json={"name": "Texnologiya"},
            headers={"Authorization": f"Bearer {regular_token}"},
        )
        assert response.status_code == 403

    def test_unauthenticated_cannot_create_category(self, client):
        response = client.post("/api/categories/", json={"name": "Sport"})
        assert response.status_code == 401


class TestUpdateCategory:
    def test_update_name_as_admin(self, client, admin_token, sample_category):
        response = client.put(
            f"/api/categories/{sample_category.id}",
            json={"name": "Yangi nom"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Yangi nom"

    def test_update_description(self, client, admin_token, sample_category):
        response = client.put(
            f"/api/categories/{sample_category.id}",
            json={"description": "Yangilangan tavsif"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["description"] == "Yangilangan tavsif"

    def test_update_nonexistent_category_returns_404(self, client, admin_token):
        response = client.put(
            "/api/categories/9999",
            json={"name": "Ghost"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    def test_non_admin_cannot_update_category(self, client, regular_token, sample_category):
        response = client.put(
            f"/api/categories/{sample_category.id}",
            json={"name": "Boshqa nom"},
            headers={"Authorization": f"Bearer {regular_token}"},
        )
        assert response.status_code == 403


class TestDeleteCategory:
    def test_delete_existing_category_as_admin(self, client, admin_token, sample_category):
        response = client.delete(
            f"/api/categories/{sample_category.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert "o'chirildi" in response.json()["message"]

    def test_deleted_category_not_found_after_delete(self, client, admin_token, sample_category):
        client.delete(
            f"/api/categories/{sample_category.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        response = client.get(f"/api/categories/{sample_category.id}")
        assert response.status_code == 404

    def test_delete_nonexistent_category_returns_404(self, client, admin_token):
        response = client.delete(
            "/api/categories/9999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    def test_non_admin_cannot_delete_category(self, client, regular_token, sample_category):
        response = client.delete(
            f"/api/categories/{sample_category.id}",
            headers={"Authorization": f"Bearer {regular_token}"},
        )
        assert response.status_code == 403