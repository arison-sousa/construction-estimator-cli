import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from estimativa.cli import ask_item_index, open_pdf
from estimativa.models import DEFAULT_TAXES, Item, Quote, brl, money, number
from estimativa.naming import (
    ProposalIdentity,
    identity_from_info,
    next_quote_identity,
    next_revision_identity,
    parse_proposal_identity,
    quote_path,
    safe_filename_component,
    set_quote_identity,
)
from estimativa.pdf_export import (
    ACCUMULATED_TOTAL_STYLE,
    ACCUMULATED_TOTAL_WIDTHS,
    BLACK,
    CONTENT_WIDTH,
    HEADER,
    ITEM_TABLE_WIDTHS,
    RESPONSIBILITY_GAP,
    RESPONSIBILITY_WIDTH,
    SIGNATURE_ROW_HEIGHTS,
    SIGNATURE_STYLE,
    _accumulated_total,
    _items_table,
    _styles,
)


class ModelTests(unittest.TestCase):
    def test_proposal_identity_uses_fixed_width_format(self):
        self.assertEqual(ProposalIdentity(1, 2026, 0).text, "0001-26-00")
        self.assertEqual(ProposalIdentity(684, 2027, 3).text, "0684-27-03")

    def test_legacy_proposal_identity_is_supported(self):
        identity = parse_proposal_identity("0669-26-rev00")
        self.assertEqual(identity, ProposalIdentity(669, 2026, 0))

    def test_quote_filename_is_readable_and_os_safe(self):
        quote = Quote()
        quote.info.client = 'JBS: Foods | Sul'
        quote.info.location = "Ipumirim/SC"
        quote.info.project = 'Reforma * Piso? "Almoxarifado"'
        set_quote_identity(quote, ProposalIdentity(1, 2026, 0))
        path = quote_path(quote, "propostas")
        self.assertEqual(
            path.name,
            "0001-26-00 - JBS Foods Sul Ipumirim SC - Reforma Piso Almoxarifado.json",
        )
        self.assertFalse(any(character in path.name for character in '<>:"/\\|?*'))

    def test_filename_components_are_limited_and_have_no_trailing_dot_or_space(self):
        component = safe_filename_component("A" * 100 + ". ", "fallback", 20)
        self.assertEqual(component, "A" * 20)

    def test_next_quote_number_resets_each_year(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "0099-25-00 - Cliente Local - Obra.json").write_text("{}", encoding="utf-8")
            (root / "0002-26-00 - Cliente Local - Obra.pdf").touch()
            self.assertEqual(next_quote_identity(root, 2026), ProposalIdentity(3, 2026, 0))
            self.assertEqual(next_quote_identity(root, 2027), ProposalIdentity(1, 2027, 0))

    def test_next_quote_number_can_read_identity_from_json_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            quote = Quote()
            set_quote_identity(quote, ProposalIdentity(8, 2026, 0))
            quote.save(root / "nome-antigo.json")
            self.assertEqual(next_quote_identity(root, 2026), ProposalIdentity(9, 2026, 0))

    def test_next_revision_preserves_number_and_year(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "0007-26-00 - Cliente Local - Obra.json").write_text("{}", encoding="utf-8")
            (root / "0007-26-01 - Cliente Local - Obra.json").write_text("{}", encoding="utf-8")
            revised = next_revision_identity(root, ProposalIdentity(7, 2026, 0))
            self.assertEqual(revised, ProposalIdentity(7, 2026, 2))

    def test_structured_identity_survives_save_and_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "quote.json"
            quote = Quote()
            set_quote_identity(quote, ProposalIdentity(12, 2026, 4))
            quote.save(path)
            loaded = Quote.load(path)
            self.assertEqual(identity_from_info(loaded.info), ProposalIdentity(12, 2026, 4))

    def test_brazilian_money(self):
        self.assertEqual(money("20.000,50"), Decimal("20000.50"))
        self.assertEqual(brl(Decimal("20000.5")), "R$ 20.000,50")

    def test_default_taxes_have_the_required_multiline_wording(self):
        self.assertEqual(Quote().taxes, DEFAULT_TAXES)
        self.assertEqual(len(DEFAULT_TAXES.splitlines()), 8)
        self.assertIn("DEBASE CONSTRUTORA LTDA", DEFAULT_TAXES)

    def test_default_commercial_terms(self):
        quote = Quote()
        self.assertEqual(quote.validity, "15 dias")
        self.assertEqual(quote.payment_terms, "-")
        self.assertEqual(quote.freight, "CIF")
        self.assertEqual(quote.start_deadline, "-")
        self.assertEqual(quote.execution_deadline, "-")
        self.assertEqual(quote.warranty, "-")

    def test_company_details_have_relaxed_line_spacing(self):
        styles = _styles()
        self.assertGreater(styles["company_details"].leading, styles["body"].leading)
        self.assertEqual(styles["company_details"].leading, 10.5)

    def test_item_table_typography_is_larger_than_supporting_text(self):
        styles = _styles()
        self.assertGreater(styles["item_body"].fontSize, styles["body"].fontSize)
        self.assertEqual(
            {styles[name].fontSize for name in ("item_body", "item_center", "item_bold", "item_right_bold", "item_section")},
            {8.0},
        )
        self.assertEqual(
            {styles[name].leading for name in ("item_body", "item_center", "item_bold", "item_right_bold", "item_section")},
            {9.8},
        )

    def test_material_and_labor_prices_are_centered_and_final_price_is_right_aligned(self):
        quote = Quote(items=[
            Item("", "", "", section="Serviços", is_section=True),
            Item("", "", "Item", material_unit=money("80"), labor_unit=money("90")),
        ])
        quote.normalize_sections()
        table = _items_table(quote, _styles())
        item_row = table._cellvalues[3]

        self.assertTrue(all(item_row[column].style.alignment == 1 for column in range(9) if column != 1 and column != 8))
        self.assertEqual(item_row[8].style.alignment, 2)

    def test_totals_and_round_trip(self):
        quote = Quote(items=[Item("1", "Teste", "", "und", number("2"), money("10,50"), money("4"))])
        self.assertEqual(quote.material_total, Decimal("21.00"))
        self.assertEqual(quote.labor_total, Decimal("8.00"))
        self.assertEqual(quote.total, Decimal("29.00"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "quote.json"
            quote.save(path)
            loaded = Quote.load(path)
            self.assertEqual(loaded.total, Decimal("29.00"))

    def test_pdf_uses_numbered_section_and_description_without_title(self):
        section = Item(
            number="",
            title="",
            description="",
            section="Título da seção",
            section_number="1",
            is_section=True,
        )
        item = Item(
            number="1.1",
            title="",
            description="Descrição direta",
        )
        table = _items_table(Quote(items=[section, item]), _styles())
        self.assertEqual(table._cellvalues[2][0].getPlainText(), "1")
        self.assertEqual(table._cellvalues[2][1].getPlainText(), "Título da seção")
        self.assertEqual(table._cellvalues[3][1].getPlainText(), "Descrição direta")
        self.assertEqual(Quote(items=[section, item]).total, item.total)

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sections.json"
            Quote(items=[section, item]).save(path)
            loaded = Quote.load(path)
            self.assertTrue(loaded.items[0].is_section)

    def test_sections_and_items_are_numbered_automatically(self):
        quote = Quote(items=[
            Item("", "", "", section="Pintura", is_section=True),
            Item("", "", "Primeiro"),
            Item("", "", "Segundo"),
            Item("", "", "", section="Revestimentos", is_section=True),
            Item("", "", "Terceiro"),
        ])
        quote.normalize_sections()
        self.assertEqual(
            [(row.section_number if row.is_section else row.number) for row in quote.items],
            ["1", "1.1", "1.2", "2", "2.1"],
        )

    def test_empty_section_is_removed(self):
        quote = Quote(items=[Item("", "", "", section="Sem itens", is_section=True)])
        quote.normalize_sections()
        self.assertEqual(quote.items, [])

    def test_accumulated_totals_align_with_item_total_columns(self):
        self.assertAlmostEqual(sum(ACCUMULATED_TOTAL_WIDTHS[:2]), sum(ITEM_TABLE_WIDTHS[:6]))
        self.assertEqual(ACCUMULATED_TOTAL_WIDTHS[2:], ITEM_TABLE_WIDTHS[6:])
        self.assertIn(("GRID", (2, 0), (-1, 0), 0.45, BLACK), ACCUMULATED_TOTAL_STYLE)

    def test_subtotal_and_accumulated_material_and_labor_are_centered(self):
        quote = Quote(items=[
            Item("", "", "", section="Serviços", is_section=True),
            Item("", "", "Item", material_unit=money("80"), labor_unit=money("90")),
        ])
        quote.normalize_sections()
        styles = _styles()

        items_table = _items_table(quote, styles)
        subtotal_row = items_table._cellvalues[4]
        accumulated_row = _accumulated_total(quote, styles)._cellvalues[0]

        self.assertTrue(all(subtotal_row[column].style.alignment == 1 for column in (6, 7)))
        self.assertEqual(subtotal_row[8].style.alignment, 2)
        self.assertTrue(all(accumulated_row[column].style.alignment == 1 for column in (2, 3)))
        self.assertEqual(accumulated_row[4].style.alignment, 2)

    def test_final_total_column_is_only_slightly_wider_than_price_columns(self):
        price_columns = ITEM_TABLE_WIDTHS[4:8]
        final_total = ITEM_TABLE_WIDTHS[8]
        self.assertTrue(all(width == price_columns[0] for width in price_columns))
        self.assertGreater(final_total, price_columns[0])
        self.assertLessEqual(final_total, price_columns[0] * 1.15)

    def test_grouped_price_headers_omit_unwanted_dividers(self):
        table = _items_table(Quote(), _styles())
        line_commands = [command[:5] for command in table._linecmds]
        self.assertIn(("GRID", (0, 2), (-1, -1), 0.45, BLACK), line_commands)
        self.assertIn(("LINEBELOW", (0, 1), (-1, 1), 0.45, BLACK), line_commands)
        self.assertFalse(any(command[4] == HEADER for command in line_commands))
        for column in (1, 2, 3, 4, 6, 8):
            self.assertIn(("LINEBEFORE", (column, 0), (column, 1), 0.45, BLACK), line_commands)
        for column in (5, 7):
            self.assertNotIn(("LINEBEFORE", (column, 0), (column, 1), 0.45, BLACK), line_commands)

    def test_responsibility_boxes_align_with_page_content_edges(self):
        self.assertAlmostEqual(RESPONSIBILITY_WIDTH * 2 + RESPONSIBILITY_GAP, CONTENT_WIDTH)

    def test_signature_line_sits_close_to_signer_name(self):
        self.assertAlmostEqual(sum(SIGNATURE_ROW_HEIGHTS), 31 * 72 / 25.4)
        self.assertIn(("TOPPADDING", (1, 1), (1, 1), 0), SIGNATURE_STYLE)
        self.assertIn(("BOTTOMPADDING", (1, 1), (1, 1), 0), SIGNATURE_STYLE)
        self.assertIn(("TOPPADDING", (1, 2), (1, 2), 0), SIGNATURE_STYLE)

    def test_each_section_has_its_own_subtotal_and_separator(self):
        quote = Quote(items=[
            Item("", "", "", section="Primeira", is_section=True),
            Item("", "", "Item A", quantity=number("2"), material_unit=money("10"), labor_unit=money("5")),
            Item("", "", "", section="Segunda", is_section=True),
            Item("", "", "Item B", quantity=number("1"), material_unit=money("7"), labor_unit=money("3")),
        ])
        quote.normalize_sections()
        table = _items_table(quote, _styles())
        labels = [
            row[1].getPlainText() if hasattr(row[1], "getPlainText") else ""
            for row in table._cellvalues
        ]
        subtotal_rows = [index for index, label in enumerate(labels) if label == "Subtotal"]
        self.assertEqual(len(subtotal_rows), 2)
        self.assertEqual(table._cellvalues[subtotal_rows[0]][6].getPlainText(), "R$ 20,00")
        self.assertEqual(table._cellvalues[subtotal_rows[0]][7].getPlainText(), "R$ 10,00")
        self.assertEqual(labels[subtotal_rows[0] + 2], "Segunda")
        self.assertEqual(quote.total, money("40"))
        table.wrap(CONTENT_WIDTH, 10000)
        subtotal_height = table._rowHeights[subtotal_rows[0]]
        self.assertAlmostEqual(subtotal_height, table._rowHeights[subtotal_rows[0] - 1])
        self.assertAlmostEqual(subtotal_height, table._rowHeights[subtotal_rows[0] - 2])
        self.assertAlmostEqual(table._rowHeights[subtotal_rows[0] + 1], subtotal_height)

    def test_item_row_rejects_item_code_without_crashing(self):
        output = StringIO()
        with patch("builtins.input", return_value="1.1"), redirect_stdout(output):
            self.assertIsNone(ask_item_index(2))
        self.assertIn("Número de linha inválido", output.getvalue())

    def test_item_row_accepts_displayed_row_number(self):
        with patch("builtins.input", return_value="2"):
            self.assertEqual(ask_item_index(2), 1)

    def test_item_row_rejects_out_of_range_number(self):
        output = StringIO()
        with patch("builtins.input", return_value="3"), redirect_stdout(output):
            self.assertIsNone(ask_item_index(2))
        self.assertIn("Linha inexistente", output.getvalue())

    @patch("estimativa.cli.subprocess.Popen")
    def test_open_pdf_uses_default_macos_viewer(self, popen):
        pdf_path = Path("propostas/teste.pdf")
        with patch("estimativa.cli.sys.platform", "darwin"):
            open_pdf(pdf_path)
        self.assertEqual(popen.call_args.args[0], ["open", str(pdf_path)])


if __name__ == "__main__":
    unittest.main()
