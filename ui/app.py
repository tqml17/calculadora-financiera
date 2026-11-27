"""Interfaz gráfica de escritorio (Tkinter/ttk) para conversión de tasas y amortización.

Organiza la aplicación en tres bloques principales:
1. Conversión de tasas de interés (Efectiva/Nominal, Vencida/Anticipada y 6 periodicidades).
2. Parámetros del préstamo con abono constante a capital, periodos de gracia y abonos extra.
3. Tabla de amortización desplazable con fila de totales generales, resumen KPI y exportación CSV.
"""

from __future__ import annotations

import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

from finance.amortization import (
    EFFECT_REDUCE_PAYMENT,
    EFFECT_REDUCE_TERM,
    EXTRA_EFFECTS,
    EXTRA_MODES,
    EXTRA_RECURRING,
    EXTRA_SINGLE,
    GRACE_DEAD,
    GRACE_NONE,
    GRACE_PARTIAL,
    GRACE_TYPES,
    TERM_UNITS,
    AmortizationSchedule,
    ExtraPaymentRule,
    generate_amortization_schedule,
    resolve_total_periods,
)
from finance.rates import (
    MODALIDADES,
    PERIODICIDADES,
    TIPOS_TASA,
    RateConversionResult,
    RateSpec,
    convert_rate,
)
from finance.validators import (
    parse_number,
    parse_optional_positive_int,
    parse_positive_int,
)

# Paleta de colores corporativa y sobria
COLORS = {
    "bg": "#F1F5F9",
    "surface": "#FFFFFF",
    "border": "#CBD5E1",
    "header_bg": "#0F172A",
    "header_fg": "#F8FAFC",
    "header_sub": "#94A3B8",
    "primary": "#1D4ED8",
    "primary_hover": "#1E40AF",
    "secondary": "#0F766E",
    "secondary_hover": "#115E59",
    "neutral": "#475569",
    "neutral_hover": "#334155",
    "danger": "#B91C1C",
    "danger_bg": "#FEF2F2",
    "ok_fg": "#065F46",
    "ok_bg": "#ECFDF5",
    "info_fg": "#1E3A8A",
    "info_bg": "#EFF6FF",
    "text": "#0F172A",
    "muted": "#475569",
    "row_even": "#FFFFFF",
    "row_odd": "#F8FAFC",
    "row_grace": "#FEF9C3",
    "row_extra": "#ECFDF5",
    "row_total": "#DBEAFE",
}


class FinancialCalculatorApp(tk.Tk):
    """Ventana principal de la calculadora financiera."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Calculadora Financiera — Conversión de Tasas y Amortización Constante")
        self.geometry("1340x860")
        self.minsize(1060, 700)
        self.configure(bg=COLORS["bg"])

        self._last_conversion: Optional[RateConversionResult] = None
        self._last_schedule: Optional[AmortizationSchedule] = None
        self._extra_rules: List[ExtraPaymentRule] = []

        self._configure_styles()
        self._init_variables()
        self._build_layout()
        self._bind_dynamic_events()

        # Ejecutar conversión inicial con valores de ejemplo listos para probar
        self._on_convert_rate(silent=True)

    # ------------------------------------------------------------------
    # Configuración de estilos ttk
    # ------------------------------------------------------------------
    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(".", font=("Segoe UI", 9), foreground=COLORS["text"])
        style.configure("App.TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["surface"])
        style.configure(
            "Card.TLabelframe",
            background=COLORS["surface"],
            bordercolor=COLORS["border"],
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=COLORS["surface"],
            foreground=COLORS["primary"],
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "Sub.TLabelframe",
            background=COLORS["surface"],
            bordercolor=COLORS["border"],
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "Sub.TLabelframe.Label",
            background=COLORS["surface"],
            foreground=COLORS["secondary"],
            font=("Segoe UI", 9, "bold"),
        )
        style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["text"])
        style.configure(
            "Muted.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["muted"],
            font=("Segoe UI", 8),
        )
        style.configure(
            "FieldBold.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "ResultTitle.TLabel",
            background=COLORS["info_bg"],
            foreground=COLORS["muted"],
            font=("Segoe UI", 8, "bold"),
        )
        style.configure(
            "ResultValue.TLabel",
            background=COLORS["info_bg"],
            foreground=COLORS["info_fg"],
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "ResultAccent.TLabel",
            background=COLORS["ok_bg"],
            foreground=COLORS["ok_fg"],
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "ResultAccentTitle.TLabel",
            background=COLORS["ok_bg"],
            foreground=COLORS["ok_fg"],
            font=("Segoe UI", 8, "bold"),
        )
        style.configure("Card.TCheckbutton", background=COLORS["surface"], foreground=COLORS["text"])

        # Botones
        style.configure(
            "Primary.TButton",
            background=COLORS["primary"],
            foreground="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            padding=(12, 6),
            borderwidth=0,
        )
        style.map(
            "Primary.TButton",
            background=[("active", COLORS["primary_hover"]), ("disabled", "#94A3B8")],
            foreground=[("disabled", "#E2E8F0")],
        )

        style.configure(
            "Secondary.TButton",
            background=COLORS["secondary"],
            foreground="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            padding=(10, 6),
            borderwidth=0,
        )
        style.map(
            "Secondary.TButton",
            background=[("active", COLORS["secondary_hover"]), ("disabled", "#94A3B8")],
        )

        style.configure(
            "Neutral.TButton",
            background=COLORS["neutral"],
            foreground="#FFFFFF",
            font=("Segoe UI", 9),
            padding=(10, 6),
            borderwidth=0,
        )
        style.map(
            "Neutral.TButton",
            background=[("active", COLORS["neutral_hover"])],
        )

        style.configure(
            "Small.TButton",
            background="#E2E8F0",
            foreground=COLORS["text"],
            font=("Segoe UI", 8, "bold"),
            padding=(8, 4),
            borderwidth=0,
        )
        style.map("Small.TButton", background=[("active", "#CBD5E1")])

        # Treeview de amortización
        style.configure(
            "Amort.Treeview",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            fieldbackground=COLORS["surface"],
            rowheight=25,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Amort.Treeview.Heading",
            background="#1E293B",
            foreground="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            padding=(6, 6),
            relief="flat",
        )
        style.map("Amort.Treeview.Heading", background=[("active", "#334155")])

        # KPI Cards
        style.configure("KPI.TFrame", background="#F8FAFC", relief="solid", borderwidth=1)
        style.configure("KPITitle.TLabel", background="#F8FAFC", foreground=COLORS["muted"], font=("Segoe UI", 8))
        style.configure("KPIValue.TLabel", background="#F8FAFC", foreground=COLORS["text"], font=("Segoe UI", 10, "bold"))

    # ------------------------------------------------------------------
    # Variables de control Tkinter
    # ------------------------------------------------------------------
    def _init_variables(self) -> None:
        # Bloque 1: Conversión de tasas
        self.var_src_rate = tk.StringVar(value="24")
        self.var_src_type = tk.StringVar(value="Nominal")
        self.var_src_mod = tk.StringVar(value="Vencida")
        self.var_src_per = tk.StringVar(value="Mensual")

        self.var_tgt_type = tk.StringVar(value="Efectiva")
        self.var_tgt_mod = tk.StringVar(value="Vencida")
        self.var_tgt_per = tk.StringVar(value="Mensual")

        # Salidas de conversión
        self.var_res_converted = tk.StringVar(value="—")
        self.var_res_periodic_tgt = tk.StringVar(value="—")
        self.var_res_ea = tk.StringVar(value="—")
        self.var_res_amort_rate = tk.StringVar(value="—")

        # Bloque 2: Parámetros del préstamo
        self.var_principal = tk.StringVar(value="10000000")
        self.var_term_value = tk.StringVar(value="12")
        self.var_term_unit = tk.StringVar(value="Periodos")
        self.var_term_preview = tk.StringVar(value="= 12 periodos")

        self.var_use_converted = tk.BooleanVar(value=True)
        self.var_amort_rate_pct = tk.StringVar(value="2.000000")
        self.var_amort_periodicity = tk.StringVar(value="Mensual")

        self.var_grace_type = tk.StringVar(value=GRACE_NONE)
        self.var_grace_periods = tk.StringVar(value="0")

        # Abonos extra
        self.var_extra_mode = tk.StringVar(value=EXTRA_SINGLE)
        self.var_extra_start = tk.StringVar(value="6")
        self.var_extra_freq = tk.StringVar(value="6")
        self.var_extra_end = tk.StringVar(value="")
        self.var_extra_amount = tk.StringVar(value="")
        self.var_extra_effect = tk.StringVar(value=EFFECT_REDUCE_TERM)

        # Estado / Errores
        self.var_status = tk.StringVar(
            value="Listo. Convierta una tasa y presione 'Calcular y Generar Tabla' para ver la amortización."
        )

        # KPIs resumen
        self.var_kpi_principal = tk.StringVar(value="$0.00")
        self.var_kpi_periods = tk.StringVar(value="0")
        self.var_kpi_rate = tk.StringVar(value="0.0000%")
        self.var_kpi_total_cap = tk.StringVar(value="$0.00")
        self.var_kpi_total_int = tk.StringVar(value="$0.00")
        self.var_kpi_total_pay = tk.StringVar(value="$0.00")
        self.var_kpi_savings = tk.StringVar(value="—")

    # ------------------------------------------------------------------
    # Construcción del layout
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        # Encabezado superior
        header = tk.Frame(self, bg=COLORS["header_bg"], padx=18, pady=10)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="Calculadora Financiera — Tasas de Interés y Amortización Constante",
            bg=COLORS["header_bg"],
            fg=COLORS["header_fg"],
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")

        tk.Label(
            header,
            text=(
                "Conversión exacta (Efectiva/Nominal, Vencida/Anticipada) y tabla de amortización "
                "con abono constante a capital, periodos de gracia y abonos extra"
            ),
            bg=COLORS["header_bg"],
            fg=COLORS["header_sub"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(2, 0))

        # Banner de estado / errores (siempre visible, sin cerrar la app)
        self.status_frame = tk.Frame(self, bg=COLORS["info_bg"], padx=14, pady=6)
        self.status_frame.pack(fill=tk.X)
        self.status_label = tk.Label(
            self.status_frame,
            textvariable=self.var_status,
            bg=COLORS["info_bg"],
            fg=COLORS["info_fg"],
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=1260,
        )
        self.status_label.pack(fill=tk.X)

        # Contenedor principal con divisor vertical ajustable entre formularios y tabla
        paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 12))

        top_container = ttk.Frame(paned, style="App.TFrame")
        bottom_container = ttk.Frame(paned, style="App.TFrame")

        paned.add(top_container, weight=0)
        paned.add(bottom_container, weight=1)

        # Panel superior en 2 columnas equilibradas
        top_container.columnconfigure(0, weight=5, uniform="top_cols")
        top_container.columnconfigure(1, weight=7, uniform="top_cols")
        top_container.rowconfigure(0, weight=1)

        self._build_rate_converter_panel(top_container)
        self._build_loan_params_panel(top_container)
        self._build_amortization_table_panel(bottom_container)

    def _build_rate_converter_panel(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(
            parent,
            text="  1. Conversión de Tasas de Interés  ",
            style="Card.TLabelframe",
            padding=(12, 8),
        )
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)

        # --- Tasa inicial ---
        ttk.Label(card, text="Tasa Inicial", style="FieldBold.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 4)
        )

        ttk.Label(card, text="Valor (%):", style="Card.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=3
        )
        self.entry_src_rate = ttk.Entry(card, textvariable=self.var_src_rate, width=14)
        self.entry_src_rate.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=3)

        ttk.Label(card, text="Tipo:", style="Card.TLabel").grid(
            row=1, column=2, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Combobox(
            card,
            textvariable=self.var_src_type,
            values=TIPOS_TASA,
            state="readonly",
            width=12,
        ).grid(row=1, column=3, sticky="ew", pady=3)

        ttk.Label(card, text="Modalidad:", style="Card.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Combobox(
            card,
            textvariable=self.var_src_mod,
            values=MODALIDADES,
            state="readonly",
            width=12,
        ).grid(row=2, column=1, sticky="ew", padx=(0, 10), pady=3)

        ttk.Label(card, text="Periodicidad:", style="Card.TLabel").grid(
            row=2, column=2, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Combobox(
            card,
            textvariable=self.var_src_per,
            values=tuple(PERIODICIDADES.keys()),
            state="readonly",
            width=14,
        ).grid(row=2, column=3, sticky="ew", pady=3)

        ttk.Separator(card, orient=tk.HORIZONTAL).grid(
            row=3, column=0, columnspan=4, sticky="ew", pady=8
        )

        # --- Tasa objetivo ---
        ttk.Label(card, text="Tasa Objetivo", style="FieldBold.TLabel").grid(
            row=4, column=0, columnspan=4, sticky="w", pady=(0, 4)
        )

        ttk.Label(card, text="Tipo:", style="Card.TLabel").grid(
            row=5, column=0, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Combobox(
            card,
            textvariable=self.var_tgt_type,
            values=TIPOS_TASA,
            state="readonly",
            width=12,
        ).grid(row=5, column=1, sticky="ew", padx=(0, 10), pady=3)

        ttk.Label(card, text="Modalidad:", style="Card.TLabel").grid(
            row=5, column=2, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Combobox(
            card,
            textvariable=self.var_tgt_mod,
            values=MODALIDADES,
            state="readonly",
            width=12,
        ).grid(row=5, column=3, sticky="ew", pady=3)

        ttk.Label(card, text="Periodicidad:", style="Card.TLabel").grid(
            row=6, column=0, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Combobox(
            card,
            textvariable=self.var_tgt_per,
            values=tuple(PERIODICIDADES.keys()),
            state="readonly",
            width=14,
        ).grid(row=6, column=1, sticky="ew", padx=(0, 10), pady=3)

        ttk.Label(
            card,
            text="Periodos/año: M=12, B=6, T=4, C=3, S=2, A=1",
            style="Muted.TLabel",
        ).grid(row=6, column=2, columnspan=2, sticky="w", pady=3)

        # Botones de conversión
        btn_row = ttk.Frame(card, style="Card.TFrame")
        btn_row.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(10, 8))

        ttk.Button(
            btn_row,
            text="Convertir Tasa",
            style="Primary.TButton",
            command=self._on_convert_rate,
        ).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(
            btn_row,
            text="Aplicar a Amortización",
            style="Secondary.TButton",
            command=self._apply_converted_rate_to_loan,
        ).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(
            btn_row,
            text="Limpiar Tasas",
            style="Neutral.TButton",
            command=self._reset_rate_fields,
        ).pack(side=tk.RIGHT)

        # --- Resultados de conversión ---
        res_box = tk.Frame(card, bg=COLORS["info_bg"], bd=1, relief="solid", padx=10, pady=8)
        res_box.grid(row=8, column=0, columnspan=4, sticky="ew", pady=(2, 6))
        res_box.columnconfigure(0, weight=1)
        res_box.columnconfigure(1, weight=1)

        ttk.Label(res_box, text="TASA CONVERTIDA RESULTANTE", style="ResultTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(res_box, text="EFECTIVA ANUAL EQUIVALENTE (EA)", style="ResultTitle.TLabel").grid(
            row=0, column=1, sticky="w", padx=(10, 0)
        )
        ttk.Label(res_box, textvariable=self.var_res_converted, style="ResultValue.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 6)
        )
        ttk.Label(res_box, textvariable=self.var_res_ea, style="ResultValue.TLabel").grid(
            row=1, column=1, sticky="w", padx=(10, 0), pady=(2, 6)
        )

        ttk.Label(
            res_box,
            text="Tasa periódica en modalidad objetivo:",
            style="ResultTitle.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Label(
            res_box,
            textvariable=self.var_res_periodic_tgt,
            background=COLORS["info_bg"],
            foreground=COLORS["text"],
            font=("Segoe UI", 9, "bold"),
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(1, 0))

        # Destacado: tasa periódica vencida usada en la tabla de amortización
        amort_box = tk.Frame(card, bg=COLORS["ok_bg"], bd=1, relief="solid", padx=10, pady=7)
        amort_box.grid(row=9, column=0, columnspan=4, sticky="ew")

        ttk.Label(
            amort_box,
            text="TASA PERIÓDICA EQUIVALENTE PARA AMORTIZACIÓN (VENCIDA)",
            style="ResultAccentTitle.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            amort_box,
            textvariable=self.var_res_amort_rate,
            style="ResultAccent.TLabel",
        ).pack(anchor="w", pady=(2, 0))

    def _build_loan_params_panel(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(
            parent,
            text="  2. Parámetros del Préstamo (Abono Constante a Capital)  ",
            style="Card.TLabelframe",
            padding=(12, 8),
        )
        card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)

        # Fila 0: Monto y Plazo
        ttk.Label(card, text="Monto del préstamo ($):", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Entry(card, textvariable=self.var_principal, width=18).grid(
            row=0, column=1, sticky="ew", padx=(0, 12), pady=3
        )

        ttk.Label(card, text="Plazo total:", style="Card.TLabel").grid(
            row=0, column=2, sticky="w", padx=(0, 6), pady=3
        )
        term_frame = ttk.Frame(card, style="Card.TFrame")
        term_frame.grid(row=0, column=3, sticky="ew", pady=3)
        ttk.Entry(term_frame, textvariable=self.var_term_value, width=8).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Combobox(
            term_frame,
            textvariable=self.var_term_unit,
            values=TERM_UNITS,
            state="readonly",
            width=9,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(term_frame, textvariable=self.var_term_preview, style="Muted.TLabel").pack(
            side=tk.LEFT
        )

        # Fila 1: Tasa de amortización (sincronizada o manual)
        ttk.Checkbutton(
            card,
            text="Usar automáticamente la tasa periódica vencida convertida",
            variable=self.var_use_converted,
            style="Card.TCheckbutton",
            command=self._toggle_amort_rate_mode,
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 2))

        ttk.Label(card, text="Tasa periódica vencida (%):", style="Card.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 6), pady=3
        )
        self.entry_amort_rate = ttk.Entry(card, textvariable=self.var_amort_rate_pct, width=18)
        self.entry_amort_rate.grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=3)

        ttk.Label(card, text="Periodicidad de pago:", style="Card.TLabel").grid(
            row=2, column=2, sticky="w", padx=(0, 6), pady=3
        )
        self.combo_amort_per = ttk.Combobox(
            card,
            textvariable=self.var_amort_periodicity,
            values=tuple(PERIODICIDADES.keys()),
            state="readonly",
            width=14,
        )
        self.combo_amort_per.grid(row=2, column=3, sticky="ew", pady=3)

        # Fila 3: Periodos de gracia
        ttk.Label(card, text="Tipo periodo de gracia:", style="Card.TLabel").grid(
            row=3, column=0, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Combobox(
            card,
            textvariable=self.var_grace_type,
            values=GRACE_TYPES,
            state="readonly",
            width=28,
        ).grid(row=3, column=1, sticky="ew", padx=(0, 12), pady=3)

        ttk.Label(card, text="Periodos de gracia:", style="Card.TLabel").grid(
            row=3, column=2, sticky="w", padx=(0, 6), pady=3
        )
        grace_num_frame = ttk.Frame(card, style="Card.TFrame")
        grace_num_frame.grid(row=3, column=3, sticky="ew", pady=3)
        self.entry_grace_periods = ttk.Entry(
            grace_num_frame, textvariable=self.var_grace_periods, width=8
        )
        self.entry_grace_periods.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(
            grace_num_frame, text="(incluidos en plazo total)", style="Muted.TLabel"
        ).pack(side=tk.LEFT)

        # --- Sub-panel de Abonos Extra a Capital ---
        extra_box = ttk.LabelFrame(
            card,
            text="  Abonos Extra a Capital (opcional)  ",
            style="Sub.TLabelframe",
            padding=(8, 6),
        )
        extra_box.grid(row=4, column=0, columnspan=4, sticky="nsew", pady=(8, 6))
        extra_box.columnconfigure(1, weight=1)
        extra_box.columnconfigure(3, weight=1)
        extra_box.columnconfigure(5, weight=1)

        # Fila 0 de abonos extra: Modalidad, Efecto, Monto
        ttk.Label(extra_box, text="Aplicación:", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 4), pady=2
        )
        ttk.Combobox(
            extra_box,
            textvariable=self.var_extra_mode,
            values=EXTRA_MODES,
            state="readonly",
            width=16,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=2)

        ttk.Label(extra_box, text="Efecto:", style="Card.TLabel").grid(
            row=0, column=2, sticky="w", padx=(0, 4), pady=2
        )
        ttk.Combobox(
            extra_box,
            textvariable=self.var_extra_effect,
            values=EXTRA_EFFECTS,
            state="readonly",
            width=14,
        ).grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=2)

        ttk.Label(extra_box, text="Monto ($):", style="Card.TLabel").grid(
            row=0, column=4, sticky="w", padx=(0, 4), pady=2
        )
        ttk.Entry(extra_box, textvariable=self.var_extra_amount, width=13).grid(
            row=0, column=5, sticky="ew", pady=2
        )

        # Fila 1 de abonos extra: Periodo/Inicio, Cada, Hasta, botones
        self.lbl_extra_start = ttk.Label(extra_box, text="Periodo:", style="Card.TLabel")
        self.lbl_extra_start.grid(row=1, column=0, sticky="w", padx=(0, 4), pady=2)
        ttk.Entry(extra_box, textvariable=self.var_extra_start, width=10).grid(
            row=1, column=1, sticky="ew", padx=(0, 8), pady=2
        )

        ttk.Label(extra_box, text="Cada (per.):", style="Card.TLabel").grid(
            row=1, column=2, sticky="w", padx=(0, 4), pady=2
        )
        self.entry_extra_freq = ttk.Entry(extra_box, textvariable=self.var_extra_freq, width=8)
        self.entry_extra_freq.grid(row=1, column=3, sticky="ew", padx=(0, 8), pady=2)

        ttk.Label(extra_box, text="Hasta (opc.):", style="Card.TLabel").grid(
            row=1, column=4, sticky="w", padx=(0, 4), pady=2
        )
        self.entry_extra_end = ttk.Entry(extra_box, textvariable=self.var_extra_end, width=8)
        self.entry_extra_end.grid(row=1, column=5, sticky="ew", pady=2)

        # Fila 2: Lista de abonos extra agregados y controles
        list_row = ttk.Frame(extra_box, style="Card.TFrame")
        list_row.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(5, 0))
        list_row.columnconfigure(0, weight=1)

        self.listbox_extras = tk.Listbox(
            list_row,
            height=3,
            font=("Segoe UI", 8),
            bg="#F8FAFC",
            fg=COLORS["text"],
            selectbackground=COLORS["primary"],
            relief="solid",
            borderwidth=1,
        )
        self.listbox_extras.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        extra_scroll = ttk.Scrollbar(list_row, orient=tk.VERTICAL, command=self.listbox_extras.yview)
        extra_scroll.grid(row=0, column=1, sticky="ns", padx=(0, 8))
        self.listbox_extras.configure(yscrollcommand=extra_scroll.set)

        extra_btns = ttk.Frame(list_row, style="Card.TFrame")
        extra_btns.grid(row=0, column=2, sticky="ns")
        ttk.Button(
            extra_btns, text="+ Agregar abono", style="Small.TButton", command=self._add_extra_payment
        ).pack(fill=tk.X, pady=(0, 3))
        ttk.Button(
            extra_btns, text="Quitar sel.", style="Small.TButton", command=self._remove_extra_payment
        ).pack(fill=tk.X, pady=(0, 3))
        ttk.Button(
            extra_btns, text="Limpiar lista", style="Small.TButton", command=self._clear_extra_payments
        ).pack(fill=tk.X)

        # Botones principales de acción del préstamo
        action_bar = ttk.Frame(card, style="Card.TFrame")
        action_bar.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(4, 0))

        ttk.Button(
            action_bar,
            text="Calcular y Generar Tabla",
            style="Primary.TButton",
            command=self._on_calculate_all,
        ).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(
            action_bar,
            text="Actualizar Tabla",
            style="Secondary.TButton",
            command=self._on_generate_schedule,
        ).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(
            action_bar,
            text="Limpiar / Reiniciar Todo",
            style="Neutral.TButton",
            command=self._reset_all,
        ).pack(side=tk.RIGHT)

        # Estado inicial de controles condicionales
        self._toggle_amort_rate_mode()
        self._toggle_grace_fields()
        self._toggle_extra_mode_fields()

    def _build_amortization_table_panel(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(
            parent,
            text="  3. Tabla de Amortización — Abono Constante a Capital  ",
            style="Card.TLabelframe",
            padding=(10, 8),
        )
        card.pack(fill=tk.BOTH, expand=True)
        card.rowconfigure(1, weight=1)
        card.columnconfigure(0, weight=1)

        # Franja superior de KPIs + botón Exportar CSV
        top_strip = ttk.Frame(card, style="Card.TFrame")
        top_strip.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        kpis = [
            ("Capital Inicial", self.var_kpi_principal),
            ("Plazo Efectivo", self.var_kpi_periods),
            ("Tasa Periódica", self.var_kpi_rate),
            ("Total Abono Capital", self.var_kpi_total_cap),
            ("Total Intereses", self.var_kpi_total_int),
            ("Total Pagado (Cuotas)", self.var_kpi_total_pay),
            ("Ahorro (Abonos Extra)", self.var_kpi_savings),
        ]
        for idx, (title, var) in enumerate(kpis):
            top_strip.columnconfigure(idx, weight=1)
            box = ttk.Frame(top_strip, style="KPI.TFrame", padding=(8, 4))
            box.grid(row=0, column=idx, sticky="ew", padx=(0, 6))
            ttk.Label(box, text=title, style="KPITitle.TLabel").pack(anchor="w")
            ttk.Label(box, textvariable=var, style="KPIValue.TLabel").pack(anchor="w")

        ttk.Button(
            top_strip,
            text="Exportar CSV",
            style="Small.TButton",
            command=self._export_csv,
        ).grid(row=0, column=len(kpis), sticky="ns")

        # Contenedor del Treeview con scrollbars vertical y horizontal
        table_wrap = ttk.Frame(card, style="Card.TFrame")
        table_wrap.grid(row=1, column=0, sticky="nsew")
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        columns = (
            "periodo",
            "saldo_inicial",
            "abono_capital",
            "interes",
            "cuota_total",
            "saldo_final",
            "detalle",
        )
        self.tree = ttk.Treeview(
            table_wrap,
            columns=columns,
            show="headings",
            style="Amort.Treeview",
            selectmode="browse",
        )

        col_config = [
            ("periodo", "Periodo", 85, "center"),
            ("saldo_inicial", "Saldo Inicial", 155, "e"),
            ("abono_capital", "Abono a Capital (incl. extra)", 185, "e"),
            ("interes", "Interés", 145, "e"),
            ("cuota_total", "Cuota Total", 155, "e"),
            ("saldo_final", "Saldo Final", 155, "e"),
            ("detalle", "Tipo / Detalle", 260, "w"),
        ]
        for col_id, heading, width, anchor in col_config:
            self.tree.heading(col_id, text=heading, anchor=anchor)
            self.tree.column(col_id, width=width, minwidth=80, anchor=anchor, stretch=True)

        v_scroll = ttk.Scrollbar(table_wrap, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(table_wrap, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        # Colores de filas según tipo de periodo
        self.tree.tag_configure("even", background=COLORS["row_even"])
        self.tree.tag_configure("odd", background=COLORS["row_odd"])
        self.tree.tag_configure("grace", background=COLORS["row_grace"])
        self.tree.tag_configure("extra", background=COLORS["row_extra"])
        self.tree.tag_configure(
            "total",
            background=COLORS["row_total"],
            font=("Segoe UI", 9, "bold"),
        )

        # Leyenda inferior
        legend = ttk.Frame(card, style="Card.TFrame")
        legend.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(
            legend,
            text=(
                "Leyenda:  ■ Amarillo = Periodo de gracia   |   ■ Verde = Periodo con abono extra   |   "
                "■ Azul = Totales generales.  En gracia muerta los intereses se capitalizan al saldo y la cuota es $0 (salvo abono extra)."
            ),
            style="Muted.TLabel",
        ).pack(anchor="w")

    # ------------------------------------------------------------------
    # Eventos dinámicos y sincronización de UI
    # ------------------------------------------------------------------
    def _bind_dynamic_events(self) -> None:
        self.var_grace_type.trace_add("write", lambda *_: self._toggle_grace_fields())
        self.var_extra_mode.trace_add("write", lambda *_: self._toggle_extra_mode_fields())
        self.var_term_value.trace_add("write", lambda *_: self._update_term_preview())
        self.var_term_unit.trace_add("write", lambda *_: self._update_term_preview())
        self.var_amort_periodicity.trace_add("write", lambda *_: self._update_term_preview())
        self.entry_src_rate.bind("<Return>", lambda _e: self._on_convert_rate())

    def _set_status(self, message: str, level: str = "info") -> None:
        self.var_status.set(message)
        if level == "error":
            bg, fg = COLORS["danger_bg"], COLORS["danger"]
        elif level == "ok":
            bg, fg = COLORS["ok_bg"], COLORS["ok_fg"]
        else:
            bg, fg = COLORS["info_bg"], COLORS["info_fg"]
        self.status_frame.configure(bg=bg)
        self.status_label.configure(bg=bg, fg=fg)

    def _toggle_amort_rate_mode(self) -> None:
        if self.var_use_converted.get():
            self.entry_amort_rate.configure(state="readonly")
            self.combo_amort_per.configure(state="disabled")
            if self._last_conversion is not None:
                self._sync_converted_rate_to_fields(self._last_conversion)
        else:
            self.entry_amort_rate.configure(state="normal")
            self.combo_amort_per.configure(state="readonly")

    def _toggle_grace_fields(self) -> None:
        if self.var_grace_type.get() == GRACE_NONE:
            self.var_grace_periods.set("0")
            self.entry_grace_periods.configure(state="disabled")
        else:
            self.entry_grace_periods.configure(state="normal")

    def _toggle_extra_mode_fields(self) -> None:
        if self.var_extra_mode.get() == EXTRA_RECURRING:
            self.lbl_extra_start.configure(text="Desde per.:")
            self.entry_extra_freq.configure(state="normal")
            self.entry_extra_end.configure(state="normal")
        else:
            self.lbl_extra_start.configure(text="Periodo:")
            self.entry_extra_freq.configure(state="disabled")
            self.entry_extra_end.configure(state="disabled")

    def _update_term_preview(self) -> None:
        raw = self.var_term_value.get().strip()
        if not raw:
            self.var_term_preview.set("= —")
            return
        try:
            term_val = parse_number(raw, "Plazo total", allow_zero=False)
            n = resolve_total_periods(
                term_val, self.var_term_unit.get(), self.var_amort_periodicity.get()
            )
            self.var_term_preview.set(f"= {n} periodos")
        except ValueError:
            self.var_term_preview.set("= plazo inválido")

    def _sync_converted_rate_to_fields(self, res: RateConversionResult) -> None:
        self.var_amort_rate_pct.set(f"{res.target_periodic_vencida * 100:.6f}")
        self.var_amort_periodicity.set(res.target.periodicidad)
        self._update_term_preview()

    # ------------------------------------------------------------------
    # Acciones de conversión de tasas
    # ------------------------------------------------------------------
    def _on_convert_rate(self, silent: bool = False) -> bool:
        try:
            rate_pct = parse_number(
                self.var_src_rate.get(),
                "Tasa inicial (%)",
                allow_zero=True,
                allow_negative=False,
                is_percentage=True,
            )
            src_spec = RateSpec(
                tipo=self.var_src_type.get(),
                modalidad=self.var_src_mod.get(),
                periodicidad=self.var_src_per.get(),
            )
            tgt_spec = RateSpec(
                tipo=self.var_tgt_type.get(),
                modalidad=self.var_tgt_mod.get(),
                periodicidad=self.var_tgt_per.get(),
            )
            res = convert_rate(rate_pct, src_spec, tgt_spec)
        except ValueError as err:
            self._set_status(f"Error en conversión de tasas: {err}", level="error")
            if not silent:
                messagebox.showerror("Error en conversión de tasas", str(err))
            return False

        self._last_conversion = res
        self.var_res_converted.set(f"{res.converted_rate * 100:.4f}% {res.target_notation}")
        self.var_res_ea.set(f"{res.effective_annual_rate * 100:.4f}% EA")
        self.var_res_periodic_tgt.set(
            f"{res.target_periodic_rate * 100:.4f}% "
            f"({res.target.periodicidad} {res.target.modalidad})"
        )
        self.var_res_amort_rate.set(
            f"{res.target_periodic_vencida * 100:.4f}% {res.amortization_rate_notation} "
            f"({res.target.periodicidad} Vencida)"
        )

        if self.var_use_converted.get():
            self._sync_converted_rate_to_fields(res)

        if not silent:
            self._set_status(
                f"Conversión exitosa: {rate_pct:.4f}% {res.source_notation} → "
                f"{res.converted_rate * 100:.4f}% {res.target_notation} "
                f"(tasa periódica vencida para amortización: {res.target_periodic_vencida * 100:.4f}%).",
                level="ok",
            )
        return True

    def _apply_converted_rate_to_loan(self) -> None:
        if not self._on_convert_rate(silent=False):
            return
        if self._last_conversion is not None:
            self._sync_converted_rate_to_fields(self._last_conversion)
            self._set_status(
                "Tasa periódica vencida aplicada a los parámetros del préstamo.",
                level="ok",
            )

    def _reset_rate_fields(self) -> None:
        self.var_src_rate.set("")
        self.var_src_type.set("Nominal")
        self.var_src_mod.set("Vencida")
        self.var_src_per.set("Mensual")
        self.var_tgt_type.set("Efectiva")
        self.var_tgt_mod.set("Vencida")
        self.var_tgt_per.set("Mensual")
        self.var_res_converted.set("—")
        self.var_res_periodic_tgt.set("—")
        self.var_res_ea.set("—")
        self.var_res_amort_rate.set("—")
        self._last_conversion = None
        self._set_status("Campos de conversión de tasas limpiados.", level="info")

    # ------------------------------------------------------------------
    # Gestión de abonos extra a capital
    # ------------------------------------------------------------------
    def _add_extra_payment(self) -> None:
        try:
            mode = self.var_extra_mode.get()
            effect = self.var_extra_effect.get()
            amount = parse_number(self.var_extra_amount.get(), "Monto del abono extra", allow_zero=False)
            start_period = parse_positive_int(
                self.var_extra_start.get(), "Periodo del abono extra", allow_zero=False
            )

            if mode == EXTRA_RECURRING:
                frequency = parse_positive_int(
                    self.var_extra_freq.get(), "Frecuencia del abono recurrente", allow_zero=False
                )
                end_period = parse_optional_positive_int(
                    self.var_extra_end.get(), "Periodo final del abono recurrente"
                )
            else:
                frequency = 1
                end_period = None

            rule = ExtraPaymentRule(
                mode=mode,
                amount=amount,
                start_period=start_period,
                effect=effect,
                frequency=frequency,
                end_period=end_period,
            )
            rule.validate()
        except ValueError as err:
            self._set_status(f"Error en abono extra: {err}", level="error")
            messagebox.showerror("Error en abono extra", str(err))
            return

        self._extra_rules.append(rule)
        self.listbox_extras.insert(tk.END, rule.describe())
        self.var_extra_amount.set("")
        self._set_status(f"Abono extra agregado: {rule.describe()}", level="ok")

    def _remove_extra_payment(self) -> None:
        selection = self.listbox_extras.curselection()
        if not selection:
            self._set_status("Seleccione un abono extra de la lista para eliminarlo.", level="info")
            return
        idx = selection[0]
        removed = self._extra_rules.pop(idx)
        self.listbox_extras.delete(idx)
        self._set_status(f"Abono extra eliminado: {removed.describe()}", level="info")

    def _clear_extra_payments(self) -> None:
        self._extra_rules.clear()
        self.listbox_extras.delete(0, tk.END)
        self._set_status("Lista de abonos extra limpiada.", level="info")

    # ------------------------------------------------------------------
    # Cálculo y renderizado de la tabla de amortización
    # ------------------------------------------------------------------
    def _on_calculate_all(self) -> None:
        """Convierte la tasa (si está en modo automático) y genera la tabla."""
        self._on_generate_schedule()

    def _on_generate_schedule(self) -> None:
        if self.var_use_converted.get():
            if not self._on_convert_rate(silent=False):
                return

        try:
            principal = parse_number(
                self.var_principal.get(),
                "Monto del préstamo",
                allow_zero=False,
                allow_negative=False,
            )
            term_val = parse_number(
                self.var_term_value.get(),
                "Plazo total",
                allow_zero=False,
                allow_negative=False,
            )

            if self.var_use_converted.get():
                assert self._last_conversion is not None
                periodic_rate = self._last_conversion.target_periodic_vencida
                periodicity = self._last_conversion.target.periodicidad
            else:
                amort_rate_pct = parse_number(
                    self.var_amort_rate_pct.get(),
                    "Tasa periódica vencida (%)",
                    allow_zero=True,
                    allow_negative=False,
                    is_percentage=True,
                )
                periodic_rate = amort_rate_pct / 100.0
                periodicity = self.var_amort_periodicity.get()

            total_periods = resolve_total_periods(
                term_val, self.var_term_unit.get(), periodicity
            )

            grace_type = self.var_grace_type.get()
            if grace_type == GRACE_NONE:
                grace_periods = 0
            else:
                grace_periods = parse_positive_int(
                    self.var_grace_periods.get(),
                    "Periodos de gracia",
                    allow_zero=True,
                )

            schedule = generate_amortization_schedule(
                principal=principal,
                total_periods=total_periods,
                periodic_rate=periodic_rate,
                grace_periods=grace_periods,
                grace_type=grace_type,
                extra_payments=self._extra_rules,
            )
        except ValueError as err:
            self._set_status(f"Error en parámetros del préstamo: {err}", level="error")
            messagebox.showerror("Error en parámetros del préstamo", str(err))
            return

        self._last_schedule = schedule
        self._render_schedule(schedule, periodicity)

        # Aviso útil si el usuario escribió un monto de abono extra pero olvidó pulsar "+ Agregar"
        unadded_extra = self.var_extra_amount.get().strip()
        extra_hint = (
            " (Nota: tiene un monto en 'Abonos Extra' sin agregar a la lista; pulse '+ Agregar abono' si desea incluirlo)."
            if unadded_extra
            else ""
        )
        self._set_status(
            f"Tabla generada correctamente: {schedule.summary.actual_periods} periodos "
            f"({periodicity.lower()}) a tasa periódica vencida de {periodic_rate * 100:.4f}%.{extra_hint}",
            level="ok",
        )

    def _render_schedule(self, schedule: AmortizationSchedule, periodicity: str) -> None:
        # Limpiar filas previas
        for item in self.tree.get_children():
            self.tree.delete(item)

        s = schedule.summary

        # Actualizar KPIs
        self.var_kpi_principal.set(f"${s.initial_principal:,.2f}")
        if s.actual_periods < s.planned_periods:
            self.var_kpi_periods.set(f"{s.actual_periods} / {s.planned_periods} ({periodicity[:3]}.)")
        else:
            self.var_kpi_periods.set(f"{s.actual_periods} ({periodicity[:3]}.)")
        self.var_kpi_rate.set(f"{s.periodic_rate * 100:.4f}%")
        self.var_kpi_total_cap.set(f"${s.total_principal:,.2f}")
        self.var_kpi_total_int.set(f"${s.total_interest:,.2f}")
        self.var_kpi_total_pay.set(f"${s.total_payment:,.2f}")

        if s.total_extra_principal > 0:
            self.var_kpi_savings.set(
                f"${s.interest_saved:,.2f} ({s.periods_saved} per.)"
            )
        else:
            self.var_kpi_savings.set("Sin abonos extra")

        # Insertar filas de amortización
        for idx, row in enumerate(schedule.rows):
            if row.extra_principal > 0:
                tag = "extra"
            elif row.period <= s.grace_periods:
                tag = "grace"
            else:
                tag = "even" if idx % 2 == 0 else "odd"

            self.tree.insert(
                "",
                tk.END,
                values=(
                    row.period,
                    f"${row.initial_balance:,.2f}",
                    f"${row.total_principal:,.2f}",
                    f"${row.interest:,.2f}",
                    f"${row.total_payment:,.2f}",
                    f"${row.ending_balance:,.2f}",
                    row.note,
                ),
                tags=(tag,),
            )

        # Fila final de totales generales
        detail_parts = [f"{s.actual_periods} periodos"]
        if s.total_extra_principal > 0:
            detail_parts.append(f"Extras: ${s.total_extra_principal:,.2f}")
        if s.total_interest_capitalized > 0:
            detail_parts.append(f"Int. capitalizado: ${s.total_interest_capitalized:,.2f}")

        self.tree.insert(
            "",
            tk.END,
            values=(
                "TOTALES",
                "—",
                f"${s.total_principal:,.2f}",
                f"${s.total_interest:,.2f}",
                f"${s.total_payment:,.2f}",
                f"${s.final_balance:,.2f}",
                " | ".join(detail_parts),
            ),
            tags=("total",),
        )

    def _export_csv(self) -> None:
        if self._last_schedule is None or not self._last_schedule.rows:
            messagebox.showinfo(
                "Exportar CSV",
                "Primero genere una tabla de amortización para poder exportarla.",
            )
            return

        path = filedialog.asksaveasfilename(
            title="Guardar tabla de amortización como CSV",
            defaultextension=".csv",
            filetypes=[("Archivo CSV", "*.csv"), ("Todos los archivos", "*.*")],
            initialfile="tabla_amortizacion.csv",
        )
        if not path:
            return

        try:
            with open(path, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "Periodo",
                        "Saldo Inicial",
                        "Abono a Capital (incl. extra)",
                        "Abono Ordinario",
                        "Abono Extra",
                        "Interés",
                        "Cuota Total",
                        "Saldo Final",
                        "Tipo / Detalle",
                    ]
                )
                for r in self._last_schedule.rows:
                    writer.writerow(
                        [
                            r.period,
                            f"{r.initial_balance:.2f}",
                            f"{r.total_principal:.2f}",
                            f"{r.regular_principal:.2f}",
                            f"{r.extra_principal:.2f}",
                            f"{r.interest:.2f}",
                            f"{r.total_payment:.2f}",
                            f"{r.ending_balance:.2f}",
                            r.note,
                        ]
                    )
                s = self._last_schedule.summary
                writer.writerow(
                    [
                        "TOTALES",
                        "",
                        f"{s.total_principal:.2f}",
                        f"{s.total_regular_principal:.2f}",
                        f"{s.total_extra_principal:.2f}",
                        f"{s.total_interest:.2f}",
                        f"{s.total_payment:.2f}",
                        f"{s.final_balance:.2f}",
                        f"Plazo efectivo: {s.actual_periods} periodos",
                    ]
                )
            self._set_status(f"Tabla exportada correctamente a: {path}", level="ok")
        except OSError as err:
            self._set_status(f"No se pudo guardar el archivo CSV: {err}", level="error")
            messagebox.showerror("Error al exportar CSV", str(err))

    def _reset_all(self) -> None:
        self._reset_rate_fields()
        self.var_principal.set("")
        self.var_term_value.set("")
        self.var_term_unit.set("Periodos")
        self.var_term_preview.set("= —")
        self.var_use_converted.set(True)
        self.var_amort_rate_pct.set("")
        self.var_amort_periodicity.set("Mensual")
        self.var_grace_type.set(GRACE_NONE)
        self.var_grace_periods.set("0")

        self.var_extra_mode.set(EXTRA_SINGLE)
        self.var_extra_start.set("")
        self.var_extra_freq.set("1")
        self.var_extra_end.set("")
        self.var_extra_amount.set("")
        self.var_extra_effect.set(EFFECT_REDUCE_TERM)
        self._clear_extra_payments()

        for item in self.tree.get_children():
            self.tree.delete(item)
        self._last_schedule = None

        self.var_kpi_principal.set("$0.00")
        self.var_kpi_periods.set("0")
        self.var_kpi_rate.set("0.0000%")
        self.var_kpi_total_cap.set("$0.00")
        self.var_kpi_total_int.set("$0.00")
        self.var_kpi_total_pay.set("$0.00")
        self.var_kpi_savings.set("—")

        self._toggle_amort_rate_mode()
        self._toggle_grace_fields()
        self._toggle_extra_mode_fields()
        self._set_status("Todos los campos y la tabla han sido reiniciados.", level="info")


def run_app() -> None:
    """Inicia el bucle principal de la interfaz gráfica."""
    app = FinancialCalculatorApp()
    app.mainloop()
