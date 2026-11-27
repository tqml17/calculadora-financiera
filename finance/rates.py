"""Motor de conversión exacta de tasas de interés (efectiva/nominal, vencida/anticipada).

Fórmulas financieras utilizadas:
--------------------------------
Sea m el número de periodos por año según la periodicidad:
  Mensual: 12, Bimestral: 6, Trimestral: 4, Cuatrimestral: 3, Semestral: 2, Anual: 1.

1. De tasa ingresada (en decimal) a tasa periódica de origen (i_p):
   - Si es Nominal (j):   i_p = j / m
   - Si es Efectiva (i):  i_p = i

2. De tasa periódica de origen a tasa periódica vencida (i_v):
   - Si es Vencida:       i_v = i_p
   - Si es Anticipada:    i_v = i_p / (1 - i_p)   [requiere i_p < 1 (100%)]

3. De tasa periódica vencida a tasa Efectiva Anual vencida (EA):
   - EA = (1 + i_v)^m - 1

4. De EA a tasa periódica vencida objetivo (i_v_obj, con m_obj periodos/año):
   - i_v_obj = (1 + EA)^(1 / m_obj) - 1

5. De tasa periódica vencida objetivo a tasa periódica en modalidad objetivo (i_p_obj):
   - Si objetivo es Vencida:     i_p_obj = i_v_obj
   - Si objetivo es Anticipada:  i_p_obj = i_v_obj / (1 + i_v_obj)

6. De tasa periódica objetivo a tasa expresada en tipo objetivo (r_obj):
   - Si objetivo es Efectiva:    r_obj = i_p_obj
   - Si objetivo es Nominal:     r_obj = i_p_obj * m_obj

Para la tabla de amortización siempre se utiliza la tasa periódica vencida
equivalente (i_v_obj) correspondiente a la periodicidad de pago.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Tuple

PERIODICIDADES: Dict[str, int] = {
    "Mensual": 12,
    "Bimestral": 6,
    "Trimestral": 4,
    "Cuatrimestral": 3,
    "Semestral": 2,
    "Anual": 1,
}

PERIODICIDAD_ABREV: Dict[str, str] = {
    "Mensual": "M",
    "Bimestral": "B",
    "Trimestral": "T",
    "Cuatrimestral": "C",
    "Semestral": "S",
    "Anual": "A",
}

TIPOS_TASA: Tuple[str, ...] = ("Efectiva", "Nominal")
MODALIDADES: Tuple[str, ...] = ("Vencida", "Anticipada")


@dataclass(frozen=True)
class RateSpec:
    """Especificación de una tasa de interés (tipo, modalidad y periodicidad)."""

    tipo: str  # "Efectiva" o "Nominal"
    modalidad: str  # "Vencida" o "Anticipada"
    periodicidad: str  # Clave de PERIODICIDADES

    def validate(self) -> int:
        """Valida los atributos y retorna los periodos por año (m)."""
        if self.tipo not in TIPOS_TASA:
            raise ValueError(
                f"Tipo de tasa inválido: '{self.tipo}'. Use {TIPOS_TASA}."
            )
        if self.modalidad not in MODALIDADES:
            raise ValueError(
                f"Modalidad inválida: '{self.modalidad}'. Use {MODALIDADES}."
            )
        if self.periodicidad not in PERIODICIDADES:
            raise ValueError(
                f"Periodicidad inválida: '{self.periodicidad}'. "
                f"Use {tuple(PERIODICIDADES.keys())}."
            )
        return PERIODICIDADES[self.periodicidad]


@dataclass(frozen=True)
class RateConversionResult:
    """Resultado completo de una conversión de tasas (valores en decimal)."""

    input_rate: float
    source: RateSpec
    target: RateSpec
    source_periodic_rate: float
    source_periodic_vencida: float
    effective_annual_rate: float
    target_periodic_vencida: float
    target_periodic_rate: float
    converted_rate: float

    @property
    def source_notation(self) -> str:
        return format_rate_notation(self.source)

    @property
    def target_notation(self) -> str:
        return format_rate_notation(self.target)

    @property
    def amortization_rate_notation(self) -> str:
        """Notación de la tasa periódica vencida equivalente usada en amortización."""
        return format_rate_notation(
            RateSpec("Efectiva", "Vencida", self.target.periodicidad)
        )


def format_rate_notation(spec: RateSpec) -> str:
    """Genera una abreviatura financiera estándar (p. ej. NAMV, EMV, EA, ETA)."""
    p_abrev = PERIODICIDAD_ABREV.get(spec.periodicidad, "?")
    m_abrev = "V" if spec.modalidad == "Vencida" else "A"

    if spec.tipo == "Nominal":
        # Nominal Anual [Periodicidad] [Vencida/Anticipada], p. ej. NAMV, NATA
        if spec.periodicidad == "Anual":
            return f"NA{m_abrev}"
        return f"NA{p_abrev}{m_abrev}"

    # Efectiva
    if spec.periodicidad == "Anual" and spec.modalidad == "Vencida":
        return "EA"
    return f"E{p_abrev}{m_abrev}"


def convert_rate(
    rate_percent: float,
    source: RateSpec,
    target: RateSpec,
) -> RateConversionResult:
    """Convierte una tasa ingresada en porcentaje entre cualquier par de especificaciones.

    Args:
        rate_percent: Tasa inicial expresada en porcentaje (p. ej. 24 para 24%).
        source: Especificación de la tasa inicial.
        target: Especificación de la tasa objetivo.

    Returns:
        RateConversionResult con todas las tasas intermedias y finales en decimal
        (multiplicar por 100 para porcentaje).

    Raises:
        ValueError: Si la tasa produce denominadores inválidos, es negativa,
            no es finita o es una tasa anticipada >= 100% en su periodo.
    """
    m_in = source.validate()
    m_out = target.validate()

    if not isinstance(rate_percent, (int, float)) or not math.isfinite(rate_percent):
        raise ValueError("La tasa de interés debe ser un número finito válido.")

    if rate_percent < 0:
        raise ValueError("La tasa de interés inicial no puede ser negativa.")

    r_in = float(rate_percent) / 100.0

    # Paso 1: Tasa periódica de origen (i_p_in)
    if source.tipo == "Nominal":
        i_p_in = r_in / m_in
    else:
        i_p_in = r_in

    # Paso 2: Conversión a tasa periódica vencida (i_v_in) con validación de denominadores
    if source.modalidad == "Anticipada":
        if i_p_in >= 1.0:
            raise ValueError(
                f"La tasa periódica anticipada ({i_p_in * 100:.4f}% en periodo "
                f"{source.periodicidad.lower()}) no puede ser igual o mayor al 100%, "
                "ya que produce un denominador inválido (1 - i_a <= 0)."
            )
        denom = 1.0 - i_p_in
        if denom <= 0.0:
            raise ValueError("Denominador inválido al convertir tasa anticipada a vencida.")
        i_v_in = i_p_in / denom
    else:
        if 1.0 + i_p_in <= 0.0:
            raise ValueError(
                "La tasa periódica vencida produce un factor inválido (1 + i_v <= 0)."
            )
        i_v_in = i_p_in

    # Paso 3: Tasa Efectiva Anual vencida equivalente (EA)
    try:
        ea = math.pow(1.0 + i_v_in, m_in) - 1.0
    except OverflowError as exc:
        raise ValueError(
            "La tasa ingresada es demasiado grande y provoca desbordamiento numérico."
        ) from exc

    if not math.isfinite(ea) or (1.0 + ea) <= 0.0:
        raise ValueError(
            "No fue posible calcular una tasa Efectiva Anual válida con los datos ingresados."
        )

    # Paso 4: Tasa periódica vencida objetivo (i_v_out) -> usada en amortización
    i_v_out = math.pow(1.0 + ea, 1.0 / m_out) - 1.0

    # Paso 5: Tasa periódica en modalidad objetivo (i_p_out)
    if target.modalidad == "Anticipada":
        denom_out = 1.0 + i_v_out
        if denom_out <= 0.0:
            raise ValueError("Denominador inválido al convertir tasa vencida a anticipada.")
        i_p_out = i_v_out / denom_out
        if i_p_out >= 1.0:
            raise ValueError(
                "La tasa periódica anticipada resultante alcanzó o superó el 100%."
            )
    else:
        i_p_out = i_v_out

    # Paso 6: Tasa objetivo expresada en su tipo (Efectiva o Nominal)
    if target.tipo == "Nominal":
        r_out = i_p_out * m_out
    else:
        r_out = i_p_out

    return RateConversionResult(
        input_rate=r_in,
        source=source,
        target=target,
        source_periodic_rate=i_p_in,
        source_periodic_vencida=i_v_in,
        effective_annual_rate=ea,
        target_periodic_vencida=i_v_out,
        target_periodic_rate=i_p_out,
        converted_rate=r_out,
    )
