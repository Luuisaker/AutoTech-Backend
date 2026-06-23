import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Text
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    roles: Mapped[list["UserRole"]] = relationship(
        "UserRole", back_populates="user", cascade="all, delete-orphan", lazy="joined"
    )
    vehicles = relationship("Vehicle", back_populates="owner")
    workshops = relationship("Workshop", back_populates="owner")


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
    is_active: Mapped[int] = mapped_column(Integer, default=1)
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
    address: Mapped[str] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    is_certified: Mapped[int] = mapped_column(Integer, default=0)
    average_rating: Mapped[float] = mapped_column(Float, default=0.0)
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
    standard_price_min: Mapped[float] = mapped_column(Float)
    standard_price_max: Mapped[float] = mapped_column(Float)

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
    is_active: Mapped[int] = mapped_column(Integer, default=1)
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
    status: Mapped[str] = mapped_column(String)  # PENDING, PAID, FINANCED, CANCELLED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    items = relationship("OrderItem", back_populates="order")
    installments = relationship("Installment", back_populates="order")
    vehicle = relationship("Vehicle")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)

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
    status: Mapped[str] = mapped_column(String)  # PENDING, PAID, OVERDUE
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

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
