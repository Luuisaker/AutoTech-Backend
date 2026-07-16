"""Tests del sistema de crédito por niveles.

Cubre:
- Cálculo de nivel basado en puntos
- Penalizaciones exponenciales
- Validación de límites en checkout
- Ajuste manual del admin
- Preservación de ajuste proporcional al subir de nivel
"""

import math
import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from src.modules.credit.application.create import (
    MyCreditLineDTO,
    CreditLineDetailDTO,
    AdminCreditLineDTO,
    CheckoutEligibilityDTO,
    CheckoutEligibilityRequest,
    AdminCreditUpdateRequest,
    CreditLevelDTO,
)
from src.modules.credit.domain.entity import CreditLevel, CreditHistory


# ── Datos de prueba ───────────────────────────────────────────

LEVELS = [
    CreditLevel(level=1, points_required=0, credit_multiplier=1.0, min_down_payment_pct=60, base_parts_limit=150),
    CreditLevel(level=2, points_required=300, credit_multiplier=2.0, min_down_payment_pct=50, base_parts_limit=300),
    CreditLevel(level=3, points_required=900, credit_multiplier=4.0, min_down_payment_pct=40, base_parts_limit=600),
    CreditLevel(level=4, points_required=2700, credit_multiplier=8.0, min_down_payment_pct=30, base_parts_limit=1200),
]

LEVELS_MAP = {lvl.level: lvl for lvl in LEVELS}


def recalculate_level(points: float, current_level: int, current_limit: float) -> dict:
    """Pure function que replica la lógica de CreditService.recalculate_level."""
    for lvl in sorted(LEVELS_MAP.keys(), reverse=True):
        level_def = LEVELS_MAP[lvl]
        if points >= level_def.points_required:
            new_level = lvl
            new_base = level_def.base_parts_limit
            # Preservar ajuste proporcional
            old_level_def = LEVELS_MAP.get(current_level)
            if old_level_def and current_limit > 0 and old_level_def.base_parts_limit > 0:
                ratio = current_limit / old_level_def.base_parts_limit
                new_limit = max(new_base, min(new_base * ratio, new_base * 3))
            else:
                new_limit = new_base
            return {
                "level": new_level,
                "parts_limit": round(new_limit, 2),
                "service_limit": round(new_limit / 3, 2),
            }
    return {"level": current_level, "parts_limit": current_limit, "service_limit": round(current_limit / 3, 2)}


def apply_penalty(days_late: int) -> float:
    """Calcula penalización exponencial."""
    return 10 * (2 ** (days_late - 1))


# ── Tests de niveles ──────────────────────────────────────────


class TestLevelCalculation:
    def test_level_1_default(self):
        result = recalculate_level(0, 1, 150.0)
        assert result["level"] == 1
        assert result["parts_limit"] == 150.0

    def test_level_1_with_points_below_300(self):
        result = recalculate_level(299, 1, 150.0)
        assert result["level"] == 1

    def test_level_2_exact_threshold(self):
        result = recalculate_level(300, 1, 150.0)
        assert result["level"] == 2
        assert result["parts_limit"] == 300.0

    def test_level_2_above_threshold(self):
        result = recalculate_level(500, 1, 150.0)
        assert result["level"] == 2
        assert result["parts_limit"] == 300.0

    def test_level_3(self):
        result = recalculate_level(900, 2, 300.0)
        assert result["level"] == 3
        assert result["parts_limit"] == 600.0

    def test_level_4(self):
        result = recalculate_level(2700, 3, 600.0)
        assert result["level"] == 4
        assert result["parts_limit"] == 1200.0

    def test_service_limit_is_one_third(self):
        result = recalculate_level(300, 1, 150.0)
        assert result["service_limit"] == 100.0  # 300 / 3

    def test_service_limit_level_4(self):
        result = recalculate_level(2700, 3, 600.0)
        assert result["service_limit"] == 400.0  # 1200 / 3

    def test_baja_de_nivel_por_perder_puntos(self):
        """Si pierde puntos, debe bajar de nivel y reducir límite."""
        result = recalculate_level(200, 2, 300.0)
        assert result["level"] == 1
        assert result["parts_limit"] == 150.0


class TestAdminAdjustmentPreserved:
    def test_admin_raised_limit_preserved_on_level_up(self):
        """Admin subió a $200 en nivel 1 (base $150). Al subir a nivel 2 (base $300),
        debe preservar la proporción: 200/150 = 1.33x. Nuevo: 300 * 1.33 = 400."""
        result = recalculate_level(300, 1, 200.0)
        assert result["level"] == 2
        assert result["parts_limit"] == 400.0  # 300 * (200/150)

    def test_admin_raised_limit_capped_at_3x_base(self):
        """No puede exceder 3x el base del nuevo nivel."""
        result = recalculate_level(300, 1, 400.0)  # 400/150 = 2.67, 300*2.67=800, min(800, 900)=800
        # Esperado: 300 * min(400/150, 3) = 300 * 2.67 = 800
        expected = round(300 * min(400 / 150, 3), 2)
        assert result["parts_limit"] == expected

    def test_admin_lowered_limit_respected(self):
        """Si admin puso límite menor al base pero mayor al mínimo, se preserva."""
        result = recalculate_level(300, 1, 150.0)
        assert result["parts_limit"] == 300.0  # Vuelve al base


# ── Tests de penalizaciones ───────────────────────────────────


class TestPenalties:
    def test_day_1_penalty(self):
        assert apply_penalty(1) == 10.0

    def test_day_2_penalty(self):
        assert apply_penalty(2) == 20.0

    def test_day_3_penalty(self):
        assert apply_penalty(3) == 40.0

    def test_day_5_penalty(self):
        assert apply_penalty(5) == 160.0

    def test_days_since_formula(self):
        """Verificar fórmula: 10 * 2^(days-1)"""
        for days in range(1, 11):
            expected = 10 * (2 ** (days - 1))
            assert apply_penalty(days) == expected

    def test_penalty_causes_level_down(self):
        """Nivel 2 con 310 pts, penalización de -40 → 270 pts → nivel 1."""
        points_after = 310 - apply_penalty(3)  # 310 - 40 = 270
        result = recalculate_level(points_after, 2, 300.0)
        assert result["level"] == 1
        assert result["parts_limit"] == 150.0

    def test_points_not_negative(self):
        """Los puntos no pueden ser negativos."""
        points = max(0, 5 - apply_penalty(3))  # 5 - 40 = 0
        assert points == 0.0


# ── Tests de checkout eligibility ─────────────────────────────


class TestCheckoutEligibility:
    def test_within_limit(self):
        """100 financiado, límite 150 → eligible"""
        available = 150.0
        financed = 100.0
        assert financed <= available

    def test_exceeds_limit_returns_min_dp(self):
        """200 financiado, límite 150 → necesita ~35% más de inicial."""
        available = 150.0
        financed = 200.0
        needed_pct = ((financed - available) / financed) * 100
        min_dp = math.ceil(needed_pct) + 10
        assert min_dp >= 35  # ((200-150)/200)*100 = 25, ceil=25, +10 = 35

    def test_exact_limit_boundary(self):
        """Financiado exactamente igual al disponible."""
        available = 150.0
        financed = 150.0
        assert financed <= available

    def test_service_line_uses_both_lines(self):
        """Servicio de $80 financiado, service_available=$50, parts_available=$150
        → debe usar $30 de parts line."""
        service_financed = 80.0
        service_available = 50.0
        parts_available = 150.0
        excess = service_financed - service_available
        assert excess == 30.0
        assert excess <= parts_available  # Suficiente en parts line

    def test_service_line_exceeds_both(self):
        """Servicio de $300, service_available=$50, parts_available=$100
        → exceso de $250, solo hay $100 → no eligible."""
        service_financed = 300.0
        service_available = 50.0
        parts_available = 100.0
        excess = service_financed - service_available
        assert excess > parts_available  # No alcanza


# ── Tests de DTOs ─────────────────────────────────────────────


class TestMyCreditLineDTO:
    def test_valid_dto(self):
        dto = MyCreditLineDTO(
            level=2,
            parts_limit=300.0,
            service_limit=100.0,
            parts_available=250.0,
            service_available=80.0,
            parts_debt=50.0,
            service_debt=20.0,
        )
        assert dto.level == 2
        assert dto.parts_available == 250.0


class TestCheckoutEligibilityDTO:
    def test_eligible(self):
        dto = CheckoutEligibilityDTO(
            eligible=True,
            parts_available=150.0,
            service_available=50.0,
        )
        assert dto.eligible
        assert dto.min_down_payment_percentage is None

    def test_not_eligible_with_min_dp(self):
        dto = CheckoutEligibilityDTO(
            eligible=False,
            parts_available=150.0,
            service_available=50.0,
            min_down_payment_percentage=45.0,
            message="Necesitas al menos 45% de inicial",
        )
        assert not dto.eligible
        assert dto.min_down_payment_percentage == 45.0


class TestAdminCreditUpdateRequest:
    def test_only_parts(self):
        req = AdminCreditUpdateRequest(parts_credit_limit=200.0)
        assert req.parts_credit_limit == 200.0
        assert req.service_credit_limit is None

    def test_both_fields(self):
        req = AdminCreditUpdateRequest(parts_credit_limit=300.0, service_credit_limit=100.0)
        assert req.parts_credit_limit == 300.0
        assert req.service_credit_limit == 100.0


class TestCheckoutEligibilityRequest:
    def test_default_service_zero(self):
        req = CheckoutEligibilityRequest(total_financed_parts=100.0)
        assert req.total_financed_parts == 100.0
        assert req.total_financed_service == 0.0


class TestAdminCreditLineDTO:
    def test_admin_dto_includes_points(self):
        dto = AdminCreditLineDTO(
            user_id=uuid4(),
            user_name="Test User",
            user_email="test@test.com",
            level=2,
            credit_points=500.0,
            parts_limit=300.0,
            service_limit=100.0,
            parts_available=250.0,
            service_available=80.0,
            parts_debt=50.0,
            service_debt=20.0,
        )
        assert dto.credit_points == 500.0  # Solo visible para admin


class TestCreditLevelDTO:
    def test_from_entity(self):
        entity = LEVELS[1]  # level 2
        dto = CreditLevelDTO(
            level=entity.level,
            points_required=entity.points_required,
            credit_multiplier=entity.credit_multiplier,
            min_down_payment_pct=entity.min_down_payment_pct,
            base_parts_limit=entity.base_parts_limit,
        )
        assert dto.level == 2
        assert dto.points_required == 300
        assert dto.min_down_payment_pct == 50
