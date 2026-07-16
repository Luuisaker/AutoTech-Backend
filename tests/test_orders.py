"""Tests del módulo de órdenes y cuotas.

Cubre:
- Entidades Order, OrderItem, Installment, Transaction
- DTOs de creación y respuesta
- Lógica de montos financiados
"""

import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError
from decimal import Decimal

from src.modules.orders.domain.entity import Order, OrderItem, Installment, Transaction
from src.modules.orders.application.create import (
    OrderDTO,
    OrderItemDTO,
    OrderListDTO,
    InstallmentDTO,
    InstallmentListDTO,
    CheckoutRequest,
    WorkshopCheckoutInput,
    CheckoutItemInput,
    PayInstallmentRequest,
    MarkInstallmentPaidRequest,
    ConfirmPaymentRequest,
    OrderRatingInfo,
    WorkshopOrderDTO,
    RateOrderRequest,
    MarkShippedRequest,
)


# ── Entity tests ──────────────────────────────────────────────


class TestOrderEntity:
    def test_create_order(self):
        user_id = uuid4()
        vehicle_id = uuid4()
        order = Order(user_id=user_id, vehicle_id=vehicle_id)
        assert order.user_id == user_id
        assert order.status == "PENDING"
        assert order.delivery_method == "PICKUP"
        assert order.total_amount == 0.0

    def test_order_defaults(self):
        order = Order(user_id=uuid4(), vehicle_id=uuid4())
        assert order.closed_by_client is False
        assert order.closed_by_workshop is False
        assert order.mileage == 0


class TestInstallmentEntity:
    def test_create_installment(self):
        order_id = uuid4()
        inst = Installment(order_id=order_id, amount=100.0)
        assert inst.amount == 100.0
        assert inst.status == "PENDING"
        assert inst.payment_method == "OTHER"


class TestTransactionEntity:
    def test_create_transaction(self):
        txn = Transaction(
            order_id=uuid4(),
            amount=50.0,
        )
        assert txn.status == "PENDING"
        assert txn.payment_method == "OTHER"


# ── DTO tests ─────────────────────────────────────────────────


class TestOrderDTO:
    def test_from_entity(self):
        oid = uuid4()
        dto = OrderDTO(
            id=oid,
            vehicle_id=uuid4(),
            total_amount=250.0,
            down_payment=100.0,
            financed_amount=150.0,
            installment_count=4,
            status="FINANCED",
            delivery_method="PICKUP",
            delivery_address=None,
            delivery_fee=0.0,
            reference_number=None,
            tracking_number=None,
            shipping_notes=None,
            shipped_at=None,
            workshop_name="Taller Test",
            workshop_id=str(uuid4()),
            workshop_rif="J-12345678-9",
            workshop_address="Calle 123",
            user_first_name="Juan",
            user_last_name="Pérez",
            user_ci="V-12345678",
            user_email="juan@test.com",
            items=[],
            created_at=datetime.now(),
        )
        assert dto.id == oid
        assert dto.status == "FINANCED"
        assert dto.total_amount == 250.0


class TestCheckoutRequest:
    def test_valid_request(self):
        req = CheckoutRequest(
            workshops=[
                WorkshopCheckoutInput(
                    workshop_id=uuid4(),
                    items=[
                        CheckoutItemInput(
                            cart_item_id="item-1",
                            down_payment_percentage=60.0,
                        )
                    ],
                )
            ]
        )
        assert len(req.workshops) == 1

    def test_down_payment_validation(self):
        with pytest.raises(ValidationError):
            CheckoutItemInput(
                cart_item_id="item-1",
                down_payment_percentage=150.0,  # > 100
            )


class TestPayInstallmentRequest:
    def test_valid(self):
        req = PayInstallmentRequest(
            payment_method="BANK_TRANSFER",
            reference_number="REF-123",
        )
        assert req.payment_method == "BANK_TRANSFER"

    def test_invalid_payment_method(self):
        with pytest.raises(ValidationError):
            PayInstallmentRequest(
                payment_method="CREDIT_CARD",  # No permitido
                reference_number="REF-123",
            )


class TestMarkInstallmentPaidRequest:
    def test_optional_reference(self):
        req = MarkInstallmentPaidRequest()
        assert req.reference_number is None


class TestRateOrderRequest:
    def test_valid_rating(self):
        req = RateOrderRequest(rating=5)
        assert req.rating == 5

    def test_rating_too_low(self):
        with pytest.raises(ValidationError):
            RateOrderRequest(rating=0)  # Mínimo 1

    def test_rating_too_high(self):
        with pytest.raises(ValidationError):
            RateOrderRequest(rating=6)  # Máximo 5


class TestMarkShippedRequest:
    def test_valid(self):
        req = MarkShippedRequest(tracking_number="TRACK-123")
        assert req.tracking_number == "TRACK-123"


class TestInstallmentDTO:
    def test_installment_list_dto(self):
        dto = InstallmentListDTO(
            installments=[
                InstallmentDTO(
                    id=uuid4(),
                    order_id=uuid4(),
                    amount=50.0,
                    due_date=datetime.now(),
                    status="PENDING",
                    paid_at=None,
                )
            ]
        )
        assert len(dto.installments) == 1
        assert dto.installments[0].amount == 50.0
