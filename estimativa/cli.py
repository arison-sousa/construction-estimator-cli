from __future__ import annotations

import argparse
from datetime import date
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

from .models import Item, Quote, brl, money, number
from .naming import (
    identity_from_info,
    next_quote_identity,
    next_revision_identity,
    quote_path,
    set_quote_identity,
)
from .pdf_export import export_pdf
from .xlsx_export import export_xlsx


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOGO = ROOT / "assets" / "debase-logo.jpg"
DEFAULT_PROPOSALS_DIR = Path("propostas")


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


def _multiline_editor_command() -> list[str]:
    configured = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if configured:
        return shlex.split(configured, posix=os.name != "nt")
    if sys.platform == "darwin":
        return [
            "vim",
            "-Nu",
            "NONE",
            "-n",
            "-c",
            "set wrap linebreak textwidth=0 wrapmargin=0 backspace=indent,eol,start",
            "-c",
            "inoremap <C-O> <Cmd>write<CR>",
            "-c",
            "inoremap <C-X> <Cmd>wq<CR>",
            "-c",
            "nnoremap <C-O> :write<CR>",
            "-c",
            "nnoremap <C-X> :wq<CR>",
            "-c",
            "startinsert",
        ]
    if sys.platform.startswith("win"):
        return ["notepad"]
    if shutil.which("nano"):
        return ["nano"]
    return ["vi"]


def normalize_pasted_description(value: str) -> str:
    """Remove PDF margin line breaks while preserving the item heading and paragraphs."""
    source_lines = [line.strip() for line in value.strip().splitlines()]
    if len(source_lines) < 2:
        return value.strip()

    normalized = [source_lines[0]]
    current = ""
    for line in source_lines[1:]:
        if not line:
            if current:
                normalized.append(current)
                current = ""
            if normalized and normalized[-1] != "":
                normalized.append("")
            continue
        if current:
            current = f"{current} {line}"
        else:
            current = line
    if current:
        normalized.append(current)

    while normalized and normalized[-1] == "":
        normalized.pop()
    return "\n".join(normalized)


def ask_multiline(label: str, default: str = "") -> str:
    """Edit a multiline value in a terminal editor instead of committing one line at a time."""
    command = _multiline_editor_command()
    editor_name = Path(command[0]).name.lower()
    print(f"{label}: um editor de texto será aberto para você editar todas as linhas.")
    if editor_name in {"nano", "pico"}:
        print("Use as setas para editar; Ctrl+O e Enter salvam; Ctrl+X volta para a proposta.")
    elif editor_name == "vim":
        print("Use as setas para editar; Ctrl+O salva; Ctrl+X salva e volta para a proposta.")
    else:
        print("Salve o texto e feche o editor para voltar à proposta.")

    with tempfile.TemporaryDirectory(prefix="orcamento-") as temp_dir:
        text_path = Path(temp_dir) / "descricao.txt"
        text_path.write_text(default, encoding="utf-8")
        try:
            result = subprocess.run([*command, str(text_path)], check=False)
        except KeyboardInterrupt:
            print("\nEdição cancelada. O texto anterior foi mantido.")
            return default
        except OSError as exc:
            print(f"Não foi possível abrir o editor de texto: {exc}")
            return default
        if result.returncode != 0:
            print("O editor foi fechado sem concluir. O texto anterior foi mantido.")
            return default
        return text_path.read_text(encoding="utf-8").strip() or default


def edit_info(quote: Quote) -> None:
    info = quote.info
    info.client = ask("Cliente", info.client)
    info.location = ask("Local", info.location or info.city)
    info.project = ask("Obra", info.project)
    info.contact = ask("Contato", info.contact)
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
    edited_description = ask_multiline("Descrição", description)
    return Item(
        section_number=old.section_number,
        section=old.section,
        number=old.number,
        title="",
        description=normalize_pasted_description(edited_description),
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

    print("\nSeções disponíveis:")
    for position in positions:
        section = quote.items[position]
        print(f"{section.section_number}. {section.section}")

    answer = ask("Número da seção (Enter = última seção)")
    if not answer:
        return positions[-1]

    for position in positions:
        if quote.items[position].section_number == answer:
            return position
    print(f"Seção {answer} inexistente.")
    return None


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
    for item in quote.items:
        if item.is_section:
            print(f"{item.section_number:>4}  [SEÇÃO] {item.section}")
            continue
        service = (item.description or item.title).splitlines()[0] if (item.description or item.title) else ""
        print(f"{item.number:>4}  {service[:48]:<48} {brl(item.total):>16}")
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


def ask_row_index(quote: Quote) -> int | None:
    """Ask for a section/item number (for example 2 or 2.1) and locate it."""
    answer = ask("Número da seção ou item (ex.: 2 ou 2.1)")
    for index, row in enumerate(quote.items):
        row_number = row.section_number if row.is_section else row.number
        if row_number == answer:
            return index
    print(f"Linha {answer or '(vazia)'} inexistente.")
    return None


def edit_row(quote: Quote, index: int) -> None:
    """Edit a section title or all fields of an item without changing its number."""
    row = quote.items[index]
    quote.items[index] = input_section(row) if row.is_section else input_item(row)
    quote.renumber()


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


def open_folder(path: Path) -> None:
    """Open a folder in the operating system's file manager."""
    path.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        print(f"Não foi possível abrir a pasta de propostas: {exc}")


def proposal_paths(directory: Path = DEFAULT_PROPOSALS_DIR) -> list[Path]:
    """Return saved proposals with the newest proposal numbers first."""
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"), key=lambda path: path.name, reverse=True)


def print_proposal_list(directory: Path = DEFAULT_PROPOSALS_DIR) -> list[Path]:
    paths = proposal_paths(directory)
    print("\nPROPOSTAS SALVAS")
    if not paths:
        print("Nenhuma proposta encontrada.")
        return []

    for index, path in enumerate(paths, 1):
        try:
            info = Quote.load(path).info
            proposal = info.proposal or path.stem.split(" - ", 1)[0]
            client = info.client or "(sem cliente)"
            project = info.project or "(sem obra)"
            print(f"{index}. {proposal} | {client} | {project} | {info.issue_date}")
        except (OSError, ValueError, KeyError):
            print(f"{index}. {path.stem}")
    return paths


def choose_proposal(directory: Path = DEFAULT_PROPOSALS_DIR) -> Path | None:
    paths = print_proposal_list(directory)
    if not paths:
        return None
    answer = ask("Número da proposta (0 = voltar)")
    try:
        choice = int(answer)
    except ValueError:
        print("Número inválido.")
        return None
    if choice == 0:
        return None
    if not 1 <= choice <= len(paths):
        print(f"Proposta inexistente. Digite um número entre 1 e {len(paths)}.")
        return None
    return paths[choice - 1]


def editor(quote: Quote, path: Path) -> int:
    while True:
        quote.renumber()
        print_summary(quote)
        print("[1] Dados da proposta")
        print("[2] Adicionar seção")
        print("[3] Adicionar item")
        print("[4] Remover linha")
        print("[5] Condições")
        print("[6] Editar linha")
        print("[7] Salvar e gerar PDF")
        print("[9] Dados da empresa")
        print("[0] Sair")
        choice = input("> ").strip()
        if choice == "1":
            edit_info(quote)
        elif choice == "2":
            add_section_with_item(quote)
        elif choice == "3":
            add_item_to_section(quote)
        elif choice == "4":
            if not quote.items:
                continue
            index = ask_row_index(quote)
            if index is not None:
                remove_row(quote, index)
        elif choice == "5":
            edit_terms(quote)
        elif choice == "6":
            if not quote.items:
                continue
            index = ask_row_index(quote)
            if index is not None:
                edit_row(quote, index)
        elif choice == "7":
            quote.save(path)
            pdf_path = path.with_suffix(".pdf")
            export_pdf(quote, pdf_path, DEFAULT_LOGO)
            print(f"Salvo em {path}\nPDF gerado em {pdf_path}")
            open_pdf(pdf_path)
        elif choice == "9":
            edit_company(quote)
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


def create_quote(directory: Path = DEFAULT_PROPOSALS_DIR) -> int:
    quote = Quote()
    edit_info(quote)
    set_quote_identity(quote, next_quote_identity(directory, date.today().year))
    path = quote_path(quote, directory)
    print(f"Nova proposta: {quote.info.proposal}\nArquivo: {path}")
    return editor(quote, path)


def edit_quote(path: Path) -> int:
    return editor(Quote.load(path), path)


def revise_quote(source: Path) -> int:
    quote = Quote.load(source)
    current = identity_from_info(quote.info)
    if current is None:
        raise ValueError("Não foi possível identificar o número da proposta existente.")
    revised = next_revision_identity(source.parent, current)
    set_quote_identity(quote, revised)
    quote.info.issue_date = date.today().strftime("%d/%m/%Y")
    path = quote_path(quote, source.parent)
    print(f"Nova revisão: {quote.info.proposal}\nArquivo: {path}")
    return editor(quote, path)


def view_quote_pdf(source: Path) -> Path:
    quote = Quote.load(source)
    output = source.with_suffix(".pdf")
    export_pdf(quote, output, DEFAULT_LOGO)
    print(f"PDF gerado em {output}")
    open_pdf(output)
    return output


def home(directory: Path = DEFAULT_PROPOSALS_DIR) -> int:
    while True:
        print("\nDEBASE — PROPOSTAS\n")
        print("1 Nova proposta")
        print("2 Editar proposta")
        print("3 Criar revisão")
        print("4 Listar propostas")
        print("5 Visualizar PDF")
        print("6 Abrir folder proposta")
        print("0 Sair")
        choice = input("> ").strip()

        if choice == "1":
            create_quote(directory)
        elif choice == "2":
            path = choose_proposal(directory)
            if path is not None:
                edit_quote(path)
        elif choice == "3":
            path = choose_proposal(directory)
            if path is not None:
                revise_quote(path)
        elif choice == "4":
            print_proposal_list(directory)
            input("\nPressione Enter para voltar.")
        elif choice == "5":
            path = choose_proposal(directory)
            if path is not None:
                view_quote_pdf(path)
        elif choice == "6":
            open_folder(directory)
        elif choice == "0":
            return 0
        else:
            print("Opção inválida.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orcamento", description="Crie e exporte propostas comerciais pelo terminal.")
    sub = parser.add_subparsers(dest="command")
    new = sub.add_parser("novo", help="criar uma proposta interativamente")
    new.add_argument("--diretorio", default="propostas", help="pasta onde a proposta será salva")
    edit = sub.add_parser("editar", help="editar uma proposta salva")
    edit.add_argument("arquivo")
    revise = sub.add_parser("revisar", help="criar a próxima revisão de uma proposta")
    revise.add_argument("arquivo")
    show = sub.add_parser("mostrar", help="mostrar totais de uma proposta")
    show.add_argument("arquivo")
    pdf = sub.add_parser("pdf", help="gerar PDF de uma proposta")
    pdf.add_argument("arquivo")
    pdf.add_argument("-o", "--saida")
    excel = sub.add_parser("excel", help="gerar Excel de uma proposta")
    excel.add_argument("arquivo")
    excel.add_argument("-o", "--saida")
    sample = sub.add_parser("exemplo", help="criar um exemplo JSON e PDF")
    sample.add_argument("--diretorio", default="output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command is None:
            return home()
        if args.command == "novo":
            directory = Path(args.diretorio).expanduser()
            return create_quote(directory)
        if args.command == "editar":
            path = Path(args.arquivo).expanduser()
            return edit_quote(path)
        if args.command == "revisar":
            source = Path(args.arquivo).expanduser()
            return revise_quote(source)
        if args.command == "mostrar":
            print_summary(Quote.load(args.arquivo))
            return 0
        if args.command == "pdf":
            if args.saida:
                quote = Quote.load(args.arquivo)
                output = Path(args.saida).expanduser()
                export_pdf(quote, output, DEFAULT_LOGO)
                print(f"PDF gerado em {output}")
                open_pdf(output)
            else:
                view_quote_pdf(Path(args.arquivo).expanduser())
            return 0
        if args.command == "excel":
            quote = Quote.load(args.arquivo)
            output = Path(args.saida).expanduser() if args.saida else Path(args.arquivo).expanduser().with_suffix(".xlsx")
            export_xlsx(quote, output, DEFAULT_LOGO)
            print(f"Excel gerado em {output}")
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
