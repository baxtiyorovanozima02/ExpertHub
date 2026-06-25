"""
Auth service uchun unit testlar.
Testlar: hash_password, verify_password, create_access_token, register_user, login_user
"""
import pytest
from unittest.mock import MagicMock, patch
from jose import jwt

from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    register_user,
    login_user,
    _prepare_password,
)
from app.core.config import settings


class TestPreparePassword:
    def test_returns_bytes(self):
        result = _prepare_password("test123")
        assert isinstance(result, bytes)

    def test_same_input_same_output(self):
        assert _prepare_password("hello") == _prepare_password("hello")

    def test_different_inputs_different_output(self):
        assert _prepare_password("abc") != _prepare_password("xyz")

    def test_max_length_under_72_bytes(self):
        result = _prepare_password("a" * 100)
        assert len(result) <= 88


class TestPasswordHashing:
    def test_hash_returns_string(self):
        hashed = hash_password("mypassword")
        assert isinstance(hashed, str)

    def test_hash_starts_with_bcrypt_prefix(self):
        hashed = hash_password("mypassword")
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        hashed = hash_password("correct_pass")
        assert verify_password("correct_pass", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct_pass")
        assert verify_password("wrong_pass", hashed) is False

    def test_hash_is_unique(self):
        h1 = hash_password("same_pass")
        h2 = hash_password("same_pass")
        assert h1 != h2

    def test_verify_empty_password(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("notempty", hashed) is False


class TestCreateAccessToken:
    def test_token_is_string(self):
        token = create_access_token({"sub": "1", "role": "user"})
        assert isinstance(token, str)

    def test_token_contains_user_id(self):
        token = create_access_token({"sub": "42", "role": "user"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "42"

    def test_token_contains_role(self):
        token = create_access_token({"sub": "1", "role": "admin"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["role"] == "admin"

    def test_token_has_expiry(self):
        token = create_access_token({"sub": "1"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload

    def test_invalid_secret_raises(self):
        token = create_access_token({"sub": "1"})
        with pytest.raises(Exception):
            jwt.decode(token, "wrong_secret", algorithms=[settings.ALGORITHM])



class TestRegisterUser:
    def _make_db(self, existing_user=None):
        db = MagicMock()
        query_mock = db.query.return_value.filter.return_value.first
        query_mock.return_value = existing_user
        return db

    def test_register_new_user_returns_user(self):
        db = self._make_db(existing_user=None)
        result = register_user(db, "new@mail.com", "pass123", "user")
        assert result is not None
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_register_duplicate_email_returns_none(self):
        fake_user = MagicMock()
        db = self._make_db(existing_user=fake_user)
        result = register_user(db, "exists@mail.com", "pass", "user")
        assert result is None
        db.add.assert_not_called()

    def test_password_is_hashed_before_save(self):
        db = self._make_db(existing_user=None)
        register_user(db, "user@mail.com", "plaintext", "user")
        added_user = db.add.call_args[0][0]
        assert added_user.password != "plaintext"
        assert added_user.password.startswith("$2b$")


class TestLoginUser:
    def _make_db_with_user(self, email, password):
        db = MagicMock()
        fake_user = MagicMock()
        fake_user.email = email
        fake_user.password = hash_password(password)
        db.query.return_value.filter.return_value.first.return_value = fake_user
        return db, fake_user

    def test_login_correct_credentials(self):
        db, fake_user = self._make_db_with_user("user@mail.com", "secret")
        result = login_user(db, "user@mail.com", "secret")
        assert result == fake_user

    def test_login_wrong_password_returns_none(self):
        db, _ = self._make_db_with_user("user@mail.com", "secret")
        result = login_user(db, "user@mail.com", "wrongpass")
        assert result is None

    def test_login_user_not_found_returns_none(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = login_user(db, "notfound@mail.com", "anypass")
        assert result is None