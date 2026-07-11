import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from src.config.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[str] = mapped_column(String)
    ci: Mapped[str] = mapped_column(String, unique=True)
    phone: Mapped[str] = mapped_column(String, nullable=True)
    photo_url: Mapped[str] = mapped_column(String, nullable=True)
    is_suspended: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    client_average_rating: Mapped[float] = mapped_column(Float, default=0.0)
    client_rating_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    roles: Mapped[list["UserRole"]] = relationship(
        "UserRole", back_populates="user", cascade="all, delete-orphan", lazy="joined"
    )
    vehicles = relationship("Vehicle", back_populates="owner")
    workshops = relationship("Workshop", back_populates="owner")
    service_orders = relationship("ServiceOrder", back_populates="user")


class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String)  # CLIENT, WORKSHOP_OWNER, ADMIN

    user = relationship("User", back_populates="roles")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    vehicle_type: Mapped[str] = mapped_column(String)  # CAR, MOTORCYCLE
    brand: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    year: Mapped[int] = mapped_column(Integer)
    license_plate: Mapped[str] = mapped_column(String, unique=True)
    vin: Mapped[str] = mapped_column(String, unique=True)
    photo_url: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner = relationship("User", back_populates="vehicles")
    history_logs = relationship("VehicleHistoryLog", back_populates="vehicle")


class Workshop(Base):
    __tablename__ = "workshops"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String)
    rif: Mapped[str] = mapped_column(String, unique=True)
    verification_document_url: Mapped[str] = mapped_column(String, nullable=True)
    photo_url: Mapped[str] = mapped_column(String, nullable=True)
    address: Mapped[str] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    is_certified: Mapped[int] = mapped_column(Integer, default=0)
    was_certified: Mapped[int] = mapped_column(Integer, default=0)
    is_suspended: Mapped[int] = mapped_column(Integer, default=0)
    average_rating: Mapped[float] = mapped_column(Float, default=0.0)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner = relationship("User", back_populates="workshops")
    services = relationship("WorkshopService", back_populates="workshop")
    parts = relationship("Part", back_populates="workshop")
    bank_accounts = relationship(
        "WorkshopBankAccount", back_populates="workshop", cascade="all, delete-orphan"
    )
    mobile_payments = relationship(
        "WorkshopMobilePayment", back_populates="workshop", cascade="all, delete-orphan"
    )
    payment_methods = relationship(
        "WorkshopPaymentMethod", back_populates="workshop", cascade="all, delete-orphan"
    )
    service_orders = relationship("ServiceOrder", back_populates="workshop")


class WorkshopBankAccount(Base):
    __tablename__ = "workshop_bank_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"))
    account_number: Mapped[str] = mapped_column(String)
    holder_ci: Mapped[str] = mapped_column(String)
    bank_name: Mapped[str] = mapped_column(String)
    is_active: Mapped[int] = mapped_column(Integer, default=1)

    workshop = relationship("Workshop", back_populates="bank_accounts")


class WorkshopMobilePayment(Base):
    __tablename__ = "workshop_mobile_payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"))
    phone_number: Mapped[str] = mapped_column(String)
    bank_name: Mapped[str] = mapped_column(String)
    holder_ci: Mapped[str] = mapped_column(String)
    is_active: Mapped[int] = mapped_column(Integer, default=1)

    workshop = relationship("Workshop", back_populates="mobile_payments")


class WorkshopService(Base):
    __tablename__ = "workshop_services"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"))
    service_name: Mapped[str] = mapped_column(String)
    service_type: Mapped[str] = mapped_column(String, nullable=True)
    standard_price_min: Mapped[float] = mapped_column(Float)
    standard_price_max: Mapped[float] = mapped_column(Float)
    revision_cost_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    revision_cost_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    vehicle_type: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    workshop = relationship("Workshop", back_populates="services")


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"))
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Float)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    condition: Mapped[str] = mapped_column(String)  # NEW, USED
    category: Mapped[str] = mapped_column(String, nullable=True)
    allows_installments: Mapped[int] = mapped_column(Integer, default=0)
    installment_min_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    photo_url: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workshop = relationship("Workshop", back_populates="parts")
    purchases = relationship("PartPurchase", back_populates="part")


class PartPurchase(Base):
    __tablename__ = "part_purchases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"))
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"))
    mileage: Mapped[int] = mapped_column(Integer, default=0)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float)
    total_amount: Mapped[float] = mapped_column(Float)
    down_payment: Mapped[float] = mapped_column(Float, default=0.0)
    financed_amount: Mapped[float] = mapped_column(Float, default=0.0)
    installment_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String, default="PENDING"
    )  # PENDING, PAID, FINANCED, CANCELLED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    part = relationship("Part", back_populates="purchases")
    payments = relationship(
        "PartPayment", back_populates="purchase", cascade="all, delete-orphan"
    )


class PartPayment(Base):
    __tablename__ = "part_payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("part_purchases.id"))
    amount: Mapped[float] = mapped_column(Float)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payment_method: Mapped[str] = mapped_column(
        String, default="OTHER"
    )  # BANK_TRANSFER, MOBILE_PAYMENT, CASH, OTHER
    reference_number: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String, default="PENDING"
    )  # PENDING, PAID, OVERDUE
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    purchase = relationship("PartPurchase", back_populates="payments")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"))
    mileage: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String)  # PENDING, PENDING_CONFIRMATION, PAID, FINANCED, CLOSED, CANCELLED
    delivery_method: Mapped[str] = mapped_column(String, default="PICKUP")  # PICKUP, DELIVERY, SHIPPING
    delivery_address: Mapped[str] = mapped_column(Text, nullable=True)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0.0)
    reference_number: Mapped[str] = mapped_column(String, nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    tracking_number: Mapped[str] = mapped_column(String, nullable=True)
    shipping_notes: Mapped[str] = mapped_column(Text, nullable=True)
    shipped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_client: Mapped[int] = mapped_column(Integer, default=0)
    closed_by_workshop: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    items = relationship("OrderItem", back_populates="order")
    installments = relationship("Installment", back_populates="order")
    user = relationship("User")
    vehicle = relationship("Vehicle")
    order_reviews = relationship("OrderReview", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"))
    part_name: Mapped[str] = mapped_column(String, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="items")
    part = relationship("Part")


class Installment(Base):
    __tablename__ = "installments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    amount: Mapped[float] = mapped_column(Float)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payment_method: Mapped[str] = mapped_column(String, default="OTHER")
    reference_number: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)  # PENDING, PAID, OVERDUE
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    rate_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="installments")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    installment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("installments.id"), nullable=True
    )
    payer_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    receiver_workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"))
    amount: Mapped[float] = mapped_column(Float)
    payment_method: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # PENDING, COMPLETED, FAILED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class VehicleHistoryLog(Base):
    __tablename__ = "vehicle_history_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"))
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=True)
    log_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mileage: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    vehicle = relationship("Vehicle", back_populates="history_logs")


class AssistanceRequest(Base):
    __tablename__ = "assistance_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"))
    target_workshop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshops.id"), nullable=True
    )
    assigned_workshop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshops.id"), nullable=True
    )
    request_type: Mapped[str] = mapped_column(String)  # TOW, BATTERY, TIRE, MECHANIC
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String
    )  # PENDING, ACCEPTED, IN_TRANSIT, COMPLETED, CANCELLED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OrderReview(Base):
    __tablename__ = "order_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"))
    rater_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    target_role: Mapped[str] = mapped_column(String)  # WORKSHOP or CLIENT
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    order = relationship("Order", back_populates="order_reviews")
    __table_args__ = (
        UniqueConstraint("order_id", "rater_id", name="uq_order_review_rater"),
        UniqueConstraint("order_id", "target_role", name="uq_order_review_target_role"),
    )


class UserPaymentAccount(Base):
    __tablename__ = "user_payment_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    account_type: Mapped[str] = mapped_column(String)  # BANK_TRANSFER, MOBILE_PAYMENT
    bank_name: Mapped[str] = mapped_column(String)
    account_number: Mapped[str] = mapped_column(String, nullable=True)
    account_holder: Mapped[str] = mapped_column(String, nullable=True)
    phone_number: Mapped[str] = mapped_column(String, nullable=True)
    holder_document: Mapped[str] = mapped_column(String)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    items = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan"
    )


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cart_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("carts.id"))
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    quantity: Mapped[int] = mapped_column(Integer)

    cart = relationship("Cart", back_populates="items")
    part = relationship("Part")


class WorkshopPaymentMethod(Base):
    __tablename__ = "workshop_payment_methods"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"))
    type: Mapped[str] = mapped_column(String)  # bank_transfer, mobile_payment, cash
    bank_name: Mapped[str] = mapped_column(String, nullable=True)
    account_number: Mapped[str] = mapped_column(String, nullable=True)
    account_holder: Mapped[str] = mapped_column(String, nullable=True)
    phone_number: Mapped[str] = mapped_column(String, nullable=True)
    holder_ci: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workshop = relationship("Workshop", back_populates="payment_methods")


class ServiceOrder(Base):
    __tablename__ = "service_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"))
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshop_services.id"))
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"))
    status: Mapped[str] = mapped_column(String, default="PENDING")
    # PENDING → AT_WORKSHOP → QUOTED → ACCEPTED → IN_PROGRESS → COMPLETED → DELIVERED → CLOSED
    #                                                                       → SHIPPED → DELIVERED → CLOSED
    #                              ↘ REJECTED
    # PENDING → CANCELLED
    base_price: Mapped[float] = mapped_column(Float)
    final_price: Mapped[float] = mapped_column(Float, nullable=True)
    extra_charge: Mapped[float] = mapped_column(Float, default=0.0)
    extra_charge_note: Mapped[str] = mapped_column(Text, nullable=True)
    extra_charge_status: Mapped[str] = mapped_column(String, default="NONE")
    # NONE, PENDING_APPROVAL, APPROVED, REJECTED
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    price_min: Mapped[float] = mapped_column(Float, nullable=True)
    price_max: Mapped[float] = mapped_column(Float, nullable=True)
    delivery_method: Mapped[str] = mapped_column(String, default="PICKUP")
    tracking_number: Mapped[str] = mapped_column(String, nullable=True)
    shipping_notes: Mapped[str] = mapped_column(Text, nullable=True)
    shipped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_client: Mapped[int] = mapped_column(Integer, default=0)
    closed_by_workshop: Mapped[int] = mapped_column(Integer, default=0)
    client_rating: Mapped[int] = mapped_column(Integer, nullable=True)
    client_review: Mapped[str] = mapped_column(Text, nullable=True)
    workshop_rating: Mapped[int] = mapped_column(Integer, nullable=True)
    workshop_review: Mapped[str] = mapped_column(Text, nullable=True)
    revision: Mapped[float] = mapped_column(Float, nullable=True)
    is_paid: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="service_orders")
    workshop = relationship("Workshop", back_populates="service_orders")
    workshop_service = relationship("WorkshopService")
    vehicle = relationship("Vehicle")
    payments = relationship("ServiceOrderPayment", back_populates="service_order")


class ServiceOrderPayment(Base):
    __tablename__ = "service_order_payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    service_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_orders.id")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[float] = mapped_column(Float)
    payment_method: Mapped[str] = mapped_column(String)
    reference_number: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="PENDING_VERIFICATION")
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    rate_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    service_order = relationship("ServiceOrder", back_populates="payments")
    user = relationship("User")
