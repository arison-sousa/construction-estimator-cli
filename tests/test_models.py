import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from estimativa.cli import ask_item_index, open_pdf
from estimativa.models import DEFAULT_TAXES, Item, Quote, brl, money, number
from estimativa.pdf_export import (
    ACCUMULATED_TOTAL_STYLE,
    ACCUMULATED_TOTAL_WIDTHS,
    BLACK,
    CONTENT_WIDTH,
    ITEM_TABLE_WIDTHS,
    RESPONSIBILITY_GAP,
    RESPONSIBILITY_WIDTH,
    _items_table,
    _styles,
)


class ModelTests(unittest.TestCase):
    def test_brazilian_money(self):
        self.assertEqual(money("20.000,50"), Decimal("20000.50"))
        self.assertEqual(brl(Decimal("20000.5")), "R$ 20.000,50")

    def test_default_taxes_have_the_required_multiline_wording(self):
        self.assertEqual(Quote().taxes, DEFAULT_TAXES)
        self.assertEqual(len(DEFAULT_TAXES.splitlines()), 8)
        self.assertIn("DEBASE CONSTRUTORA LTDA", DEFAULT_TAXES)

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
            section_number="1.0",
            is_section=True,
        )
        item = Item(
            number="1.1",
            title="",
            description="Descrição direta",
        )
        table = _items_table(Quote(items=[section, item]), _styles())
        self.assertEqual(table._cellvalues[2][0].getPlainText(), "1.0")
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
            ["1.0", "1.1", "1.2", "2.0", "2.1"],
        )

    def test_empty_section_is_removed(self):
        quote = Quote(items=[Item("", "", "", section="Sem itens", is_section=True)])
        quote.normalize_sections()
        self.assertEqual(quote.items, [])

    def test_accumulated_totals_align_with_item_total_columns(self):
        self.assertAlmostEqual(sum(ACCUMULATED_TOTAL_WIDTHS[:2]), sum(ITEM_TABLE_WIDTHS[:6]))
        self.assertEqual(ACCUMULATED_TOTAL_WIDTHS[2:], ITEM_TABLE_WIDTHS[6:])
        self.assertIn(("GRID", (2, 0), (-1, 0), 0.45, BLACK), ACCUMULATED_TOTAL_STYLE)

    def test_responsibility_boxes_align_with_page_content_edges(self):
        self.assertAlmostEqual(RESPONSIBILITY_WIDTH * 2 + RESPONSIBILITY_GAP, CONTENT_WIDTH)

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
        subtotal_rows = [index for index, label in enumerate(labels) if label == "SUB TOTAL"]
        self.assertEqual(len(subtotal_rows), 2)
        self.assertEqual(table._cellvalues[subtotal_rows[0]][6].getPlainText(), "R$ 20,00")
        self.assertEqual(table._cellvalues[subtotal_rows[0]][7].getPlainText(), "R$ 10,00")
        self.assertEqual(labels[subtotal_rows[0] + 2], "Segunda")
        self.assertEqual(quote.total, money("40"))

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
