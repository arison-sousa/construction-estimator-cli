import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from estimativa.models import Item, Quote, brl, money, number


class ModelTests(unittest.TestCase):
    def test_brazilian_money(self):
        self.assertEqual(money("20.000,50"), Decimal("20000.50"))
        self.assertEqual(brl(Decimal("20000.5")), "R$ 20.000,50")

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


if __name__ == "__main__":
    unittest.main()

