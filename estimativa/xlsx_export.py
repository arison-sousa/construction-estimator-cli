from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import math

import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell

from .models import ZERO, Quote


BLACK = "#111111"
HEADER = "#C9C9C9"
LIGHT = "#EEEEEE"
TOTAL = "#D9D9D9"
WHITE = "#FFFFFF"
CURRENCY_FORMAT = '"R$" #,##0.00'
QUANTITY_FORMAT = "#,##0.00"


def _number(value: Decimal) -> float:
    return float(value)


def _description_height(text: str, characters_per_line: int = 72) -> float:
    lines = 0
    for paragraph in (text or "").splitlines() or [""]:
        lines += max(1, math.ceil(len(paragraph) / characters_per_line))
    return max(22, 13 * lines + 6)


def _compact_height(text: str, characters_per_line: int = 90) -> float:
    lines = max(1, math.ceil(len(text or "") / characters_per_line))
    return max(16, 11 * lines + 5)


def export_xlsx(quote: Quote, path: str | Path, logo_path: str | Path | None = None) -> Path:
    """Export a quote to an editable, print-ready Excel workbook."""
    quote.normalize_sections()
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)

    workbook = xlsxwriter.Workbook(target)
    workbook.set_properties({
        "title": f"Proposta {quote.info.proposal} - {quote.info.project}",
        "subject": "Proposta comercial",
        "author": quote.company.name,
        "company": quote.company.name,
        "comments": "Gerado pelo Estimativa CLI a partir do arquivo JSON da proposta.",
    })
    workbook.set_calc_mode("auto")
    sheet = workbook.add_worksheet("Proposta")
    sheet.hide_gridlines(2)
    sheet.set_landscape()
    sheet.set_paper(9)  # A4
    sheet.fit_to_pages(1, 0)
    sheet.center_horizontally()
    sheet.set_margins(left=0.25, right=0.25, top=0.3, bottom=0.3)
    sheet.set_header("", {"margin": 0.1})
    sheet.set_footer("&R&P", {"margin": 0.15})
    sheet.set_column("A:A", 7)
    sheet.set_column("B:B", 66)
    sheet.set_column("C:C", 8)
    sheet.set_column("D:D", 10)
    sheet.set_column("E:H", 15)
    sheet.set_column("I:I", 17)

    thin = {"border": 1, "border_color": BLACK}
    formats = {
        "company": workbook.add_format({**thin, "font_name": "Arial", "font_size": 9, "valign": "vcenter", "text_wrap": True}),
        "info_label": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "bold": True, "valign": "vcenter"}),
        "info_value": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "valign": "vcenter"}),
        "header": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "align": "center", "valign": "vcenter", "bg_color": HEADER, "text_wrap": True}),
        "section_no": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "bold": True, "align": "center", "valign": "vcenter", "bg_color": LIGHT}),
        "section": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "bold": True, "valign": "vcenter", "bg_color": LIGHT}),
        "item_no": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "align": "center", "valign": "vcenter"}),
        "description": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "valign": "vcenter", "text_wrap": True}),
        "input_text": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "align": "center", "valign": "vcenter"}),
        "quantity": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "align": "center", "valign": "vcenter", "num_format": QUANTITY_FORMAT}),
        "currency": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "align": "right", "valign": "vcenter", "num_format": CURRENCY_FORMAT}),
        "derived": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "align": "right", "valign": "vcenter", "num_format": CURRENCY_FORMAT, "bg_color": LIGHT}),
        "derived_total": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "bold": True, "align": "right", "valign": "vcenter", "num_format": CURRENCY_FORMAT, "bg_color": TOTAL}),
        "subtotal_label": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "bold": True, "valign": "vcenter"}),
        "total_label": workbook.add_format({**thin, "font_name": "Arial", "font_size": 9, "bold": True, "valign": "vcenter"}),
        "box_title": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "bold": True, "align": "center", "valign": "vcenter", "bg_color": HEADER}),
        "box_text": workbook.add_format({**thin, "font_name": "Arial", "font_size": 7, "valign": "vcenter", "text_wrap": True}),
        "term_label": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "bold": True, "valign": "vcenter", "bg_color": LIGHT}),
        "term_value": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "align": "center", "valign": "vcenter", "bg_color": LIGHT, "text_wrap": True}),
        "tax_label": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "bold": True, "align": "center", "valign": "vcenter", "bg_color": LIGHT, "text_wrap": True}),
        "tax_text": workbook.add_format({**thin, "font_name": "Arial", "font_size": 7, "align": "center", "valign": "vcenter", "bg_color": LIGHT, "text_wrap": True}),
        "notes": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "valign": "top", "text_wrap": True}),
        "signature": workbook.add_format({**thin, "font_name": "Arial", "font_size": 8, "align": "center", "valign": "vcenter", "text_wrap": True}),
    }

    # Company and proposal header.
    sheet.set_row(0, 18)
    for row in range(1, 5):
        sheet.set_row(row, 17)
    sheet.merge_range("A1:A5", "", formats["company"])
    logo = Path(logo_path).expanduser() if logo_path else None
    if logo and logo.exists():
        sheet.insert_image("A1", str(logo), {"x_scale": 0.07, "y_scale": 0.07, "x_offset": 5, "y_offset": 5, "object_position": 1})
    company = quote.company
    company_text = (
        f"{company.name}\nCNPJ {company.tax_id}    INS ESTADUAL {company.state_registration}\n"
        f"{company.address}\n{company.city}\nCEP {company.postal_code}"
    )
    sheet.merge_range("B1:E5", company_text, formats["company"])
    details = [
        ("CLIENTE:", quote.info.client),
        ("OBRA:", quote.info.project),
        ("CONTATO:", quote.info.contact),
        ("LOCAL:", quote.info.location or quote.info.city),
    ]
    for row, (label, value) in enumerate(details):
        sheet.write(row, 5, label, formats["info_label"])
        sheet.merge_range(row, 6, row, 8, value, formats["info_value"])
    sheet.write(4, 5, "PROPOSTA:", formats["info_label"])
    sheet.write(4, 6, quote.info.proposal, formats["info_value"])
    sheet.write(4, 7, "DATA:", formats["info_label"])
    sheet.write(4, 8, quote.info.issue_date, formats["info_value"])

    # Items table header.
    header_top = 5
    header_bottom = 6
    sheet.set_row(header_top, 19)
    sheet.set_row(header_bottom, 18)
    for column, label in ((0, "ITEM"), (1, "SERVIÇOS"), (2, "UND"), (3, "QUANT"), (8, "PREÇO\nTOTAL")):
        sheet.merge_range(header_top, column, header_bottom, column, label, formats["header"])
    sheet.merge_range(header_top, 4, header_top, 5, "PREÇO UNITÁRIO", formats["header"])
    sheet.merge_range(header_top, 6, header_top, 7, "PREÇO TOTAL", formats["header"])
    for column, label in ((4, "MATERIAL"), (5, "MÃO DE OBRA"), (6, "MATERIAL"), (7, "MÃO DE OBRA")):
        sheet.write(header_bottom, column, label, formats["header"])

    row = 7
    all_item_rows: list[int] = []
    subtotal_rows: list[int] = []
    section_item_rows: list[int] = []
    section_material = ZERO
    section_labor = ZERO

    def write_subtotal() -> None:
        nonlocal row, section_item_rows, section_material, section_labor
        if not section_item_rows:
            return
        first = section_item_rows[0] + 1
        last = section_item_rows[-1] + 1
        sheet.merge_range(row, 0, row, 5, "Subtotal", formats["subtotal_label"])
        sheet.write_formula(row, 6, f"=SUM(G{first}:G{last})", formats["derived"], _number(section_material))
        sheet.write_formula(row, 7, f"=SUM(H{first}:H{last})", formats["derived"], _number(section_labor))
        sheet.write_formula(row, 8, f"=SUM(I{first}:I{last})", formats["derived_total"], _number(section_material + section_labor))
        sheet.set_row(row, 18)
        subtotal_rows.append(row)
        row += 1
        section_item_rows = []
        section_material = ZERO
        section_labor = ZERO

    for item in quote.items:
        if item.is_section:
            if section_item_rows:
                write_subtotal()
                sheet.set_row(row, 6)
                row += 1
            sheet.write(row, 0, item.section_number, formats["section_no"])
            sheet.merge_range(row, 1, row, 8, item.section, formats["section"])
            sheet.set_row(row, 18)
            row += 1
            continue

        description = "\n".join(part for part in (item.title, item.description) if part)
        excel_row = row + 1
        sheet.write(row, 0, item.number, formats["item_no"])
        sheet.write(row, 1, description, formats["description"])
        sheet.write(row, 2, item.unit, formats["input_text"])
        sheet.write_number(row, 3, _number(item.quantity), formats["quantity"])
        sheet.write_number(row, 4, _number(item.material_unit), formats["currency"])
        sheet.write_number(row, 5, _number(item.labor_unit), formats["currency"])
        sheet.write_formula(row, 6, f"=D{excel_row}*E{excel_row}", formats["derived"], _number(item.material_total))
        sheet.write_formula(row, 7, f"=D{excel_row}*F{excel_row}", formats["derived"], _number(item.labor_total))
        sheet.write_formula(row, 8, f"=G{excel_row}+H{excel_row}", formats["derived_total"], _number(item.total))
        sheet.set_row(row, _description_height(description))
        all_item_rows.append(row)
        section_item_rows.append(row)
        section_material += item.material_total
        section_labor += item.labor_total
        row += 1
    write_subtotal()

    # Accumulated total.
    row += 1
    sheet.merge_range(row, 0, row, 5, "TOTAL ACUMULADO", formats["total_label"])
    subtotal_cells_g = ",".join(xl_rowcol_to_cell(index, 6) for index in subtotal_rows)
    subtotal_cells_h = ",".join(xl_rowcol_to_cell(index, 7) for index in subtotal_rows)
    subtotal_cells_i = ",".join(xl_rowcol_to_cell(index, 8) for index in subtotal_rows)
    material_formula = f"=SUM({subtotal_cells_g})" if subtotal_cells_g else "=0"
    labor_formula = f"=SUM({subtotal_cells_h})" if subtotal_cells_h else "=0"
    total_formula = f"=SUM({subtotal_cells_i})" if subtotal_cells_i else "=0"
    sheet.write_formula(row, 6, material_formula, formats["derived"], _number(quote.material_total))
    sheet.write_formula(row, 7, labor_formula, formats["derived"], _number(quote.labor_total))
    sheet.write_formula(row, 8, total_formula, formats["derived_total"], _number(quote.total))
    sheet.set_row(row, 22)
    row += 2

    # Responsibilities.
    sheet.merge_range(row, 0, row, 3, "Responsabilidades da CONTRATANTE:", formats["box_title"])
    sheet.merge_range(row, 5, row, 8, f"Responsabilidades da {quote.company.name}:", formats["box_title"])
    sheet.set_row(row, 18)
    row += 1
    responsibility_count = max(len(quote.client_responsibilities), len(quote.contractor_responsibilities))
    for index in range(responsibility_count):
        client_text = f"{index + 1}. {quote.client_responsibilities[index]}" if index < len(quote.client_responsibilities) else ""
        contractor_text = f"{index + 1}. {quote.contractor_responsibilities[index]}" if index < len(quote.contractor_responsibilities) else ""
        sheet.merge_range(row, 0, row, 3, client_text, formats["box_text"])
        sheet.merge_range(row, 5, row, 8, contractor_text, formats["box_text"])
        sheet.set_row(row, max(_compact_height(client_text), _compact_height(contractor_text)))
        row += 1
    row += 1

    # Commercial terms and taxes.
    commercial_start = row
    terms = [
        ("VALIDADE DA PROPOSTA:", quote.validity),
        ("CONDIÇÃO DE PAGAMENTO:", quote.payment_terms),
        ("FRETE:", quote.freight),
        ("PRAZO DE INÍCIO APÓS FECHAMENTO:", quote.start_deadline),
        ("PRAZO DE EXECUÇÃO:", quote.execution_deadline),
        ("GARANTIA:", quote.warranty),
    ]
    visible_terms = [(label, value) for label, value in terms if str(value).strip()]
    tax_height = 11 * max(1, len(quote.taxes.splitlines())) + 5
    term_row_height = max(16, tax_height / max(1, len(visible_terms)))
    for label, value in visible_terms:
        sheet.merge_range(row, 0, row, 3, label, formats["term_label"])
        sheet.write(row, 4, value, formats["term_value"])
        sheet.set_row(row, term_row_height)
        row += 1
    sheet.merge_range(commercial_start, 5, row - 1, 5, "IMPOSTOS\nRECOLHIDOS:", formats["tax_label"])
    sheet.merge_range(commercial_start, 6, row - 1, 8, quote.taxes, formats["tax_text"])
    row += 1

    # Notes and signature.
    signature_start = row
    signature_end = row + 4
    sheet.merge_range(signature_start, 0, signature_end, 5, quote.notes, formats["notes"])
    signature_text = (
        "____________________________\n"
        f"{quote.company.signer_name}\n{quote.company.signer_email}\n"
        f"{quote.company.signer_title}\n{quote.company.signer_phone}"
    )
    sheet.merge_range(signature_start, 6, signature_end, 8, signature_text, formats["signature"])
    for signature_row in range(signature_start, signature_end + 1):
        sheet.set_row(signature_row, 14)

    last_row = signature_end
    sheet.print_area(0, 0, last_row, 8)
    sheet.repeat_rows(0, header_bottom)
    sheet.freeze_panes(header_bottom + 1, 0)
    sheet.set_selection(0, 0, 0, 0)

    workbook.close()
    return target
