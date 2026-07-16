"""Tests de autenticación y gestión de usuarios.

Requiere BD disponible para tests completos.
Sin BD, corren tests unitarios de validación.
"""

import pytest
from uuid import UUID, uuid4
from pydantic import ValidationError

from src.modules.users.application.create import CreateUserRequest, UserDTO
from src.modules.users.application.login import LoginRequest
from src.modules.users.application.update import UpdateUserRequest
from src.modules.users.domain.types import UserRole
from src.modules.users.domain.entity import User


# ── Unit tests (sin BD) ───────────────────────────────────────


class TestUserEntity:
    def test_create_user_entity(self):
        uid = uuid4()
        user = User(
            id=uid,
            email="test@example.com",
            password_hash="hash123",
            roles=["CLIENT"],
            first_name="Juan",
            last_name="Pérez",
            ci="V-12345678",
            phone="+584141234567",
            credit_level=1,
            parts_credit_limit=150.0,
            service_credit_limit=50.0,
            credit_points=0.0,
            total_parts_debt=0.0,
            total_service_debt=0.0,
        )
        assert user.id == uid
        assert user.roles == ["CLIENT"]
        assert user.credit_level == 1
        assert user.parts_credit_limit == 150.0
        assert user.service_credit_limit == 50.0

    def test_user_defaults(self):
        user = User(
            email="test@example.com",
            password_hash="hash123",
            roles=["CLIENT"],
            first_name="A",
            last_name="B",
            ci="V-12345678",
            phone="+584141234567",
        )
        assert user.credit_level == 1
        assert user.parts_credit_limit == 150.0
        assert user.credit_points == 0.0

    def test_user_default_service_limit_is_one_third(self):
        user = User(
            email="a@b.com",
            password_hash="h",
            roles=["CLIENT"],
            first_name="A",
            last_name="B",
            ci="V-12345678",
            phone="+584141234567",
        )
        assert user.service_credit_limit == 50.0
        assert user.service_credit_limit == user.parts_credit_limit / 3


class TestCreateUserRequest:
    def test_valid_request(self):
        req = CreateUserRequest(
            email="test@example.com",
            password="secret123",
            first_name="Juan",
            last_name="Pérez",
            ci="V-12345678",
            phone="+584141234567",
            role=UserRole.CLIENT,
        )
        assert req.email == "test@example.com"
        assert req.role == UserRole.CLIENT

    def test_invalid_ci_raises(self):
        with pytest.raises(ValidationError):
            CreateUserRequest(
                email="test@example.com",
                password="secret123",
                first_name="Juan",
                last_name="Pérez",
                ci="12345",  # Formato inválido
                phone="+584141234567",
                role=UserRole.CLIENT,
            )

    def test_invalid_phone_raises(self):
        with pytest.raises(ValidationError):
            CreateUserRequest(
                email="test@example.com",
                password="secret123",
                first_name="Juan",
                last_name="Pérez",
                ci="V-12345678",
                phone="123",  # Formato inválido
                role=UserRole.CLIENT,
            )

    def test_short_password_raises(self):
        with pytest.raises(ValidationError):
            CreateUserRequest(
                email="test@example.com",
                password="ab",  # Muy corto
                first_name="Juan",
                last_name="Pérez",
                ci="V-12345678",
                phone="+584141234567",
                role=UserRole.CLIENT,
            )


class TestUserDTO:
    def test_from_entity(self):
        uid = uuid4()
        user = User(
            id=uid,
            email="test@example.com",
            password_hash="hash",
            roles=["CLIENT"],
            first_name="A",
            last_name="B",
            ci="V-12345678",
            phone="+584141234567",
        )
        dto = UserDTO.model_validate(user)
        assert dto.id == uid
        assert dto.roles == ["CLIENT"]
        assert dto.is_suspended == 0


class TestLoginRequest:
    def test_valid(self):
        req = LoginRequest(email="a@b.com", password="pass123")
        assert req.email == "a@b.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="not-an-email", password="pass123")


class TestUpdateUserRequest:
    def test_partial_update(self):
        req = UpdateUserRequest(first_name="Nuevo")
        assert req.first_name == "Nuevo"
        assert req.last_name is None


# ── Integration tests (requieren BD) ──────────────────────────


@pytest.mark.skip(reason="Requiere PostgreSQL — ejecutar con BD de prueba configurada")
class TestUserAPI:
    """Correr con BD de prueba: pytest -x tests/test_users.py::TestUserAPI"""

    @pytest.mark.asyncio
    async def test_register_user(self, client):
        response = await client.post("/users/register", json={
            "email": "new@test.com",
            "password": "testpass123",
            "first_name": "Test",
            "last_name": "User",
            "ci": "V-87654321",
            "phone": "+58411234567",
            "role": "CLIENT",
        })
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_login(self, client):
        # Primero registrar, luego login
        await client.post("/users/register", json={
            "email": "logintest@test.com",
            "password": "testpass123",
            "first_name": "Login",
            "last_name": "Test",
            "ci": "V-11111111",
            "phone": "+58411234567",
            "role": "CLIENT",
        })
        response = await client.post("/users/login", json={
            "email": "logintest@test.com",
            "password": "testpass123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
