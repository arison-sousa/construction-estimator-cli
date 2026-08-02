from __future__ import annotations

from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import ZERO, Quote, brl, decimal_text


BLACK = colors.HexColor("#111111")
HEADER = colors.HexColor("#c9c9c9")
LIGHT = colors.HexColor("#eeeeee")
TOTAL = colors.HexColor("#d9d9d9")
BLUE = colors.HexColor("#29465b")
ITEM_TABLE_WIDTHS = [12 * mm, 108 * mm, 14 * mm, 15 * mm, 25 * mm, 25 * mm, 25 * mm, 25 * mm, 28 * mm]
ACCUMULATED_TOTAL_WIDTHS = [
    ITEM_TABLE_WIDTHS[0],
    sum(ITEM_TABLE_WIDTHS[1:6]),
    ITEM_TABLE_WIDTHS[6],
    ITEM_TABLE_WIDTHS[7],
    ITEM_TABLE_WIDTHS[8],
]
CONTENT_WIDTH = sum(ITEM_TABLE_WIDTHS)
RESPONSIBILITY_GAP = 5 * mm
RESPONSIBILITY_WIDTH = (CONTENT_WIDTH - RESPONSIBILITY_GAP) / 2
ITEM_ROW_LEADING = 9.8
ITEM_ROW_VERTICAL_PADDING = 2
ITEM_ROW_HEIGHT = ITEM_ROW_LEADING + 2 * ITEM_ROW_VERTICAL_PADDING
SECTION_GAP_HEIGHT = ITEM_ROW_HEIGHT
ACCUMULATED_TOTAL_STYLE = [
    ("BOX", (0, 0), (-1, -1), 1.0, BLACK),
    ("GRID", (2, 0), (-1, 0), 0.45, BLACK),
    ("BACKGROUND", (2, 0), (3, 0), LIGHT),
    ("BACKGROUND", (4, 0), (4, 0), TOTAL),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
]
SIGNATURE_ROW_HEIGHTS = [12 * mm, 4 * mm, 15 * mm]
SIGNATURE_STYLE = [
    ("BOX", (0, 0), (-1, -1), 0.8, BLACK),
    ("SPAN", (0, 0), (0, 2)),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ("TOPPADDING", (1, 1), (1, 1), 0),
    ("BOTTOMPADDING", (1, 1), (1, 1), 0),
    ("TOPPADDING", (1, 2), (1, 2), 0),
]


def _styles():
    styles = getSampleStyleSheet()
    return {
        "body": ParagraphStyle("body", parent=styles["Normal"], fontName="Helvetica", fontSize=7.2, leading=9.0, textColor=BLACK),
        "small": ParagraphStyle("small", parent=styles["Normal"], fontName="Helvetica", fontSize=6.2, leading=7.4, textColor=BLACK),
        "bold": ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.2, leading=9.0, textColor=BLACK),
        "center": ParagraphStyle("center", parent=styles["Normal"], fontName="Helvetica", fontSize=7.1, leading=8.4, alignment=TA_CENTER),
        "center_bold": ParagraphStyle("center_bold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.1, leading=8.4, alignment=TA_CENTER),
        "right_bold": ParagraphStyle("right_bold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.1, leading=8.4, alignment=TA_RIGHT),
        "company": ParagraphStyle("company", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=10),
        "company_details": ParagraphStyle("company_details", parent=styles["Normal"], fontName="Helvetica", fontSize=7.2, leading=10.5, textColor=BLACK),
        "section": ParagraphStyle("section", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9),
        "item_body": ParagraphStyle("item_body", parent=styles["Normal"], fontName="Helvetica", fontSize=8.0, leading=ITEM_ROW_LEADING, textColor=BLACK),
        "item_center": ParagraphStyle("item_center", parent=styles["Normal"], fontName="Helvetica", fontSize=8.0, leading=ITEM_ROW_LEADING, alignment=TA_CENTER),
        "item_center_bold": ParagraphStyle("item_center_bold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.0, leading=ITEM_ROW_LEADING, alignment=TA_CENTER),
        "item_bold": ParagraphStyle("item_bold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.0, leading=ITEM_ROW_LEADING, textColor=BLACK),
        "item_right_bold": ParagraphStyle("item_right_bold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.0, leading=ITEM_ROW_LEADING, alignment=TA_RIGHT),
        "item_section": ParagraphStyle("item_section", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.0, leading=ITEM_ROW_LEADING),
    }


def _p(text: object, style, bold_first: bool = False, markup: bool = False) -> Paragraph:
    value = str(text or "")
    if not markup:
        value = escape(value)
    value = value.replace("\n", "<br/>")
    if bold_first and "<br/>" in value:
        first, rest = value.split("<br/>", 1)
        value = f"<b>{first}</b><br/>{rest}"
    return Paragraph(value, style)


def _header(quote: Quote, styles, logo_path: Path | None):
    company = quote.company
    logo = _p("<b>DEBASE</b><br/>CONSTRUTORA", styles["center_bold"], markup=True)
    if logo_path and logo_path.exists():
        logo = Image(str(logo_path), width=19 * mm, height=21 * mm)
    company_text = _p(
        f"<b>{escape(company.name)}</b><br/>CNPJ {escape(company.tax_id)} &nbsp; INS ESTADUAL {escape(company.state_registration)}"
        f"<br/>{escape(company.address)}<br/>{escape(company.city)}<br/>CEP {escape(company.postal_code)}",
        styles["company_details"], markup=True,
    )
    info = quote.info
    details = Table(
        [
            [_p("<b>CLIENTE:</b>", styles["body"], markup=True), _p(info.client, styles["bold"])],
            [_p("<b>OBRA:</b>", styles["body"], markup=True), _p(info.project, styles["bold"])],
            [_p("<b>CONTATO:</b>", styles["body"], markup=True), _p(info.contact, styles["bold"])],
            [_p("<b>LOCAL:</b>", styles["body"], markup=True), _p(info.location or info.city, styles["bold"])],
            [_p("<b>PROPOSTA:</b>", styles["body"], markup=True), _p(info.proposal, styles["center"]), _p("<b>DATA:</b>", styles["body"], markup=True), _p(info.issue_date, styles["center"])],
        ],
        colWidths=[24 * mm, 58 * mm, 18 * mm, 28 * mm],
    )
    details.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("SPAN", (1, 0), (3, 0)), ("SPAN", (1, 1), (3, 1)), ("SPAN", (1, 2), (3, 2)), ("SPAN", (1, 3), (3, 3))]))
    table = Table([[logo, company_text, details]], colWidths=[22 * mm, 127 * mm, 128 * mm], rowHeights=[24 * mm])
    table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.1, BLACK), ("LINEBEFORE", (2, 0), (2, 0), 1.1, BLACK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return table


def _items_table(quote: Quote, styles):
    rows = [
        [_p("ITEM", styles["center"]), _p("SERVIÇOS", styles["center"]), _p("UND", styles["center"]), _p("QUANT", styles["center"]), _p("PREÇO UNITÁRIO", styles["center"]), "", _p("PREÇO TOTAL", styles["center"]), "", _p("PREÇO<br/>TOTAL", styles["center"], markup=True)],
        ["", "", "", "", _p("MATERIAL", styles["center"]), _p("MÃO DE OBRA", styles["center"]), _p("MATERIAL", styles["center"]), _p("MÃO DE OBRA", styles["center"]), ""],
    ]
    commands = [
        ("BACKGROUND", (0, 0), (-1, 1), HEADER), ("BOX", (0, 0), (-1, -1), 1.0, BLACK),
        ("GRID", (0, 2), (-1, -1), 0.45, BLACK), ("LINEBELOW", (0, 1), (-1, 1), 0.45, BLACK),
        ("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (1, 1)),
        ("SPAN", (2, 0), (2, 1)), ("SPAN", (3, 0), (3, 1)), ("SPAN", (4, 0), (5, 0)),
        ("SPAN", (6, 0), (7, 0)), ("SPAN", (8, 0), (8, 1)), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBEFORE", (1, 0), (1, 1), 0.45, BLACK), ("LINEBEFORE", (2, 0), (2, 1), 0.45, BLACK),
        ("LINEBEFORE", (3, 0), (3, 1), 0.45, BLACK), ("LINEBEFORE", (4, 0), (4, 1), 0.45, BLACK),
        ("LINEBEFORE", (6, 0), (6, 1), 0.45, BLACK), ("LINEBEFORE", (8, 0), (8, 1), 0.45, BLACK),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    last_section = None
    section_started = False
    section_material = ZERO
    section_labor = ZERO

    def append_section_subtotal(add_separator: bool) -> None:
        section_total = section_material + section_labor
        rows.append(["", _p("Subtotal", styles["item_bold"]), "", "", "", "", _p(brl(section_material), styles["item_center_bold"]), _p(brl(section_labor), styles["item_center_bold"]), _p(brl(section_total), styles["item_right_bold"])])
        subtotal_row = len(rows) - 1
        commands.extend([
            ("SPAN", (1, subtotal_row), (5, subtotal_row)),
            ("BACKGROUND", (6, subtotal_row), (7, subtotal_row), LIGHT),
            ("BACKGROUND", (8, subtotal_row), (8, subtotal_row), TOTAL),
            ("LINEABOVE", (0, subtotal_row), (-1, subtotal_row), 1.0, BLACK),
            ("FONTSIZE", (0, subtotal_row), (5, subtotal_row), 8.0), ("LEADING", (0, subtotal_row), (5, subtotal_row), ITEM_ROW_LEADING),
        ])
        if add_separator:
            rows.append([Spacer(1, SECTION_GAP_HEIGHT), "", "", "", "", "", "", "", ""])
            separator_row = len(rows) - 1
            commands.extend([
                ("SPAN", (0, separator_row), (-1, separator_row)),
                ("TOPPADDING", (0, separator_row), (-1, separator_row), 0), ("BOTTOMPADDING", (0, separator_row), (-1, separator_row), 0),
                ("FONTSIZE", (0, separator_row), (-1, separator_row), 1.0), ("LEADING", (0, separator_row), (-1, separator_row), SECTION_GAP_HEIGHT),
            ])

    for item in quote.items:
        if item.is_section:
            if section_started:
                append_section_subtotal(add_separator=True)
            rows.append([_p(item.section_number, styles["item_center_bold"]), _p(item.section, styles["item_section"]), "", "", "", "", "", "", ""])
            index = len(rows) - 1
            commands.extend([
                ("SPAN", (1, index), (-1, index)), ("BACKGROUND", (0, index), (-1, index), LIGHT),
                ("LINEABOVE", (0, index), (-1, index), 0.7, BLACK),
                ("FONTSIZE", (0, index), (-1, index), 8.0), ("LEADING", (0, index), (-1, index), ITEM_ROW_LEADING),
            ])
            last_section = (item.section_number, item.section)
            section_started = True
            section_material = ZERO
            section_labor = ZERO
            continue
        section = (item.section_number, item.section)
        if item.section and section != last_section:
            if section_started:
                append_section_subtotal(add_separator=True)
            rows.append([_p(item.section_number, styles["item_center_bold"]), _p(item.section, styles["item_section"]), "", "", "", "", "", "", ""])
            index = len(rows) - 1
            commands.extend([
                ("SPAN", (1, index), (-1, index)), ("BACKGROUND", (0, index), (-1, index), LIGHT),
                ("LINEABOVE", (0, index), (-1, index), 0.7, BLACK),
                ("FONTSIZE", (0, index), (-1, index), 8.0), ("LEADING", (0, index), (-1, index), ITEM_ROW_LEADING),
            ])
            last_section = section
            section_started = True
            section_material = ZERO
            section_labor = ZERO
        elif not section_started:
            section_started = True
        description = "\n".join(part for part in (item.title, item.description) if part)
        rows.append([
            _p(item.number, styles["item_center"]), _p(description, styles["item_body"]), _p(item.unit, styles["item_center"]),
            _p(decimal_text(item.quantity), styles["item_center"]), _p(brl(item.material_unit), styles["item_center"]),
            _p(brl(item.labor_unit), styles["item_center"]), _p(brl(item.material_total), styles["item_center"]),
            _p(brl(item.labor_total), styles["item_center"]), _p(brl(item.total), styles["item_right_bold"]),
        ])
        section_material += item.material_total
        section_labor += item.labor_total
        item_row = len(rows) - 1
        commands.extend([
            ("BACKGROUND", (6, item_row), (7, item_row), LIGHT),
            ("BACKGROUND", (8, item_row), (8, item_row), TOTAL),
        ])
    append_section_subtotal(add_separator=False)
    table = LongTable(rows, colWidths=ITEM_TABLE_WIDTHS, repeatRows=2, splitByRow=1)
    table.setStyle(TableStyle(commands))
    return table


def _accumulated_total(quote: Quote, styles):
    return Table(
        [[
            "",
            _p("TOTAL ACUMULADO", styles["item_bold"]),
            _p(brl(quote.material_total), styles["item_center_bold"]),
            _p(brl(quote.labor_total), styles["item_center_bold"]),
            _p(brl(quote.total), styles["item_right_bold"]),
        ]],
        colWidths=ACCUMULATED_TOTAL_WIDTHS,
        style=TableStyle(ACCUMULATED_TOTAL_STYLE),
    )


def _responsibilities(quote: Quote, styles):
    def box(title, values):
        rows = [[_p(title, styles["center_bold"])]] + [[_p(f"{i}. {text}", styles["small"])] for i, text in enumerate(values, 1)]
        table = Table(rows, colWidths=[RESPONSIBILITY_WIDTH])
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), HEADER), ("BOX", (0, 0), (-1, -1), 0.7, BLACK), ("GRID", (0, 0), (-1, -1), 0.35, BLACK), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        return table
    contractor_title = f"Responsabilidades da {quote.company.name}:"
    outer = Table([[box("Responsabilidades da CONTRATANTE:", quote.client_responsibilities), "", box(contractor_title, quote.contractor_responsibilities)]], colWidths=[RESPONSIBILITY_WIDTH, RESPONSIBILITY_GAP, RESPONSIBILITY_WIDTH])
    outer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return outer


def _commercial(quote: Quote, styles):
    rows = [
        [_p("<b>VALIDADE DA PROPOSTA:</b>", styles["body"], markup=True), _p(quote.validity, styles["center"]), _p("<b>IMPOSTOS<br/>RECOLHIDOS:</b>", styles["center_bold"], markup=True), _p(quote.taxes, styles["center"])],
        [_p("<b>CONDIÇÃO DE PAGAMENTO:</b>", styles["body"], markup=True), _p(quote.payment_terms, styles["center"]), "", ""],
        [_p("<b>FRETE:</b>", styles["body"], markup=True), _p(quote.freight, styles["center"]), "", ""],
        [_p("<b>PRAZO DE INÍCIO APÓS FECHAMENTO:</b>", styles["body"], markup=True), _p(quote.start_deadline, styles["center"]), "", ""],
        [_p("<b>PRAZO DE EXECUÇÃO:</b>", styles["body"], markup=True), _p(quote.execution_deadline, styles["center"]), "", ""],
        [_p("<b>GARANTIA:</b>", styles["body"], markup=True), _p(quote.warranty, styles["center"]), "", ""],
    ]
    table = Table(rows, colWidths=[123 * mm, 31 * mm, 25 * mm, 98 * mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("SPAN", (2, 0), (2, 5)), ("SPAN", (3, 0), (3, 5)), ("BOX", (0, 0), (-1, -1), 0.8, BLACK), ("GRID", (0, 0), (1, -1), 0.4, BLACK), ("LINEBEFORE", (2, 0), (2, -1), 0.8, BLACK), ("LINEBEFORE", (3, 0), (3, -1), 0.8, BLACK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return table


def export_pdf(quote: Quote, target: str | Path, logo_path: str | Path | None = None) -> Path:
    output = Path(target).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    logo = Path(logo_path) if logo_path else None
    doc = SimpleDocTemplate(str(output), pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm, topMargin=8 * mm, bottomMargin=10 * mm, title=quote.info.proposal or "Proposta comercial", author=quote.company.name)

    def page(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(landscape(A4)[0] - 10 * mm, 5 * mm, str(document.page))
        canvas.restoreState()

    story = [_header(quote, styles, logo), _items_table(quote, styles), Spacer(1, 4 * mm)]
    story.append(_accumulated_total(quote, styles))
    story.extend([Spacer(1, 5 * mm), _responsibilities(quote, styles), Spacer(1, 5 * mm), _commercial(quote, styles), Spacer(1, 3 * mm)])
    signature = Table([
        [_p(quote.notes, styles["body"]), ""],
        ["", _p("______________________________", styles["center"])],
        ["", _p(f"<b>{escape(quote.company.signer_name)}</b><br/>{escape(quote.company.signer_email)}<br/>{escape(quote.company.signer_title)}<br/>{escape(quote.company.signer_phone)}", styles["center"], markup=True)],
    ], colWidths=[190 * mm, 87 * mm], rowHeights=SIGNATURE_ROW_HEIGHTS)
    signature.setStyle(TableStyle(SIGNATURE_STYLE))
    story.append(KeepTogether(signature))
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return output
