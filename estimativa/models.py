from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Any


ZERO = Decimal("0.00")


def money(value: Any) -> Decimal:
    """Parse Decimal values, including Brazilian input such as 20.000,50."""
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    text = str(value or "0").strip().replace("R$", "").replace(" ", "")
    if not text:
        return ZERO
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"Valor monetário inválido: {value!r}") from exc


def number(value: Any) -> Decimal:
    text = str(value or "0").strip().replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Quantidade inválida: {value!r}") from exc
    if result < 0:
        raise ValueError("A quantidade não pode ser negativa")
    return result


def brl(value: Decimal) -> str:
    value = money(value)
    formatted = f"{value:,.2f}"
    return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def decimal_text(value: Decimal) -> str:
    places = 2 if value == value.quantize(Decimal("0.01")) else 4
    return f"{value:.{places}f}".replace(".", ",")


@dataclass
class Company:
    name: str = "DEBASE CONSTRUTORA LTDA"
    tax_id: str = "30.884.014/0001-86"
    state_registration: str = "25.873.821-9"
    address: str = "Rua Jacutinga nº 449 Bairro Efapi"
    city: str = "Chapecó - SC"
    postal_code: str = "89.809-810"
    signer_name: str = "Ceser Kiefer"
    signer_title: str = "Diretor"
    signer_email: str = "comercial@debaseconstrutora.com.br"
    signer_phone: str = "(49) 99926-9847"


@dataclass
class QuoteInfo:
    client: str = ""
    project: str = ""
    contact: str = ""
    city: str = ""
    proposal: str = ""
    issue_date: str = field(default_factory=lambda: date.today().strftime("%d/%m/%Y"))


@dataclass
class Item:
    number: str
    title: str
    description: str
    unit: str = "vb"
    quantity: Decimal = Decimal("1")
    material_unit: Decimal = ZERO
    labor_unit: Decimal = ZERO
    section: str = ""

    @property
    def material_total(self) -> Decimal:
        return money(self.quantity * self.material_unit)

    @property
    def labor_total(self) -> Decimal:
        return money(self.quantity * self.labor_unit)

    @property
    def total(self) -> Decimal:
        return self.material_total + self.labor_total

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Item":
        values = dict(data)
        values["quantity"] = number(values.get("quantity", 0))
        values["material_unit"] = money(values.get("material_unit", 0))
        values["labor_unit"] = money(values.get("labor_unit", 0))
        return cls(**values)


DEFAULT_CLIENT_RESPONSIBILITIES = [
    "Liberar toda a área para execução dos serviços;",
    "Acompanhar os serviços e fornecer definições quando necessário;",
    "Deslocar interferências na execução dos serviços que não foram listadas na planilha do orçamento;",
    "Fornecer água e energia elétrica (220/380 V) necessária para a execução dos serviços;",
    "Permitir montagem do canteiro de obras próximo ao local dos serviços;",
]

DEFAULT_CONTRACTOR_RESPONSIBILITIES = [
    "Fornecer todos os itens exigidos pela legislação trabalhista;",
    "Fornecer material e mão de obra qualificada para execução dos serviços contratados;",
    "Fornecer todos os equipamentos necessários para execução dos serviços contratados;",
    "Zelar pela organização e limpeza da obra e do canteiro durante o andamento da mesma;",
]

DEFAULT_TAXES = (
    "Sobre a mão de obra: INSS incluso no orçamento. ISS incluso no orçamento. "
    "Sobre material faturado: PIS 0,65% incluso; COFINS 3,0% incluso; "
    "IRPJ 1,20% incluso; ICMS e IPI 0% para construção civil isenta."
)


@dataclass
class Quote:
    company: Company = field(default_factory=Company)
    info: QuoteInfo = field(default_factory=QuoteInfo)
    items: list[Item] = field(default_factory=list)
    client_responsibilities: list[str] = field(default_factory=lambda: list(DEFAULT_CLIENT_RESPONSIBILITIES))
    contractor_responsibilities: list[str] = field(default_factory=lambda: list(DEFAULT_CONTRACTOR_RESPONSIBILITIES))
    validity: str = "15 dias"
    payment_terms: str = "120 ddf"
    freight: str = "CIF"
    start_deadline: str = "7 dias"
    execution_deadline: str = "7 dias"
    warranty: str = "2 anos"
    taxes: str = DEFAULT_TAXES
    notes: str = "Atenciosamente,"

    @property
    def material_total(self) -> Decimal:
        return sum((item.material_total for item in self.items), ZERO)

    @property
    def labor_total(self) -> Decimal:
        return sum((item.labor_total for item in self.items), ZERO)

    @property
    def total(self) -> Decimal:
        return self.material_total + self.labor_total

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for item in data["items"]:
            for key in ("quantity", "material_unit", "labor_unit"):
                item[key] = str(item[key])
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Quote":
        values = dict(data)
        values["company"] = Company(**values.get("company", {}))
        values["info"] = QuoteInfo(**values.get("info", {}))
        values["items"] = [Item.from_dict(item) for item in values.get("items", [])]
        return cls(**values)

    def save(self, path: str | Path) -> Path:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> "Quote":
        source = Path(path).expanduser()
        return cls.from_dict(json.loads(source.read_text(encoding="utf-8")))

