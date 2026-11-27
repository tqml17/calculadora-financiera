"""Motor de tabla de amortización con abono constante a capital (sistema alemán).

Lógica financiera implementada:
-------------------------------
1. Abono constante a capital:
   - Sin periodos de gracia, el capital P se divide en partes iguales entre los N
     periodos: A = P / N.
   - En cada periodo t:
       Interés_t = SaldoInicial_t * i
       Cuota_t   = AbonoCapital_t + Interés_t
       SaldoFinal_t = SaldoInicial_t - AbonoCapital_t

2. Periodos de gracia (g periodos incluidos dentro del plazo total N, con 0 <= g < N):
   - Gracia con pago de intereses (parcial):
       Durante t = 1..g no se realiza abono ordinario a capital; el deudor paga
       únicamente los intereses causados cada periodo (Cuota_t = Interés_t), por lo
       que el saldo se mantiene constante (salvo que haya abonos extra en gracia).
   - Gracia de cuota/interés muerto (capitalización):
       Durante t = 1..g no se paga capital ni intereses (Cuota_t = 0, salvo abonos
       extra explícitos). Los intereses causados en cada periodo se capitalizan
       sumándose al saldo: SaldoFinal_t = SaldoInicial_t + Interés_t.
   - Al terminar los g periodos de gracia, el saldo vigente se amortiza de forma
     constante entre los (N - g) periodos restantes.

3. Abonos extra a capital (en periodos específicos o recurrentes):
   - Se suman al abono ordinario a capital del periodo (limitados al saldo disponible
     para no generar saldos negativos).
   - Efecto 'Reducir plazo':
       Mantiene intacto el abono ordinario constante a capital (A). Al bajar más
       rápido el saldo, la deuda se liquida en menos periodos que el plazo original.
   - Efecto 'Reducir cuota':
       Recalcula el abono ordinario a capital para los periodos restantes:
       A_nuevo = SaldoFinal_t / (N - t), conservando el plazo original (salvo que
       el abono extra cancele totalmente la deuda) con cuotas futuras más bajas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, List, Optional, Sequence, Tuple

from .rates import PERIODICIDADES

GRACE_NONE = "Sin periodo de gracia"
GRACE_PARTIAL = "Con pago de intereses (Gracia parcial)"
GRACE_DEAD = "Cuota/interés muerto (Capitalización)"

GRACE_TYPES: Tuple[str, ...] = (GRACE_NONE, GRACE_PARTIAL, GRACE_DEAD)

EXTRA_SINGLE = "Periodo específico"
EXTRA_RECURRING = "Recurrente"
EXTRA_MODES: Tuple[str, ...] = (EXTRA_SINGLE, EXTRA_RECURRING)

EFFECT_REDUCE_TERM = "Reducir plazo"
EFFECT_REDUCE_PAYMENT = "Reducir cuota"
EXTRA_EFFECTS: Tuple[str, ...] = (EFFECT_REDUCE_TERM, EFFECT_REDUCE_PAYMENT)

TERM_UNITS: Tuple[str, ...] = ("Periodos", "Meses", "Años")

EPSILON = 1e-8


@dataclass(frozen=True)
class ExtraPaymentRule:
    """Regla de abono extra a capital (único o recurrente)."""

    mode: str  # EXTRA_SINGLE o EXTRA_RECURRING
    amount: float  # Monto del abono extra (> 0)
    start_period: int  # Periodo único o periodo inicial (>= 1)
    effect: str  # EFFECT_REDUCE_TERM o EFFECT_REDUCE_PAYMENT
    frequency: int = 1  # Cada cuántos periodos (solo si es recurrente, >= 1)
    end_period: Optional[int] = None  # Periodo final opcional (solo recurrente)

    def validate(self, max_periods: Optional[int] = None) -> None:
        if self.mode not in EXTRA_MODES:
            raise ValueError(f"Modalidad de abono extra inválida: '{self.mode}'.")
        if self.effect not in EXTRA_EFFECTS:
            raise ValueError(f"Efecto de abono extra inválido: '{self.effect}'.")
        if not isinstance(self.amount, (int, float)) or not math.isfinite(self.amount) or self.amount <= 0:
            raise ValueError("El monto del abono extra debe ser mayor que cero.")
        if not isinstance(self.start_period, int) or self.start_period < 1:
            raise ValueError("El periodo del abono extra debe ser un entero mayor o igual a 1.")
        if self.mode == EXTRA_RECURRING:
            if not isinstance(self.frequency, int) or self.frequency < 1:
                raise ValueError("La frecuencia de recurrencia debe ser un entero mayor o igual a 1.")
            if self.end_period is not None:
                if not isinstance(self.end_period, int) or self.end_period < self.start_period:
                    raise ValueError(
                        "El periodo final del abono recurrente debe ser mayor o igual al periodo inicial."
                    )
        if max_periods is not None and self.start_period > max_periods:
            raise ValueError(
                f"El periodo inicial del abono extra ({self.start_period}) "
                f"excede el plazo total del préstamo ({max_periods} periodos)."
            )

    def describe(self) -> str:
        """Texto descriptivo compacto para mostrar en la interfaz."""
        if self.mode == EXTRA_SINGLE:
            when = f"Periodo {self.start_period}"
        else:
            fin = f" hasta {self.end_period}" if self.end_period is not None else " hasta el final"
            when = f"Cada {self.frequency} per. (desde {self.start_period}{fin})"
        return f"{when} | ${self.amount:,.2f} | {self.effect}"


@dataclass(frozen=True)
class AmortizationRow:
    """Fila individual de la tabla de amortización."""

    period: int
    initial_balance: float
    regular_principal: float
    extra_principal: float
    total_principal: float  # Abono a capital total (ordinario + extra)
    interest: float  # Interés causado en el periodo
    interest_paid: float  # Interés pagado en efectivo en el periodo
    interest_capitalized: float  # Interés capitalizado (solo gracia muerta)
    total_payment: float  # Cuota total desembolsada en el periodo
    ending_balance: float
    note: str


@dataclass(frozen=True)
class AmortizationSummary:
    """Totales y métricas resumen de la tabla de amortización."""

    initial_principal: float
    periodic_rate: float
    planned_periods: int
    actual_periods: int
    grace_periods: int
    grace_type: str
    total_regular_principal: float
    total_extra_principal: float
    total_principal: float
    total_interest: float
    total_interest_paid: float
    total_interest_capitalized: float
    total_payment: float
    final_balance: float
    periods_saved: int
    interest_saved: float


@dataclass(frozen=True)
class AmortizationSchedule:
    """Resultado completo: filas y totales generales."""

    rows: List[AmortizationRow] = field(default_factory=list)
    summary: AmortizationSummary = field(default=None)  # type: ignore[assignment]


def resolve_total_periods(
    term_value: float,
    term_unit: str,
    periodicity: str,
) -> int:
    """Convierte el plazo ingresado (Periodos, Meses o Años) a número entero de periodos."""
    if periodicity not in PERIODICIDADES:
        raise ValueError(f"Periodicidad inválida: '{periodicity}'.")
    if term_unit not in TERM_UNITS:
        raise ValueError(f"Unidad de plazo inválida: '{term_unit}'.")
    if not isinstance(term_value, (int, float)) or not math.isfinite(term_value) or term_value <= 0:
        raise ValueError("El plazo total debe ser un número mayor que cero.")

    periods_per_year = PERIODICIDADES[periodicity]

    if term_unit == "Periodos":
        raw_periods = float(term_value)
    elif term_unit == "Años":
        raw_periods = float(term_value) * periods_per_year
    else:  # "Meses"
        months_per_period = 12.0 / periods_per_year
        raw_periods = float(term_value) / months_per_period

    rounded = round(raw_periods)
    if abs(raw_periods - rounded) > 1e-6 or rounded < 1:
        months_per_period = int(12 // periods_per_year)
        raise ValueError(
            f"El plazo de {term_value:g} {term_unit.lower()} no corresponde a un número "
            f"entero positivo de periodos para la periodicidad {periodicity.lower()} "
            f"({months_per_period} mes(es) por periodo)."
        )
    return int(rounded)


def _expand_extra_payments(
    rules: Sequence[ExtraPaymentRule],
    total_periods: int,
) -> Dict[int, Tuple[float, bool]]:
    """Mapea cada periodo t -> (monto_extra_total, recalcular_cuota_despues).

    Si múltiples reglas coinciden en el mismo periodo, se suman sus montos; si al
    menos una indica 'Reducir cuota', se recalcula el abono constante posterior.
    """
    schedule_map: Dict[int, Tuple[float, bool]] = {}

    for rule in rules:
        rule.validate(max_periods=total_periods)
        recalc = rule.effect == EFFECT_REDUCE_PAYMENT

        if rule.mode == EXTRA_SINGLE:
            periods = [rule.start_period]
        else:
            end_p = min(rule.end_period, total_periods) if rule.end_period is not None else total_periods
            periods = list(range(rule.start_period, end_p + 1, rule.frequency))

        for p in periods:
            if 1 <= p <= total_periods:
                prev_amt, prev_recalc = schedule_map.get(p, (0.0, False))
                schedule_map[p] = (prev_amt + float(rule.amount), prev_recalc or recalc)

    return schedule_map


def _simulate_schedule(
    principal: float,
    total_periods: int,
    periodic_rate: float,
    grace_periods: int,
    grace_type: str,
    extra_map: Dict[int, Tuple[float, bool]],
) -> List[AmortizationRow]:
    """Ejecuta la simulación periodo a periodo del sistema de abono constante a capital."""
    rows: List[AmortizationRow] = []
    balance = float(principal)

    # Saldo teórico sin abonos extra 'Reducir plazo' durante gracia, para fijar
    # correctamente la cuota base cuando un abono extra en gracia busca reducir plazo.
    baseline_grace_balance = float(principal)
    had_reduce_payment_in_grace = False

    amortization_periods = total_periods - grace_periods
    regular_principal_target = 0.0

    for period in range(1, total_periods + 1):
        if balance <= EPSILON:
            break

        initial_balance = balance
        interest = initial_balance * periodic_rate
        scheduled_extra, reduce_payment = extra_map.get(period, (0.0, False))

        if period <= grace_periods:
            # --- Fase de periodo de gracia (sin abono ordinario a capital) ---
            regular_principal = 0.0

            if grace_type == GRACE_DEAD:
                # Cuota/interés muerto: el interés se capitaliza al saldo
                interest_paid = 0.0
                interest_capitalized = interest
                balance_with_interest = initial_balance + interest_capitalized
                baseline_grace_balance = baseline_grace_balance * (1.0 + periodic_rate)

                applied_extra = min(scheduled_extra, balance_with_interest) if scheduled_extra > 0 else 0.0
                if reduce_payment and applied_extra > 0:
                    had_reduce_payment_in_grace = True

                total_principal = applied_extra
                ending_balance = balance_with_interest - applied_extra
                total_payment = applied_extra

                note = "Gracia muerta (int. capitalizado)"
                if applied_extra > 0:
                    eff_lbl = "Red. cuota" if reduce_payment else "Red. plazo"
                    note = f"Gracia muerta + Extra ${applied_extra:,.2f} ({eff_lbl})"
            else:
                # Gracia parcial: se pagan los intereses del periodo
                interest_paid = interest
                interest_capitalized = 0.0

                applied_extra = min(scheduled_extra, initial_balance) if scheduled_extra > 0 else 0.0
                if reduce_payment and applied_extra > 0:
                    had_reduce_payment_in_grace = True

                total_principal = applied_extra
                ending_balance = initial_balance - applied_extra
                total_payment = interest_paid + applied_extra

                note = "Gracia parcial (pago de int.)"
                if applied_extra > 0:
                    eff_lbl = "Red. cuota" if reduce_payment else "Red. plazo"
                    note = f"Gracia parcial + Extra ${applied_extra:,.2f} ({eff_lbl})"

            if abs(ending_balance) < EPSILON:
                ending_balance = 0.0

            rows.append(
                AmortizationRow(
                    period=period,
                    initial_balance=initial_balance,
                    regular_principal=regular_principal,
                    extra_principal=applied_extra,
                    total_principal=total_principal,
                    interest=interest,
                    interest_paid=interest_paid,
                    interest_capitalized=interest_capitalized,
                    total_payment=total_payment,
                    ending_balance=ending_balance,
                    note=note,
                )
            )
            balance = ending_balance
            continue

        # --- Fase de amortización ordinaria (t > grace_periods) ---
        if period == grace_periods + 1:
            # Al iniciar la amortización, definimos el abono constante a capital:
            # si hubo abonos en gracia con efecto 'Reducir plazo' (y ninguno con
            # 'Reducir cuota'), conservamos la cuota base sin esos abonos para acortar el plazo.
            if grace_periods > 0 and not had_reduce_payment_in_grace and baseline_grace_balance > balance + EPSILON:
                regular_principal_target = baseline_grace_balance / amortization_periods
            else:
                regular_principal_target = balance / amortization_periods

        interest_paid = interest
        interest_capitalized = 0.0

        # En el último periodo del plazo se liquida cualquier residuo por redondeo
        if period == total_periods:
            regular_principal = initial_balance
        else:
            regular_principal = min(regular_principal_target, initial_balance)

        remaining_after_regular = max(0.0, initial_balance - regular_principal)
        applied_extra = min(scheduled_extra, remaining_after_regular) if scheduled_extra > 0 else 0.0

        total_principal = regular_principal + applied_extra
        ending_balance = initial_balance - total_principal

        # Evitar residuos ínfimos de punto flotante
        if abs(ending_balance) < EPSILON:
            total_principal = initial_balance
            ending_balance = 0.0

        total_payment = total_principal + interest_paid

        if applied_extra > 0:
            eff_lbl = "Red. cuota" if reduce_payment else "Red. plazo"
            note = f"Extra ${applied_extra:,.2f} ({eff_lbl})"
        else:
            note = "Normal"

        rows.append(
            AmortizationRow(
                period=period,
                initial_balance=initial_balance,
                regular_principal=regular_principal,
                extra_principal=applied_extra,
                total_principal=total_principal,
                interest=interest,
                interest_paid=interest_paid,
                interest_capitalized=interest_capitalized,
                total_payment=total_payment,
                ending_balance=ending_balance,
                note=note,
            )
        )

        balance = ending_balance

        # Si el abono extra del periodo busca reducir cuota y queda saldo y plazo,
        # recalculamos el abono constante a capital para los periodos restantes.
        if applied_extra > 0 and reduce_payment and balance > EPSILON and period < total_periods:
            remaining_periods = total_periods - period
            regular_principal_target = balance / remaining_periods

    return rows


def generate_amortization_schedule(
    principal: float,
    total_periods: int,
    periodic_rate: float,
    grace_periods: int = 0,
    grace_type: str = GRACE_NONE,
    extra_payments: Sequence[ExtraPaymentRule] = (),
) -> AmortizationSchedule:
    """Genera la tabla de amortización con abono constante a capital y sus totales.

    Args:
        principal: Monto inicial del préstamo (> 0).
        total_periods: Plazo total en periodos (entero >= 1, incluye periodos de gracia).
        periodic_rate: Tasa periódica vencida en decimal (p. ej. 0.02 para 2%, >= 0).
        grace_periods: Número de periodos de gracia (0 <= grace_periods < total_periods).
        grace_type: GRACE_NONE, GRACE_PARTIAL o GRACE_DEAD.
        extra_payments: Secuencia de reglas ExtraPaymentRule.

    Returns:
        AmortizationSchedule con todas las filas y el resumen general.
    """
    if not isinstance(principal, (int, float)) or not math.isfinite(principal) or principal <= 0:
        raise ValueError("El monto del préstamo debe ser un número mayor que cero.")

    if not isinstance(total_periods, int) or total_periods < 1:
        raise ValueError("El plazo total debe ser un número entero mayor o igual a 1 periodo.")

    if not isinstance(periodic_rate, (int, float)) or not math.isfinite(periodic_rate) or periodic_rate < 0:
        raise ValueError("La tasa periódica de amortización debe ser un número mayor o igual a cero.")

    if not isinstance(grace_periods, int) or grace_periods < 0:
        raise ValueError("Los periodos de gracia deben ser un número entero mayor o igual a cero.")

    if grace_type not in GRACE_TYPES:
        raise ValueError(f"Tipo de periodo de gracia inválido: '{grace_type}'.")

    if grace_type == GRACE_NONE:
        effective_grace = 0
    else:
        effective_grace = grace_periods

    if effective_grace >= total_periods:
        raise ValueError(
            f"Los periodos de gracia ({effective_grace}) deben ser menores al plazo total "
            f"({total_periods} periodos) para que exista al menos un periodo de amortización."
        )

    effective_grace_type = GRACE_NONE if effective_grace == 0 else grace_type
    extra_map = _expand_extra_payments(extra_payments, total_periods)

    rows = _simulate_schedule(
        principal=principal,
        total_periods=total_periods,
        periodic_rate=periodic_rate,
        grace_periods=effective_grace,
        grace_type=effective_grace_type,
        extra_map=extra_map,
    )

    total_regular = sum(r.regular_principal for r in rows)
    total_extra = sum(r.extra_principal for r in rows)
    total_principal = sum(r.total_principal for r in rows)
    total_interest = sum(r.interest for r in rows)
    total_interest_paid = sum(r.interest_paid for r in rows)
    total_interest_cap = sum(r.interest_capitalized for r in rows)
    total_payment = sum(r.total_payment for r in rows)
    final_balance = rows[-1].ending_balance if rows else float(principal)
    actual_periods = len(rows)

    # Calcular ahorro frente al escenario base sin abonos extra
    if extra_map:
        base_rows = _simulate_schedule(
            principal=principal,
            total_periods=total_periods,
            periodic_rate=periodic_rate,
            grace_periods=effective_grace,
            grace_type=effective_grace_type,
            extra_map={},
        )
        base_interest = sum(r.interest for r in base_rows)
        interest_saved = max(0.0, base_interest - total_interest)
        periods_saved = max(0, len(base_rows) - actual_periods)
    else:
        interest_saved = 0.0
        periods_saved = 0

    summary = AmortizationSummary(
        initial_principal=float(principal),
        periodic_rate=float(periodic_rate),
        planned_periods=total_periods,
        actual_periods=actual_periods,
        grace_periods=effective_grace,
        grace_type=effective_grace_type,
        total_regular_principal=total_regular,
        total_extra_principal=total_extra,
        total_principal=total_principal,
        total_interest=total_interest,
        total_interest_paid=total_interest_paid,
        total_interest_capitalized=total_interest_cap,
        total_payment=total_payment,
        final_balance=final_balance,
        periods_saved=periods_saved,
        interest_saved=interest_saved,
    )
    return AmortizationSchedule(rows=rows, summary=summary)
