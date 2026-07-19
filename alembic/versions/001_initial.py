"""initial schema — all tables

Revision ID: 001
Revises:
Create Date: 2026-07-13

"""
from typing import Sequence, Union
from uuid import uuid5, NAMESPACE_DNS

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("ci", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("photo_url", sa.String(), nullable=True),
        sa.Column("is_suspended", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_average_rating", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("client_rating_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credit_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parts_credit_limit", sa.Float(), nullable=False, server_default="150.0"),
        sa.Column("service_credit_limit", sa.Float(), nullable=False, server_default="50.0"),
        sa.Column("credit_points", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_parts_debt", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_service_debt", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("totp_secret", sa.String(), nullable=True),
        sa.Column("is_2fa_enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("language_preference", sa.String(5), server_default="es", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("ci"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- roles ---
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )

    # Seed the 4 roles with deterministic UUIDs (uuid5 based on DNS namespace)
    for name in ["CLIENT", "WORKSHOP_OWNER", "ADMIN", "SUPERADMIN"]:
        role_id = str(uuid5(NAMESPACE_DNS, name))
        op.execute(
            f"INSERT INTO roles (id, name) VALUES ('{role_id}', '{name}') "
            f"ON CONFLICT (name) DO NOTHING"
        )

    # --- user_roles ---
    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
    )

    # --- vehicles ---
    op.create_table(
        "vehicles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_type", sa.String(), nullable=False),
        sa.Column("brand", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("license_plate", sa.String(), nullable=False),
        sa.Column("vin", sa.String(), nullable=False),
        sa.Column("photo_url", sa.String(), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("license_plate"),
        sa.UniqueConstraint("vin"),
    )

    # --- workshops ---
    op.create_table(
        "workshops",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("rif", sa.String(), nullable=False),
        sa.Column("verification_document_url", sa.String(), nullable=True),
        sa.Column("photo_url", sa.String(), nullable=True),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("is_certified", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("was_certified", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_suspended", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("commission_suspended", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("commission_warned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("average_rating", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("rif"),
    )

    # --- workshop_bank_accounts ---
    op.create_table(
        "workshop_bank_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("account_number", sa.String(), nullable=False),
        sa.Column("holder_ci", sa.String(), nullable=False),
        sa.Column("bank_name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
    )

    # --- workshop_mobile_payments ---
    op.create_table(
        "workshop_mobile_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("phone_number", sa.String(), nullable=False),
        sa.Column("bank_name", sa.String(), nullable=False),
        sa.Column("holder_ci", sa.String(), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
    )

    # --- workshop_services ---
    op.create_table(
        "workshop_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("service_name", sa.String(), nullable=False),
        sa.Column("service_type", sa.String(), nullable=True),
        sa.Column("standard_price_min", sa.Float(), nullable=False),
        sa.Column("standard_price_max", sa.Float(), nullable=False),
        sa.Column("revision_cost_min", sa.Float(), nullable=True),
        sa.Column("revision_cost_max", sa.Float(), nullable=True),
        sa.Column("vehicle_type", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- parts ---
    op.create_table(
        "parts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("condition", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("allows_installments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("installment_min_percentage", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("photo_url", sa.String(), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- part_purchases ---
    op.create_table(
        "part_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("part_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parts.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("mileage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("down_payment", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("financed_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("installment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- part_payments ---
    op.create_table(
        "part_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("purchase_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("part_purchases.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_method", sa.String(), nullable=False, server_default="OTHER"),
        sa.Column("reference_number", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- orders ---
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("mileage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("delivery_method", sa.String(), nullable=False, server_default="PICKUP"),
        sa.Column("delivery_address", sa.Text(), nullable=True),
        sa.Column("delivery_fee", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("reference_number", sa.String(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tracking_number", sa.String(), nullable=True),
        sa.Column("shipping_notes", sa.Text(), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_client", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("closed_by_workshop", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- order_items ---
    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("part_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parts.id"), nullable=False),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("part_name", sa.String(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- installments ---
    op.create_table(
        "installments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_method", sa.String(), nullable=False, server_default="OTHER"),
        sa.Column("reference_number", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rate", sa.Float(), nullable=True),
        sa.Column("rate_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("points_eligible_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- transactions ---
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("installment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("installments.id"), nullable=True),
        sa.Column("payer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("receiver_workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("payment_method", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- vehicle_history_logs ---
    op.create_table(
        "vehicle_history_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("log_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mileage", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- assistance_requests ---
    op.create_table(
        "assistance_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("target_workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=True),
        sa.Column("assigned_workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=True),
        sa.Column("request_type", sa.String(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- reviews ---
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- order_reviews ---
    op.create_table(
        "order_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("rater_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_role", sa.String(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("order_id", "rater_id", name="uq_order_review_rater"),
        sa.UniqueConstraint("order_id", "target_role", name="uq_order_review_target_role"),
    )

    # --- user_payment_accounts ---
    op.create_table(
        "user_payment_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("account_type", sa.String(), nullable=False),
        sa.Column("bank_name", sa.String(), nullable=False),
        sa.Column("account_number", sa.String(), nullable=True),
        sa.Column("account_holder", sa.String(), nullable=True),
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column("holder_document", sa.String(), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- carts ---
    op.create_table(
        "carts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- cart_items ---
    op.create_table(
        "cart_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("carts.id"), nullable=False),
        sa.Column("part_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parts.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
    )

    # --- workshop_payment_methods ---
    op.create_table(
        "workshop_payment_methods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("bank_name", sa.String(), nullable=True),
        sa.Column("account_number", sa.String(), nullable=True),
        sa.Column("account_holder", sa.String(), nullable=True),
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column("holder_ci", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- service_orders ---
    op.create_table(
        "service_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshop_services.id"), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("base_price", sa.Float(), nullable=False),
        sa.Column("final_price", sa.Float(), nullable=True),
        sa.Column("extra_charge", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("extra_charge_note", sa.Text(), nullable=True),
        sa.Column("extra_charge_status", sa.String(), nullable=False, server_default="NONE"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("price_min", sa.Float(), nullable=True),
        sa.Column("price_max", sa.Float(), nullable=True),
        sa.Column("delivery_method", sa.String(), nullable=False, server_default="PICKUP"),
        sa.Column("tracking_number", sa.String(), nullable=True),
        sa.Column("shipping_notes", sa.Text(), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_client", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("closed_by_workshop", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("client_rating", sa.Integer(), nullable=True),
        sa.Column("client_review", sa.Text(), nullable=True),
        sa.Column("workshop_rating", sa.Integer(), nullable=True),
        sa.Column("workshop_review", sa.Text(), nullable=True),
        sa.Column("revision", sa.Float(), nullable=True),
        sa.Column("is_paid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_financed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("down_payment_pct", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- service_order_payments ---
    op.create_table(
        "service_order_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("service_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service_orders.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("payment_method", sa.String(), nullable=False),
        sa.Column("reference_number", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING_VERIFICATION"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rate", sa.Float(), nullable=True),
        sa.Column("rate_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- credit_levels ---
    op.create_table(
        "credit_levels",
        sa.Column("level", sa.Integer(), primary_key=True),
        sa.Column("points_required", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("credit_multiplier", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("min_down_payment_pct", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("base_parts_limit", sa.Float(), nullable=False, server_default="150.0"),
    )
    # Seed credit_levels (updated values from migration 010)
    op.execute(
        "INSERT INTO credit_levels (level, points_required, credit_multiplier, min_down_payment_pct, base_parts_limit) VALUES "
        "(1, 0, 1.0, 60.0, 150.0),"
        "(2, 300, 1.5, 50.0, 225.0),"
        "(3, 900, 2.0, 40.0, 300.0),"
        "(4, 2700, 3.0, 30.0, 450.0)"
    )

    # --- credit_history ---
    op.create_table(
        "credit_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("parts_line_used", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("service_line_used", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- credit_limit_reviews ---
    op.create_table(
        "credit_limit_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- service_order_installments ---
    op.create_table(
        "service_order_installments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("service_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service_orders.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_method", sa.String(), nullable=False, server_default="OTHER"),
        sa.Column("reference_number", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rate", sa.Float(), nullable=True),
        sa.Column("rate_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("points_eligible_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- late_fees ---
    op.create_table(
        "late_fees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("installment_type", sa.String(20), nullable=False),
        sa.Column("installment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("payment_method", sa.String(), nullable=False, server_default="OTHER"),
        sa.Column("reference_number", sa.String(), nullable=True),
        sa.Column("rate", sa.Float(), nullable=True),
        sa.Column("rate_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("erroneous_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- workshop_commissions ---
    op.create_table(
        "workshop_commissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("service_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service_orders.id"), nullable=True),
        sa.Column("financed_amount", sa.Float(), nullable=False),
        sa.Column("commission_rate", sa.Float(), nullable=False, server_default="7.0"),
        sa.Column("commission_amount", sa.Float(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("payment_method", sa.String(), nullable=True),
        sa.Column("reference_number", sa.String(), nullable=True),
        sa.Column("rate", sa.Float(), nullable=True),
        sa.Column("rate_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- trusted_devices ---
    op.create_table(
        "trusted_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_trusted_devices_device_id", "trusted_devices", ["device_id"])

    # --- admin_payment_methods ---
    op.create_table(
        "admin_payment_methods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("method_type", sa.String(length=30), nullable=False),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column("account_number", sa.String(length=100), nullable=True),
        sa.Column("holder_name", sa.String(length=150), nullable=True),
        sa.Column("holder_ci", sa.String(length=20), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


    # --- support_messages ---
    op.create_table(
        "support_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("related_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("support_messages")
    op.drop_table("admin_payment_methods")
    op.drop_table("trusted_devices")
    op.drop_table("workshop_commissions")
    op.drop_table("late_fees")
    op.drop_table("service_order_installments")
    op.drop_table("credit_limit_reviews")
    op.drop_table("credit_history")
    op.execute("DELETE FROM credit_levels")
    op.drop_table("credit_levels")
    op.drop_table("service_order_payments")
    op.drop_table("service_orders")
    op.drop_table("workshop_payment_methods")
    op.drop_table("cart_items")
    op.drop_table("carts")
    op.drop_table("user_payment_accounts")
    op.drop_table("order_reviews")
    op.drop_table("reviews")
    op.drop_table("assistance_requests")
    op.drop_table("vehicle_history_logs")
    op.drop_table("transactions")
    op.drop_table("installments")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("part_payments")
    op.drop_table("part_purchases")
    op.drop_table("parts")
    op.drop_table("workshop_services")
    op.drop_table("workshop_mobile_payments")
    op.drop_table("workshop_bank_accounts")
    op.drop_table("workshops")
    op.drop_table("vehicles")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
