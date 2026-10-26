import csv
import re
from datetime import timedelta
from io import BytesIO, StringIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

HEADERS = [
    "UUID",
    "Fecha efectiva",
    "Tipo",
    "Estado",
    "Cuenta",
    "Destino",
    "Área",
    "Categoría",
    "Subcategoría",
    "Importe",
    "Moneda",
    "Método de pago",
    "Descripción",
    "Referencia",
    "Registrado por (UUID)",
    "Registrado por (nombre)",
]


def detail_row(item, zone):
    return [
        str(item.pk),
        item.occurred_at.astimezone(zone).isoformat(),
        item.kind,
        item.status,
        item.account.name,
        item.destination_account.name if item.destination_account else "",
        item.area.name if item.area else "",
        item.category.name if item.category else "",
        item.subcategory.name if item.subcategory else "",
        format(item.amount, ".2f"),
        item.currency,
        item.payment_method,
        item.description,
        item.reference,
        str(item.owner_id),
        item.owner.get_full_name() or "Integrante",
    ]


def safe_text(value):
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value))
    # Guard leading whitespace/control characters as well as formula markers.
    return (
        "'" + text
        if text.lstrip().startswith(("=", "+", "-", "@"))
        or text.startswith(("\t", "\r", "\n"))
        else text
    )


def export_csv(rows, data):
    buffer = StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(HEADERS)
    zone = ZoneInfo(data["timezone"])
    for item in rows:
        writer.writerow([safe_text(value) for value in detail_row(item, zone)])
    return buffer.getvalue().encode("utf-8-sig")


def period_label(data):
    from datetime import datetime

    end = datetime.fromisoformat(data["end_exclusive"]).date() - timedelta(
        days=1
    )
    return f'{data["start"][:10]} a {end} | {data["timezone"]} | PEN'


def export_xlsx(rows, data):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    workbook.remove(workbook.active)
    zone = ZoneInfo(data["timezone"])
    summary_rows = [
        ["Ingresos vigentes", data["income"]],
        ["Gastos vigentes", data["expense"]],
        ["Flujo neto", data["net_flow"]],
        ["Movimientos del detalle", str(len(rows))],
        ["Generado (UTC)", data["generated_at"]],
        ["Regla", data["note"]],
    ]
    summary_rows += [
        [f"Filtro: {key}", value] for key, value in data["filters"].items()
    ]
    specs = [
        ("Resumen financiero", ["Indicador", "Valor"], summary_rows, {2}),
        (
            "Movimientos",
            HEADERS,
            [detail_row(item, zone) for item in rows],
            {10},
        ),
        (
            "Gastos por área",
            ["Área", "Importe"],
            [[p["name"], p["amount"]] for p in data["areas"]],
            {2},
        ),
        (
            "Gastos por categoría",
            ["Categoría", "Importe"],
            [[p["name"], p["amount"]] for p in data["categories"]],
            {2},
        ),
        (
            "Evolución temporal",
            [
                "Inicio del grupo",
                "Ingresos",
                "Gastos",
                "Flujo neto",
                "Gastos acumulados",
            ],
            [
                [
                    p["date"],
                    p["income"],
                    p["expense"],
                    p["net_flow"],
                    p["accumulated"],
                ]
                for p in data["evolution"]["points"]
            ],
            {2, 3, 4, 5},
        ),
    ]
    for title, headers, values, money_columns in specs:
        sheet = workbook.create_sheet(title)
        sheet.append(["ControlGastos | " + title])
        sheet.append([period_label(data)])
        sheet.append(
            [
                "Importes como texto decimal exacto; formato PEN. No contiene fórmulas."
            ]
        )
        sheet.append(headers)
        for row in values:
            sheet.append([str(value) for value in row])
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.value = re.sub(
                        r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cell.value
                    )
                    cell.data_type = (
                        "s"  # Even '=...' is a literal shared/inline string.
                    )
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                if (
                    cell.row > 4
                    and cell.column in money_columns
                    and re.fullmatch(r"-?\d+\.\d{2}", str(cell.value))
                ):
                    cell.number_format = '"S/ "@'
                    cell.alignment = Alignment(
                        horizontal="right", vertical="top"
                    )
        for cell in sheet[4]:
            cell.fill = PatternFill("solid", fgColor="047857")
            cell.font = Font(color="FFFFFF", bold=True)
        sheet["A1"].font = Font(size=17, bold=True, color="064E3B")
        sheet.freeze_panes = "A5"
        sheet.auto_filter.ref = (
            f"A4:{get_column_letter(len(headers))}{max(4, sheet.max_row)}"
        )
        for index, header in enumerate(headers, start=1):
            sheet.column_dimensions[get_column_letter(index)].width = (
                48
                if header in ("Descripción", "Regla", "Valor")
                else 38 if header in ("UUID", "Fecha efectiva") else 24
            )
        sheet.print_title_rows = "1:4"
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def export_pdf(rows, data):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        LongTable,
        TableStyle,
        PageBreak,
    )

    output = BytesIO()
    width, height = landscape(A4)
    document = SimpleDocTemplate(
        output,
        pagesize=(width, height),
        rightMargin=32,
        leftMargin=32,
        topMargin=45,
        bottomMargin=38,
        title="ControlGastos - Reporte financiero",
        author="ControlGastos",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Cell",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            splitLongWords=True,
        )
    )
    story = []

    def paragraph(value, style="Cell"):
        return Paragraph(
            escape(str(value)).replace("\n", "<br/>"), styles[style]
        )

    def table(title, headers, values, widths):
        story.append(paragraph(title, "Heading2"))
        if not values:
            story.append(
                paragraph("Sin resultados para los filtros seleccionados.")
            )
            story.append(Spacer(1, 12))
            return
        table_rows = [[paragraph(value) for value in headers]] + [
            [paragraph(value) for value in row] for row in values
        ]
        grid = LongTable(
            table_rows,
            colWidths=widths,
            repeatRows=1,
            hAlign="LEFT",
            splitByRow=1,
        )
        grid.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#d1fae5"),
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f1f5f9")],
                    ),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    (
                        "LINEBELOW",
                        (0, 0),
                        (-1, 0),
                        1,
                        colors.HexColor("#047857"),
                    ),
                ]
            )
        )
        if title == "Detalle de movimientos":
            grid.setStyle(
                TableStyle(
                    [
                        ("NOSPLIT", (0, index), (-1, index + 1))
                        for index in range(1, len(table_rows), 2)
                    ]
                )
            )
        story.append(grid)
        story.append(Spacer(1, 16))

    story.append(paragraph("ControlGastos", "Title"))
    story.append(paragraph("Reporte financiero personalizado", "Heading1"))
    story.append(paragraph(period_label(data)))
    story.append(paragraph(f'Generado (UTC): {data["generated_at"]}'))
    story.append(
        paragraph(
            "Filtros: "
            + (
                ", ".join(f"{k}={v}" for k, v in data["filters"].items())
                or "Mes actual, movimientos vigentes"
            )
        )
    )
    story.append(Spacer(1, 15))
    table(
        "Indicadores",
        ["Ingresos", "Gastos", "Flujo neto"],
        [["S/ " + data[k] for k in ("income", "expense", "net_flow")]],
        [250, 250, 277],
    )
    story.append(paragraph(data["note"]))
    table(
        "Gastos por área",
        ["Área", "Importe PEN"],
        [[p["name"], "S/ " + p["amount"]] for p in data["areas"]],
        [530, 247],
    )
    table(
        "Gastos por categoría",
        ["Categoría", "Importe PEN"],
        [[p["name"], "S/ " + p["amount"]] for p in data["categories"]],
        [530, 247],
    )
    story.append(PageBreak())
    table(
        "Evolución temporal",
        ["Inicio", "Ingresos PEN", "Gastos PEN", "Flujo PEN", "Acumulado PEN"],
        [
            [
                p["date"],
                p["income"],
                p["expense"],
                p["net_flow"],
                p["accumulated"],
            ]
            for p in data["evolution"]["points"]
        ],
        [130, 160, 160, 160, 167],
    )
    story.append(PageBreak())
    zone = ZoneInfo(data["timezone"])
    details = []
    for item in rows:
        # Two rows per movement: all fields are preserved without a tiny 14-column table.
        main = [
            item.occurred_at.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S %z"),
            item.kind + " / " + item.status,
            item.account.name
            + (
                " -> " + item.destination_account.name
                if item.destination_account
                else ""
            ),
            "S/ " + format(item.amount, ".2f"),
        ]
        extra = [
            "UUID: " + str(item.pk),
            " / ".join(
                filter(
                    None,
                    [
                        item.area.name if item.area else "",
                        item.category.name if item.category else "",
                        item.subcategory.name if item.subcategory else "",
                    ],
                )
            ),
            ("Registrado por: " + (item.owner.get_full_name() or "Integrante") + " | " if item.family_id else "") + item.description
            + (" | Ref: " + item.reference if item.reference else "")
            + (
                " | Método: " + item.payment_method
                if item.payment_method
                else ""
            ),
            item.currency,
        ]
        details.extend([main, extra])
    table(
        "Detalle de movimientos",
        [
            "Fecha / Identificador",
            "Tipo / Clasificación",
            "Cuenta / Descripción",
            "Importe",
        ],
        details,
        [200, 170, 260, 147],
    )

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(
            32, 22, "ControlGastos | Informe privado | " + data["timezone"]
        )
        canvas.drawRightString(width - 32, 22, f"Página {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
