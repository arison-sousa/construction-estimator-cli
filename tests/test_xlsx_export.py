from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from estimativa.models import Item, Quote, money, number
from estimativa.xlsx_export import export_xlsx


class XlsxExportTests(unittest.TestCase):
    def sample_quote(self) -> Quote:
        quote = Quote(items=[
            Item("", "", "", section="Serviços", is_section=True),
            Item("", "", "Primeiro item", "un", number("2"), money("10"), money("5")),
            Item("", "", "Segundo item", "un", number("1"), money("7"), money("3")),
        ])
        quote.info.client = "Cliente"
        quote.info.location = "Local"
        quote.info.project = "Obra"
        quote.info.proposal = "0001-26-00"
        quote.normalize_sections()
        return quote

    def test_export_creates_formula_driven_print_ready_workbook(self):
        quote = self.sample_quote()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "proposta.xlsx"
            export_xlsx(quote, output)

            self.assertTrue(output.exists())
            with ZipFile(output) as archive:
                sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
                workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")

        self.assertIn("<f>D9*E9</f><v>20.0</v>", sheet_xml)
        self.assertIn("<f>D9*F9</f><v>10.0</v>", sheet_xml)
        self.assertIn("<f>G9+H9</f><v>30.0</v>", sheet_xml)
        self.assertIn("<f>SUM(G9:G10)</f><v>27.0</v>", sheet_xml)
        self.assertIn('orientation="landscape"', sheet_xml)
        self.assertIn('paperSize="9"', sheet_xml)
        self.assertIn('_xlnm.Print_Area', workbook_xml)
        self.assertEqual(quote.total, Decimal("40.00"))

    def test_export_handles_quote_without_items(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "empty.xlsx"
            export_xlsx(Quote(), output)
            with ZipFile(output) as archive:
                sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")

        self.assertIn("<f>0</f><v>0.0</v>", sheet_xml)


if __name__ == "__main__":
    unittest.main()
