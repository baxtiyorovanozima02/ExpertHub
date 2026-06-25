"""
Auth API endpointlari uchun integratsiya testlari.
Testlar: /api/auth/register, /api/auth/login, /api/auth/me
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole


SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_auth.db"

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
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestRegisterEndpoint:
    def test_register_success(self, client):
        response = client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "password123",
            "role": "user"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["role"] == "user"
        assert data["is_active"] is True
        assert "id" in data
        assert "password" not in data

    def test_register_duplicate_email_returns_400(self, client):
        payload = {"email": "dup@example.com", "password": "pass", "role": "user"}
        client.post("/api/auth/register", json=payload)
        response = client.post("/api/auth/register", json=payload)
        assert response.status_code == 400
        assert "allaqachon mavjud" in response.json()["detail"]

    def test_register_admin_role(self, client):
        response = client.post("/api/auth/register", json={
            "email": "admin@example.com",
            "password": "adminpass",
            "role": "admin"
        })
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    def test_register_invalid_email_returns_422(self, client):
        response = client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "pass",
            "role": "user"
        })
        assert response.status_code == 422

    def test_register_missing_password_returns_422(self, client):
        response = client.post("/api/auth/register", json={
            "email": "user@example.com",
            "role": "user"
        })
        assert response.status_code == 422


class TestLoginEndpoint:
    def _register(self, client, email="user@test.com", password="testpass", role="user"):
        client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "role": role
        })

    def test_login_success_returns_token(self, client):
        self._register(client)
        response = client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "testpass"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self, client):
        self._register(client)
        response = client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "wrongpass"
        })
        assert response.status_code == 401
        assert "noto'g'ri" in response.json()["detail"]

    def test_login_nonexistent_user_returns_401(self, client):
        response = client.post("/api/auth/login", json={
            "email": "noone@test.com",
            "password": "pass"
        })
        assert response.status_code == 401

    def test_login_invalid_email_format_returns_422(self, client):
        response = client.post("/api/auth/login", json={
            "email": "bademail",
            "password": "pass"
        })
        assert response.status_code == 422


class TestGetMeEndpoint:
    def _get_token(self, client, email="me@test.com", password="mypass"):
        client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "role": "user"
        })
        login = client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        return login.json()["access_token"]

    def test_get_me_with_valid_token(self, client):
        token = self._get_token(client)
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@test.com"
        assert "password" not in data

    def test_get_me_without_token_returns_401(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_get_me_with_invalid_token_returns_401(self, client):
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert response.status_code == 401

    def test_get_me_returns_correct_role(self, client):
        token = self._get_token(client, "expert@test.com", "pass")
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["role"] == "user""""
Auth API endpointlari uchun integratsiya testlari.
Testlar: /api/auth/register, /api/auth/login, /api/auth/me
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole



SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_auth.db"

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
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()



class TestRegisterEndpoint:
    def test_register_success(self, client):
        response = client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "password123",
            "role": "user"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["role"] == "user"
        assert data["is_active"] is True
        assert "id" in data
        assert "password" not in data

    def test_register_duplicate_email_returns_400(self, client):
        payload = {"email": "dup@example.com", "password": "pass", "role": "user"}
        client.post("/api/auth/register", json=payload)
        response = client.post("/api/auth/register", json=payload)
        assert response.status_code == 400
        assert "allaqachon mavjud" in response.json()["detail"]

    def test_register_admin_role(self, client):
        response = client.post("/api/auth/register", json={
            "email": "admin@example.com",
            "password": "adminpass",
            "role": "admin"
        })
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    def test_register_invalid_email_returns_422(self, client):
        response = client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "pass",
            "role": "user"
        })
        assert response.status_code == 422

    def test_register_missing_password_returns_422(self, client):
        response = client.post("/api/auth/register", json={
            "email": "user@example.com",
            "role": "user"
        })
        assert response.status_code == 422

class TestLoginEndpoint:
    def _register(self, client, email="user@test.com", password="testpass", role="user"):
        client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "role": role
        })

    def test_login_success_returns_token(self, client):
        self._register(client)
        response = client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "testpass"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self, client):
        self._register(client)
        response = client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "wrongpass"
        })
        assert response.status_code == 401
        assert "noto'g'ri" in response.json()["detail"]

    def test_login_nonexistent_user_returns_401(self, client):
        response = client.post("/api/auth/login", json={
            "email": "noone@test.com",
            "password": "pass"
        })
        assert response.status_code == 401

    def test_login_invalid_email_format_returns_422(self, client):
        response = client.post("/api/auth/login", json={
            "email": "bademail",
            "password": "pass"
        })
        assert response.status_code == 422


class TestGetMeEndpoint:
    def _get_token(self, client, email="me@test.com", password="mypass"):
        client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "role": "user"
        })
        login = client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        return login.json()["access_token"]

    def test_get_me_with_valid_token(self, client):
        token = self._get_token(client)
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@test.com"
        assert "password" not in data

    def test_get_me_without_token_returns_401(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_get_me_with_invalid_token_returns_401(self, client):
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert response.status_code == 401

    def test_get_me_returns_correct_role(self, client):
        token = self._get_token(client, "expert@test.com", "pass")
        # Role ni tekshirish
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["role"] == "user"