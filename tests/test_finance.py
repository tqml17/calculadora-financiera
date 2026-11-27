"""Pruebas unitarias para conversión de tasas, validaciones y tabla de amortización."""

from __future__ import annotations

import math
import unittest

from finance.amortization import (
    EFFECT_REDUCE_PAYMENT,
    EFFECT_REDUCE_TERM,
    EXTRA_RECURRING,
    EXTRA_SINGLE,
    GRACE_DEAD,
    GRACE_NONE,
    GRACE_PARTIAL,
    ExtraPaymentRule,
    generate_amortization_schedule,
    resolve_total_periods,
)
from finance.rates import (
    MODALIDADES,
    PERIODICIDADES,
    TIPOS_TASA,
    RateSpec,
    convert_rate,
)
from finance.validators import (
    parse_number,
    parse_optional_positive_int,
    parse_positive_int,
)


class TestRateConversions(unittest.TestCase):
    """Verifica exactitud y validaciones del conversor de tasas."""

    def test_namv_to_emv_and_ea(self) -> None:
        src = RateSpec("Nominal", "Vencida", "Mensual")
        tgt = RateSpec("Efectiva", "Vencida", "Mensual")
        res = convert_rate(24.0, src, tgt)

        self.assertAlmostEqual(res.converted_rate, 0.02, places=10)
        self.assertAlmostEqual(res.target_periodic_vencida, 0.02, places=10)
        expected_ea = (1.02**12) - 1.0
        self.assertAlmostEqual(res.effective_annual_rate, expected_ea, places=10)

    def test_roundtrip_all_combinations(self) -> None:
        """Toda combinación de tipo/modalidad/periodicidad debe ser exactamente reversible."""
        specs = [
            RateSpec(t, mod, per)
            for t in TIPOS_TASA
            for mod in MODALIDADES
            for per in PERIODICIDADES
        ]
        base = RateSpec("Efectiva", "Vencida", "Anual")
        base_rate_pct = 18.0

        for target in specs:
            forward = convert_rate(base_rate_pct, base, target)
            backward = convert_rate(forward.converted_rate * 100.0, target, base)
            self.assertAlmostEqual(
                backward.converted_rate * 100.0,
                base_rate_pct,
                places=8,
                msg=f"Fallo roundtrip para {target}",
            )

    def test_anticipated_to_vencida_exact(self) -> None:
        # 2% mensual anticipada -> 2 / (1 - 0.02) = 2.0408163265% mensual vencida
        src = RateSpec("Efectiva", "Anticipada", "Mensual")
        tgt = RateSpec("Efectiva", "Vencida", "Mensual")
        res = convert_rate(2.0, src, tgt)
        self.assertAlmostEqual(res.converted_rate, 0.02 / 0.98, places=10)
        self.assertAlmostEqual(res.target_periodic_vencida, 0.02 / 0.98, places=10)

    def test_nominal_anticipated_periodic_validation(self) -> None:
        # 400% Nominal Trimestral Anticipada -> 100% trimestral anticipada -> inválido
        src = RateSpec("Nominal", "Anticipada", "Trimestral")
        tgt = RateSpec("Efectiva", "Vencida", "Anual")
        with self.assertRaises(ValueError):
            convert_rate(400.0, src, tgt)

        # 120% Nominal Mensual Anticipada -> 10% mensual anticipada -> válido (< 100% en periodo)
        src_ok = RateSpec("Nominal", "Anticipada", "Mensual")
        res_ok = convert_rate(120.0, src_ok, RateSpec("Efectiva", "Vencida", "Mensual"))
        self.assertAlmostEqual(res_ok.converted_rate, 0.10 / 0.90, places=10)

    def test_effective_anticipated_100_or_more_rejected(self) -> None:
        src = RateSpec("Efectiva", "Anticipada", "Mensual")
        tgt = RateSpec("Efectiva", "Vencida", "Mensual")
        with self.assertRaises(ValueError):
            convert_rate(100.0, src, tgt)
        with self.assertRaises(ValueError):
            convert_rate(105.0, src, tgt)

    def test_zero_and_negative_rates(self) -> None:
        src = RateSpec("Nominal", "Anticipada", "Semestral")
        tgt = RateSpec("Efectiva", "Vencida", "Mensual")
        res = convert_rate(0.0, src, tgt)
        self.assertEqual(res.converted_rate, 0.0)
        self.assertEqual(res.target_periodic_vencida, 0.0)

        with self.assertRaises(ValueError):
            convert_rate(-5.0, src, tgt)


class TestAmortizationSchedule(unittest.TestCase):
    """Verifica el sistema de abono constante a capital, gracia y abonos extra."""

    def test_basic_constant_principal(self) -> None:
        sched = generate_amortization_schedule(
            principal=12_000_000,
            total_periods=12,
            periodic_rate=0.02,
        )
        self.assertEqual(len(sched.rows), 12)
        for row in sched.rows:
            self.assertAlmostEqual(row.total_principal, 1_000_000.0, places=6)

        self.assertAlmostEqual(sched.rows[0].interest, 240_000.0, places=6)
        self.assertAlmostEqual(sched.rows[0].total_payment, 1_240_000.0, places=6)
        self.assertAlmostEqual(sched.rows[-1].ending_balance, 0.0, places=6)
        self.assertAlmostEqual(sched.summary.total_principal, 12_000_000.0, places=6)
        self.assertAlmostEqual(
            sched.summary.total_payment,
            sched.summary.total_principal + sched.summary.total_interest,
            places=6,
        )

    def test_partial_grace_periods(self) -> None:
        sched = generate_amortization_schedule(
            principal=10_000_000,
            total_periods=12,
            periodic_rate=0.015,
            grace_periods=2,
            grace_type=GRACE_PARTIAL,
        )
        self.assertEqual(len(sched.rows), 12)
        # Periodos 1 y 2: solo intereses, saldo constante
        for i in (0, 1):
            self.assertAlmostEqual(sched.rows[i].total_principal, 0.0, places=6)
            self.assertAlmostEqual(sched.rows[i].interest, 150_000.0, places=6)
            self.assertAlmostEqual(sched.rows[i].total_payment, 150_000.0, places=6)
            self.assertAlmostEqual(sched.rows[i].ending_balance, 10_000_000.0, places=6)

        # Periodos 3..12 (10 periodos): abono constante = 1,000,000
        for row in sched.rows[2:]:
            self.assertAlmostEqual(row.total_principal, 1_000_000.0, places=6)
        self.assertAlmostEqual(sched.summary.final_balance, 0.0, places=6)

    def test_dead_grace_capitalization(self) -> None:
        p = 10_000_000.0
        r = 0.02
        sched = generate_amortization_schedule(
            principal=p,
            total_periods=12,
            periodic_rate=r,
            grace_periods=2,
            grace_type=GRACE_DEAD,
        )
        expected_after_grace = p * ((1.0 + r) ** 2)
        self.assertAlmostEqual(sched.rows[0].total_payment, 0.0, places=6)
        self.assertAlmostEqual(sched.rows[1].total_payment, 0.0, places=6)
        self.assertAlmostEqual(sched.rows[1].ending_balance, expected_after_grace, places=6)
        self.assertAlmostEqual(sched.rows[2].total_principal, expected_after_grace / 10.0, places=6)
        self.assertAlmostEqual(sched.summary.final_balance, 0.0, places=6)

        # Invariante contable: Total Cuotas == Capital Inicial + Total Intereses Causados
        self.assertAlmostEqual(
            sched.summary.total_payment,
            p + sched.summary.total_interest,
            places=5,
        )

    def test_extra_payment_reduce_term(self) -> None:
        rule = ExtraPaymentRule(
            mode=EXTRA_SINGLE,
            amount=3_000_000,
            start_period=3,
            effect=EFFECT_REDUCE_TERM,
        )
        sched = generate_amortization_schedule(
            principal=12_000_000,
            total_periods=12,
            periodic_rate=0.02,
            extra_payments=[rule],
        )
        # Abono ordinario sigue siendo 1M -> 3M extra ahorra exactamente 3 periodos (12 -> 9)
        self.assertEqual(sched.summary.actual_periods, 9)
        self.assertEqual(sched.summary.periods_saved, 3)
        self.assertGreater(sched.summary.interest_saved, 0.0)
        self.assertAlmostEqual(sched.rows[2].total_principal, 4_000_000.0, places=6)
        self.assertAlmostEqual(sched.rows[3].total_principal, 1_000_000.0, places=6)
        self.assertAlmostEqual(sched.summary.final_balance, 0.0, places=6)

    def test_extra_payment_reduce_payment(self) -> None:
        rule = ExtraPaymentRule(
            mode=EXTRA_SINGLE,
            amount=3_000_000,
            start_period=3,
            effect=EFFECT_REDUCE_PAYMENT,
        )
        sched = generate_amortization_schedule(
            principal=12_000_000,
            total_periods=12,
            periodic_rate=0.02,
            extra_payments=[rule],
        )
        # Mantiene 12 periodos; saldo tras periodo 3 = 12M - 3M(ord) - 3M(extra) = 6M
        # Nuevo abono constante para 9 periodos restantes = 6M / 9
        self.assertEqual(sched.summary.actual_periods, 12)
        self.assertEqual(sched.summary.periods_saved, 0)
        self.assertAlmostEqual(sched.rows[3].total_principal, 6_000_000.0 / 9.0, places=6)
        self.assertAlmostEqual(sched.summary.final_balance, 0.0, places=6)

    def test_recurring_extra_payments(self) -> None:
        rule = ExtraPaymentRule(
            mode=EXTRA_RECURRING,
            amount=1_000_000,
            start_period=2,
            frequency=2,
            end_period=10,
            effect=EFFECT_REDUCE_TERM,
        )
        sched = generate_amortization_schedule(
            principal=10_000_000,
            total_periods=10,
            periodic_rate=0.01,
            extra_payments=[rule],
        )
        self.assertLess(sched.summary.actual_periods, 10)
        self.assertAlmostEqual(sched.summary.total_principal, 10_000_000.0, places=6)
        self.assertAlmostEqual(sched.summary.final_balance, 0.0, places=6)

    def test_resolve_total_periods_and_validations(self) -> None:
        self.assertEqual(resolve_total_periods(2, "Años", "Mensual"), 24)
        self.assertEqual(resolve_total_periods(12, "Meses", "Trimestral"), 4)
        self.assertEqual(resolve_total_periods(1.5, "Años", "Semestral"), 3)

        with self.assertRaises(ValueError):
            resolve_total_periods(5, "Meses", "Trimestral")

        with self.assertRaises(ValueError):
            generate_amortization_schedule(0, 12, 0.01)

        with self.assertRaises(ValueError):
            generate_amortization_schedule(1_000_000, 12, 0.01, grace_periods=12, grace_type=GRACE_PARTIAL)


class TestValidators(unittest.TestCase):
    """Verifica el parseo seguro de entradas numéricas."""

    def test_parse_number_valid_and_invalid(self) -> None:
        self.assertAlmostEqual(parse_number("12,5%", "Tasa", is_percentage=True), 12.5)
        self.assertAlmostEqual(parse_number("$10,000,000", "Monto"), 10_000_000.0)
        self.assertAlmostEqual(parse_number("10.000.000,50", "Monto"), 10_000_000.50)

        for bad in ("", "abc", "-10", "0", "nan", "inf"):
            with self.assertRaises(ValueError):
                parse_number(bad, "Campo")

    def test_parse_ints(self) -> None:
        self.assertEqual(parse_positive_int("12", "Plazo"), 12)
        self.assertEqual(parse_positive_int("0", "Gracia", allow_zero=True), 0)
        self.assertIsNone(parse_optional_positive_int("", "Hasta"))
        self.assertEqual(parse_optional_positive_int("24", "Hasta"), 24)

        with self.assertRaises(ValueError):
            parse_positive_int("3.5", "Plazo")


if __name__ == "__main__":
    unittest.main()
