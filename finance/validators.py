"""Utilidades de parseo y validación de entradas numéricas para la interfaz."""

from __future__ import annotations

import math
import re
from typing import Optional

_THOUSANDS_COMMA_RE = re.compile(r"^[+-]?\d{1,3}(,\d{3})+$")
_THOUSANDS_DOT_RE = re.compile(r"^[+-]?\d{1,3}(\.\d{3})+$")


def parse_number(
    raw_value: str,
    field_name: str,
    *,
    allow_zero: bool = False,
    allow_negative: bool = False,
    is_percentage: bool = False,
) -> float:
    """Convierte texto ingresado por el usuario a float con mensajes de error claros.

    Soporta separador decimal con punto ('.') o coma (','), y limpia símbolos
    comunes como '$', '%' y espacios. Rechaza texto no numérico, NaN e infinito.
    """
    if raw_value is None or not str(raw_value).strip():
        raise ValueError(f"El campo '{field_name}' es obligatorio.")

    cleaned = str(raw_value).strip().replace("$", "").replace("%", "").replace(" ", "")

    if "," in cleaned and "." in cleaned:
        # El último separador se interpreta como decimal y el otro como miles
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        if not is_percentage and _THOUSANDS_COMMA_RE.match(cleaned):
            cleaned = cleaned.replace(",", "")
        elif cleaned.count(",") == 1:
            cleaned = cleaned.replace(",", ".")
        else:
            raise ValueError(
                f"Formato numérico inválido en '{field_name}': '{raw_value}'."
            )
    elif "." in cleaned and not is_percentage and cleaned.count(".") > 1:
        if _THOUSANDS_DOT_RE.match(cleaned):
            cleaned = cleaned.replace(".", "")
        else:
            raise ValueError(
                f"Formato numérico inválido en '{field_name}': '{raw_value}'."
            )

    try:
        value = float(cleaned)
    except ValueError as exc:
        raise ValueError(
            f"El campo '{field_name}' debe contener un valor numérico válido "
            f"(se recibió '{raw_value}')."
        ) from exc

    if not math.isfinite(value):
        raise ValueError(f"El campo '{field_name}' debe ser un número finito válido.")

    if not allow_negative and value < 0:
        raise ValueError(f"El campo '{field_name}' no puede ser negativo.")

    if not allow_zero and value == 0:
        raise ValueError(f"El campo '{field_name}' debe ser mayor que cero.")

    return value


def parse_positive_int(
    raw_value: str,
    field_name: str,
    *,
    allow_zero: bool = False,
) -> int:
    """Convierte texto ingresado a entero no negativo o positivo con validación estricta."""
    val = parse_number(
        raw_value,
        field_name,
        allow_zero=allow_zero,
        allow_negative=False,
        is_percentage=False,
    )
    rounded = round(val)
    if abs(val - rounded) > 1e-9:
        raise ValueError(f"El campo '{field_name}' debe ser un número entero.")
    return int(rounded)


def parse_optional_positive_int(raw_value: str, field_name: str) -> Optional[int]:
    """Parsea un entero positivo si el campo no está vacío; retorna None si está vacío."""
    if raw_value is None or not str(raw_value).strip():
        return None
    return parse_positive_int(raw_value, field_name, allow_zero=False)
