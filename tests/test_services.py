"""Tests del módulo de servicios.

Cubre:
- Entidad Service (no tiene campos de crédito aún)
- ServiceOrder con flag is_financed
- DTOs de servicio
"""

import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError

from src.modules.services.domain.entity import Service
from src.modules.services.application.create import (
    ServiceDTO,
    ServiceOrderDTO,
    ServiceOrderPaymentDTO,
    ServiceOrderRatingInfo,
    CreateServiceRequest,
    CreateServiceOrderRequest,
    SetQuoteRequest,
    PayServiceOrderRequest,
    RateServiceOrderRequest,
)


# ── Entity tests ──────────────────────────────────────────────


class TestServiceEntity:
    def test_create_service(self):
        wid = uuid4()
        s = Service(
            workshop_id=wid,
            service_name="Cambio de Aceite",
            service_type="MANTENIMIENTO",
            standard_price_min=30.0,
            standard_price_max=50.0,
        )
        assert s.workshop_id == wid
        assert s.service_name == "Cambio de Aceite"
        assert s.vehicle_type == "ALL"


# ── DTO tests ─────────────────────────────────────────────────


def _make_service_order_dto(**overrides) -> ServiceOrderDTO:
    defaults = dict(
        id=uuid4(),
        user_id=uuid4(),
        workshop_id=uuid4(),
        service_id=uuid4(),
        vehicle_id=uuid4(),
        service_name="Test",
        status="PENDING",
        base_price=100.0,
        created_at=datetime.now(),
        workshop_name="Taller Test",
        workshop_rif="J-12345678-9",
        workshop_address="Calle 123",
        vehicle_brand="Toyota",
        vehicle_model="Corolla",
        vehicle_license_plate="ABC-123",
        user_first_name="Juan",
        user_last_name="Pérez",
        user_ci="V-12345678",
        user_email="juan@test.com",
        final_price=100.0,
        extra_charge=0.0,
        extra_charge_note=None,
        extra_charge_status="NONE",
        price_min=0.0,
        price_max=0.0,
        notes=None,
        completed_at=None,
        delivered_at=None,
    )
    defaults.update(overrides)
    return ServiceOrderDTO(**defaults)


class TestServiceOrderDTO:
    def test_default_is_paid(self):
        dto = _make_service_order_dto()
        assert dto.is_paid is False

    def test_with_ratings(self):
        dto = _make_service_order_dto(
            status="CLOSED",
            ratings=ServiceOrderRatingInfo(
                client_rating=5,
                client_rated=True,
                workshop_rating=4,
                workshop_rated=True,
            ),
        )
        assert dto.ratings.client_rating == 5
        assert dto.ratings.workshop_rated is True


class TestCreateServiceRequest:
    def test_valid(self):
        req = CreateServiceRequest(
            workshop_id=uuid4(),
            service_name="Alineación",
            standard_price_min=20.0,
            standard_price_max=40.0,
        )
        assert req.service_name == "Alineación"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            CreateServiceRequest(
                workshop_id=uuid4(),
                # Falta service_name
                standard_price_min=20.0,
                standard_price_max=40.0,
            )


class TestSetQuoteRequest:
    def test_valid(self):
        req = SetQuoteRequest(final_price=150.0)
        assert req.final_price == 150.0


class TestPayServiceOrderRequest:
    def test_valid(self):
        req = PayServiceOrderRequest(payment_method="BANK_TRANSFER", reference_number="REF-001")
        assert req.payment_method == "BANK_TRANSFER"

    def test_invalid_method(self):
        with pytest.raises(ValidationError):
            PayServiceOrderRequest(
                payment_method="CRYPTO",
                reference_number="REF-001",
            )


class TestRateServiceOrderRequest:
    def test_valid(self):
        req = RateServiceOrderRequest(rating=4, comment="Buen servicio")
        assert req.rating == 4
        assert req.comment == "Buen servicio"

    def test_rating_bounds(self):
        with pytest.raises(ValidationError):
            RateServiceOrderRequest(rating=0)
