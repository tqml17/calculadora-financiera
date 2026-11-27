# Calculadora Financiera — Conversor de Tasas y Tabla de Amortización Constante

Aplicación de escritorio en Python (interfaz gráfica con **Tkinter / ttk**, 100 % biblioteca estándar, sin dependencias externas) que convierte tasas de interés entre cualquier combinación de tipo, modalidad y periodicidad, y genera la tabla de amortización con **abono constante a capital** (sistema alemán), incluyendo periodos de gracia y abonos extra.

## Requisitos

- Python 3.9 o superior (incluye `tkinter` en la instalación estándar de Python para Windows y macOS; en Linux puede requerir `python3-tk`).

## Cómo ejecutar

Desde la carpeta del proyecto:

```bash
python main.py
```

Para ejecutar las pruebas unitarias:

```bash
python -m unittest discover -s tests -v
```

## Estructura del proyecto

```text
calculadora_financiera/
├── main.py                  # Punto de entrada de la aplicación de escritorio
├── finance/
│   ├── __init__.py          # Exportaciones del motor financiero
│   ├── rates.py             # Conversión exacta de tasas y validaciones matemáticas
│   ├── amortization.py      # Motor de amortización constante, periodos de gracia y abonos extra
│   └── validators.py        # Parseo y validación robusta de campos numéricos
├── ui/
│   ├── __init__.py
│   └── app.py               # Interfaz gráfica en Tkinter/ttk con tabla desplazable y exportación CSV
└── tests/
    └── test_finance.py      # Pruebas unitarias de tasas, amortización y validadores
```

## Resumen de fórmulas financieras

### 1. Conversión de tasas
Sea $m$ el número de periodos por año (`Mensual: 12`, `Bimestral: 6`, `Trimestral: 4`, `Cuatrimestral: 3`, `Semestral: 2`, `Anual: 1`):

1. **Tasa periódica inicial** ($i_p$): $j/m$ si es Nominal, o $i$ si es Efectiva.
2. **A periódica vencida** ($i_v$): $i_v = i_p$ si es Vencida; $i_v = \dfrac{i_p}{1 - i_p}$ si es Anticipada (validando $i_p < 100\%$).
3. **Efectiva Anual equivalente ($EA$)**: $EA = (1 + i_v)^m - 1$.
4. **Periódica vencida objetivo** ($i_{v,\text{obj}}$, usada en la amortización): $i_{v,\text{obj}} = (1 + EA)^{1/m_{\text{obj}}} - 1$.
5. **Periódica en modalidad objetivo**: $i_{v,\text{obj}}$ si es Vencida; $\dfrac{i_{v,\text{obj}}}{1 + i_{v,\text{obj}}}$ si es Anticipada.
6. **Tasa objetivo expresada**: se multiplica por $m_{\text{obj}}$ si es Nominal; se deja igual si es Efectiva.

### 2. Amortización con abono constante a capital
- **Gracia parcial (con pago de intereses)**: durante los $g$ periodos de gracia el abono ordinario a capital es $0$ y se paga únicamente el interés del periodo.
- **Gracia muerta (capitalización)**: durante los $g$ periodos de gracia no se paga cuota (salvo abonos extra) y los intereses causados se suman al saldo.
- **Abono constante a capital**: tras la gracia, el saldo vigente se divide en partes iguales entre los $N - g$ periodos restantes.
- **Abonos extra**:
  - *Reducir plazo*: conserva el abono ordinario constante y acorta el número de periodos.
  - *Reducir cuota*: recalcula el abono ordinario constante sobre el nuevo saldo entre los periodos restantes ($N - t$).
