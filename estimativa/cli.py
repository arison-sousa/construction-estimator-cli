from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

from .models import Item, Quote, brl, money, number
from .pdf_export import export_pdf


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOGO = ROOT / "assets" / "debase-logo.jpg"


def ask(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{label}{suffix}: ").strip()
    return answer or default


def ask_decimal(label: str, default="0"):
    while True:
        try:
            return number(ask(label, str(default).replace(".", ",")))
        except ValueError as exc:
            print(f"Erro: {exc}")


def ask_money(label: str, default="0"):
    while True:
        try:
            return money(ask(label, str(default).replace(".", ",")))
        except ValueError as exc:
            print(f"Erro: {exc}")


def ask_multiline(label: str, default: str = "") -> str:
    print(f"{label} (termine com uma linha contendo apenas .)")
    if default:
        print(f"Atual: {default}")
    lines = []
    while True:
        line = input("| ")
        if line == ".":
            break
        lines.append(line)
    return "\n".join(lines).strip() or default


def edit_info(quote: Quote) -> None:
    info = quote.info
    info.client = ask("Cliente", info.client)
    info.project = ask("Obra", info.project)
    info.contact = ask("Contato", info.contact)
    info.city = ask("Cidade", info.city)
    info.proposal = ask("Número da proposta", info.proposal)
    info.issue_date = ask("Data", info.issue_date)


def edit_company(quote: Quote) -> None:
    company = quote.company
    company.name = ask("Razão social", company.name)
    company.tax_id = ask("CNPJ", company.tax_id)
    company.state_registration = ask("Inscrição estadual", company.state_registration)
    company.address = ask("Endereço", company.address)
    company.city = ask("Cidade da empresa", company.city)
    company.postal_code = ask("CEP", company.postal_code)
    company.signer_name = ask("Nome do responsável", company.signer_name)
    company.signer_title = ask("Cargo", company.signer_title)
    company.signer_email = ask("E-mail", company.signer_email)
    company.signer_phone = ask("Telefone", company.signer_phone)


def input_item(existing: Item | None = None) -> Item:
    old = existing or Item(number="", title="", description="")
    description = "\n".join(part for part in (old.title, old.description) if part)
    return Item(
        section_number=old.section_number,
        section=old.section,
        number=old.number,
        title="",
        description=ask_multiline("Descrição", description),
        unit=ask("Unidade", old.unit),
        quantity=ask_decimal("Quantidade", old.quantity),
        material_unit=ask_money("Material unitário", old.material_unit),
        labor_unit=ask_money("Mão de obra unitária", old.labor_unit),
    )


def input_section(existing: Item | None = None) -> Item:
    old = existing or Item(number="", title="", description="", is_section=True)
    return Item(
        number="",
        title="",
        description="",
        section_number=old.section_number,
        section=ask("Título da seção", old.section),
        is_section=True,
    )


def section_positions(quote: Quote) -> list[int]:
    return [index for index, item in enumerate(quote.items) if item.is_section]


def choose_section(quote: Quote) -> int | None:
    positions = section_positions(quote)
    if not positions:
        return None
    if len(positions) == 1:
        position = positions[0]
        section = quote.items[position]
        print(f"Seção: {section.section_number} {section.section}")
        return position

    print("\nEscolha a seção:")
    for choice, position in enumerate(positions, 1):
        section = quote.items[position]
        print(f"{choice}. {section.section_number} {section.section}")
    try:
        choice = int(ask("Número da seção"))
    except ValueError:
        print("Seção inválida.")
        return None
    if not 1 <= choice <= len(positions):
        print(f"Seção inexistente. Digite um número entre 1 e {len(positions)}.")
        return None
    return positions[choice - 1]


def add_section_with_item(quote: Quote) -> None:
    print("\nNova seção")
    section = input_section()
    print("\nPrimeiro item da seção")
    item = input_item()
    quote.items.extend([section, item])
    quote.normalize_sections()


def add_item_to_section(quote: Quote) -> None:
    section_index = choose_section(quote)
    if section_index is None:
        print("Nenhuma seção cadastrada. Crie a seção e seu primeiro item.")
        add_section_with_item(quote)
        return

    insertion_index = section_index + 1
    while insertion_index < len(quote.items) and not quote.items[insertion_index].is_section:
        insertion_index += 1
    quote.items.insert(insertion_index, input_item())
    quote.renumber()


def remove_row(quote: Quote, index: int) -> None:
    row = quote.items[index]
    if row.is_section:
        end = index + 1
        while end < len(quote.items) and not quote.items[end].is_section:
            end += 1
        count = end - index - 1
        if ask(f"Remover a seção e seus {count} item(ns)? s/N", "N").lower() == "s":
            del quote.items[index:end]
            quote.renumber()
        return

    section_index = index - 1
    while section_index >= 0 and not quote.items[section_index].is_section:
        section_index -= 1
    next_is_section = index + 1 >= len(quote.items) or quote.items[index + 1].is_section
    only_item = section_index >= 0 and section_index + 1 == index and next_is_section
    if only_item:
        if ask("Este é o único item. Remover o item e sua seção? s/N", "N").lower() == "s":
            del quote.items[section_index:index + 1]
            quote.renumber()
    elif ask("Confirmar remoção? s/N", "N").lower() == "s":
        quote.items.pop(index)
        quote.renumber()


def print_summary(quote: Quote) -> None:
    print(f"\n{quote.info.proposal or '(sem número)'} — {quote.info.client or '(sem cliente)'}")
    print(f"Obra: {quote.info.project or '-'}")
    if not quote.items:
        print("Nenhum item cadastrado.")
    for index, item in enumerate(quote.items, 1):
        if item.is_section:
            print(f"{index:>2}. [SEÇÃO] {item.section_number} {item.section}")
            continue
        service = (item.description or item.title).splitlines()[0] if (item.description or item.title) else ""
        print(f"{index:>2}. {item.number:<6} {service[:48]:<48} {brl(item.total):>16}")
    print(f"Material: {brl(quote.material_total)}")
    print(f"Mão de obra: {brl(quote.labor_total)}")
    print(f"TOTAL: {brl(quote.total)}\n")


def edit_terms(quote: Quote) -> None:
    quote.validity = ask("Validade", quote.validity)
    quote.payment_terms = ask("Condição de pagamento", quote.payment_terms)
    quote.freight = ask("Frete", quote.freight)
    quote.start_deadline = ask("Prazo de início", quote.start_deadline)
    quote.execution_deadline = ask("Prazo de execução", quote.execution_deadline)
    quote.warranty = ask("Garantia", quote.warranty)
    quote.taxes = ask_multiline("Impostos recolhidos", quote.taxes)
    quote.notes = ask_multiline("Observação final", quote.notes)


def edit_list(title: str, values: list[str]) -> None:
    print(f"\n{title}")
    for index, value in enumerate(values, 1):
        print(f"{index}. {value}")
    print("Digite uma responsabilidade por linha; termine com .")
    replacement = []
    while True:
        value = input("| ").strip()
        if value == ".":
            break
        if value:
            replacement.append(value)
    if replacement:
        values[:] = replacement


def ask_item_index(item_count: int) -> int | None:
    """Ask for a displayed row number and return its zero-based index."""
    answer = ask("Número da linha")
    try:
        row_number = int(answer)
    except ValueError:
        print("Número de linha inválido. Digite o número mostrado à esquerda, por exemplo: 1.")
        return None

    if not 1 <= row_number <= item_count:
        print(f"Linha inexistente. Digite um número entre 1 e {item_count}.")
        return None
    return row_number - 1


def open_pdf(path: Path) -> None:
    """Open a generated PDF in the operating system's default viewer."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        print(f"Aviso: o PDF foi gerado, mas não foi possível abri-lo automaticamente: {exc}")


def editor(quote: Quote, path: Path) -> int:
    while True:
        quote.renumber()
        print_summary(quote)
        print("[1] Dados da proposta  [2] Adicionar item  [3] Editar linha  [4] Remover linha")
        print("[5] Condições  [6] Responsabilidades  [7] Salvar  [8] Salvar e gerar PDF")
        print("[9] Dados da empresa  [10] Adicionar seção + item  [0] Sair")
        choice = input("> ").strip()
        if choice == "1":
            edit_info(quote)
        elif choice == "2":
            add_item_to_section(quote)
        elif choice == "3":
            if not quote.items:
                continue
            index = ask_item_index(len(quote.items))
            if index is not None:
                if quote.items[index].is_section:
                    quote.items[index] = input_section(quote.items[index])
                else:
                    quote.items[index] = input_item(quote.items[index])
                quote.renumber()
        elif choice == "4":
            if not quote.items:
                continue
            index = ask_item_index(len(quote.items))
            if index is not None:
                remove_row(quote, index)
        elif choice == "5":
            edit_terms(quote)
        elif choice == "6":
            edit_list("Responsabilidades da contratante", quote.client_responsibilities)
            edit_list("Responsabilidades da construtora", quote.contractor_responsibilities)
        elif choice == "7":
            quote.save(path)
            print(f"Salvo em {path}")
        elif choice == "8":
            quote.save(path)
            pdf_path = path.with_suffix(".pdf")
            export_pdf(quote, pdf_path, DEFAULT_LOGO)
            print(f"Salvo em {path}\nPDF gerado em {pdf_path}")
            open_pdf(pdf_path)
        elif choice == "9":
            edit_company(quote)
        elif choice == "10":
            add_section_with_item(quote)
        elif choice == "0":
            if ask("Salvar antes de sair? S/n", "S").lower() != "n":
                quote.save(path)
                print(f"Salvo em {path}")
            return 0
        else:
            print("Opção inválida.")


def sample_quote() -> Quote:
    quote = Quote()
    quote.info.client = "JBS Seara"
    quote.info.project = "Saídas Emergência PPCI"
    quote.info.contact = "Ricardo Golfe"
    quote.info.city = "Seara - SC"
    quote.info.proposal = "0669-26-rev00"
    quote.info.issue_date = "19/07/2026"
    quote.items = [
        Item("1.1", "Demolição de lajes", "Demolição controlada de duas lajes em concreto armado, incluindo mão de obra, equipamentos, proteção, transporte e destinação final dos resíduos.", "vb", number("1"), money("20000"), money("29000"), "1 — Saídas Emergência PPCI"),
        Item("1.3", "Escada de Emergência 01", "Execução do enclausuramento da escada com parede corta-fogo, alvenaria de vedação e cortina em concreto armado, incluindo todos os materiais, equipamentos e serviços necessários.", "vb", number("1"), money("175000"), money("130000"), "1 — Saídas Emergência PPCI"),
        Item("1.4", "Escada de Emergência 02", "Fechamento com parede corta-fogo, alvenaria de vedação e laje de cobertura em concreto armado, conforme projeto estrutural.", "vb", number("1"), money("200000"), money("185000"), "1 — Saídas Emergência PPCI"),
        Item("1.5", "Portas corta-fogo", "Fornecimento e instalação de seis portas corta-fogo conforme normas técnicas vigentes e Projeto de Prevenção e Combate a Incêndio.", "und", number("6"), money("14000"), money("6000"), "1 — Saídas Emergência PPCI"),
        Item("1.6", "Saídas de emergência", "Abertura de vãos, demolição controlada e reforços estruturais para instalação de duas portas de saída de emergência.", "und", number("2"), money("9000"), money("5000"), "1 — Saídas Emergência PPCI"),
        Item("1.7", "Calhas de drenagem", "Fabricação e instalação de calhas com grelha removível em aço inox AISI 304, incluindo interligação à rede de esgoto.", "und", number("2"), money("9000"), money("5000"), "1 — Saídas Emergência PPCI"),
        Item("1.8", "Adequação sala de painéis elétricos", "Regularização de piso, revestimento monolítico, abertura de vão, instalação de porta e desmontagem de painéis isotérmicos.", "vb", number("1"), money("10000"), money("12000"), "1 — Saídas Emergência PPCI"),
    ]
    return quote


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orcamento", description="Crie e exporte propostas comerciais pelo terminal.")
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("novo", help="criar uma proposta interativamente")
    new.add_argument("arquivo", nargs="?", default="propostas/nova-proposta.json")
    edit = sub.add_parser("editar", help="editar uma proposta salva")
    edit.add_argument("arquivo")
    show = sub.add_parser("mostrar", help="mostrar totais de uma proposta")
    show.add_argument("arquivo")
    pdf = sub.add_parser("pdf", help="gerar PDF de uma proposta")
    pdf.add_argument("arquivo")
    pdf.add_argument("-o", "--saida")
    sample = sub.add_parser("exemplo", help="criar um exemplo JSON e PDF")
    sample.add_argument("--diretorio", default="output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "novo":
            path = Path(args.arquivo).expanduser()
            quote = Quote()
            edit_info(quote)
            return editor(quote, path)
        if args.command == "editar":
            path = Path(args.arquivo).expanduser()
            return editor(Quote.load(path), path)
        if args.command == "mostrar":
            print_summary(Quote.load(args.arquivo))
            return 0
        if args.command == "pdf":
            quote = Quote.load(args.arquivo)
            output = Path(args.saida).expanduser() if args.saida else Path(args.arquivo).with_suffix(".pdf")
            export_pdf(quote, output, DEFAULT_LOGO)
            print(f"PDF gerado em {output}")
            open_pdf(output)
            return 0
        if args.command == "exemplo":
            directory = Path(args.diretorio).expanduser()
            json_path = directory / "proposta-exemplo.json"
            pdf_path = directory / "proposta-exemplo.pdf"
            quote = sample_quote()
            quote.save(json_path)
            export_pdf(quote, pdf_path, DEFAULT_LOGO)
            print(f"Exemplo JSON: {json_path}\nExemplo PDF: {pdf_path}")
            open_pdf(pdf_path)
            return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    return 0
