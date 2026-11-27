"""Módulo de cálculos financieros: conversión de tasas y amortización constante."""

from .rates import (
    PERIODICIDADES,
    TIPOS_TASA,
    MODALIDADES,
    RateSpec,
    RateConversionResult,
    convert_rate,
    format_rate_notation,
)
from .amortization import (
    GRACE_NONE,
    GRACE_PARTIAL,
    GRACE_DEAD,
    EXTRA_SINGLE,
    EXTRA_RECURRING,
    EFFECT_REDUCE_TERM,
    EFFECT_REDUCE_PAYMENT,
    ExtraPaymentRule,
    AmortizationRow,
    AmortizationSummary,
    AmortizationSchedule,
    resolve_total_periods,
    generate_amortization_schedule,
)

__all__ = [
    "PERIODICIDADES",
    "TIPOS_TASA",
    "MODALIDADES",
    "RateSpec",
    "RateConversionResult",
    "convert_rate",
    "format_rate_notation",
    "GRACE_NONE",
    "GRACE_PARTIAL",
    "GRACE_DEAD",
    "EXTRA_SINGLE",
    "EXTRA_RECURRING",
    "EFFECT_REDUCE_TERM",
    "EFFECT_REDUCE_PAYMENT",
    "ExtraPaymentRule",
    "AmortizationRow",
    "AmortizationSummary",
    "AmortizationSchedule",
    "resolve_total_periods",
    "generate_amortization_schedule",
]
