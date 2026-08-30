from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from estimativa.cli import (
    DEFAULT_PROPOSALS_DIR,
    _multiline_editor_command,
    add_item_to_section,
    ask_multiline,
    ask_row_index,
    edit_row,
    home,
    main,
    normalize_pasted_description,
    open_folder,
    proposal_paths,
)
from estimativa.models import Item, Quote


class AskMultilineTests(unittest.TestCase):
    def test_normalizes_line_breaks_copied_from_a_pdf(self):
        pasted = """Paredes de painel termoisolante
Fornecimento de todos os materiais necessários para a montagem
de 86 m2 de paredes em concreto armado.
As paredes deverão ser executadas com painéis termoisolantes de ambos
os lados, conforme aprovado pela fiscalização."""

        self.assertEqual(
            normalize_pasted_description(pasted),
            """Paredes de painel termoisolante
Fornecimento de todos os materiais necessários para a montagem de 86 m2 de paredes em concreto armado. As paredes deverão ser executadas com painéis termoisolantes de ambos os lados, conforme aprovado pela fiscalização.""",
        )

    def test_normalization_preserves_blank_paragraphs(self):
        pasted = "Título\nPrimeiro parágrafo sem ponto\n\nSegundo parágrafo"

        self.assertEqual(
            normalize_pasted_description(pasted),
            "Título\nPrimeiro parágrafo sem ponto\n\nSegundo parágrafo",
        )

    @patch("estimativa.cli.sys.platform", "darwin")
    @patch.dict("estimativa.cli.os.environ", {}, clear=True)
    def test_macos_editor_visually_wraps_without_changing_the_text(self):
        command = _multiline_editor_command()

        self.assertEqual(command[0], "vim")
        self.assertIn("set wrap linebreak textwidth=0 wrapmargin=0 backspace=indent,eol,start", command)
        self.assertIn("inoremap <C-O> <Cmd>write<CR>", command)
        self.assertIn("inoremap <C-X> <Cmd>wq<CR>", command)

    @patch("estimativa.cli._multiline_editor_command", return_value=["test-editor"])
    @patch("estimativa.cli.subprocess.run")
    def test_returns_the_complete_text_saved_by_the_editor(self, run, _command):
        def save_edited_text(command, check):
            Path(command[-1]).write_text("Primeira linha\nSegunda linha\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0)

        run.side_effect = save_edited_text

        self.assertEqual(
            ask_multiline("Descrição", "Texto anterior"),
            "Primeira linha\nSegunda linha",
        )

    @patch("estimativa.cli._multiline_editor_command", return_value=["test-editor"])
    @patch("estimativa.cli.subprocess.run")
    def test_does_not_pre_wrap_a_long_existing_description(self, run, _command):
        description = ("Descrição muito longa " * 20).strip()

        def inspect_text(command, check):
            self.assertEqual(Path(command[-1]).read_text(encoding="utf-8"), description)
            return subprocess.CompletedProcess(command, 0)

        run.side_effect = inspect_text
        self.assertEqual(ask_multiline("Descrição", description), description)

    @patch("estimativa.cli._multiline_editor_command", return_value=["test-editor"])
    @patch("estimativa.cli.subprocess.run")
    def test_keeps_the_previous_text_when_the_editor_fails(self, run, _command):
        run.return_value = subprocess.CompletedProcess(["test-editor"], 1)

        self.assertEqual(ask_multiline("Descrição", "Texto anterior"), "Texto anterior")


class SectionCommandTests(unittest.TestCase):
    def setUp(self):
        self.quote = Quote(items=[
            Item("", "", "", section="Primeira", is_section=True),
            Item("", "", "Item 1"),
            Item("", "", "", section="Segunda", is_section=True),
            Item("", "", "Item 2"),
        ])
        self.quote.normalize_sections()

    @patch("estimativa.cli.input_item", return_value=Item("", "", "Novo"))
    def test_blank_section_adds_item_to_the_last_section(self, _input_item):
        with patch("builtins.input", return_value=""):
            add_item_to_section(self.quote)

        self.assertEqual([row.number for row in self.quote.items if not row.is_section], ["1.1", "2.1", "2.2"])
        self.assertEqual(self.quote.items[-1].description, "Novo")

    @patch("estimativa.cli.input_item", return_value=Item("", "", "Novo"))
    def test_section_number_inserts_after_that_sections_last_item(self, _input_item):
        with patch("builtins.input", return_value="1"):
            add_item_to_section(self.quote)

        self.assertEqual(self.quote.items[2].description, "Novo")
        self.assertEqual(self.quote.items[2].number, "1.2")

    def test_remove_lookup_accepts_section_and_item_numbers(self):
        with patch("builtins.input", return_value="2"):
            self.assertEqual(ask_row_index(self.quote), 2)
        with patch("builtins.input", return_value="2.1"):
            self.assertEqual(ask_row_index(self.quote), 3)

    @patch("estimativa.cli.input_section", return_value=Item("", "", "", section="Editada", is_section=True))
    def test_edit_section_preserves_its_number(self, _input_section):
        edit_row(self.quote, 0)

        self.assertEqual(self.quote.items[0].section, "Editada")
        self.assertEqual(self.quote.items[0].section_number, "1")

    @patch("estimativa.cli.input_item", return_value=Item("", "", "Item editado"))
    def test_edit_item_preserves_its_number(self, _input_item):
        edit_row(self.quote, 3)

        self.assertEqual(self.quote.items[3].description, "Item editado")
        self.assertEqual(self.quote.items[3].number, "2.1")


class HomeMenuTests(unittest.TestCase):
    @patch("estimativa.cli.create_quote", return_value=0)
    def test_new_uses_the_external_proposals_folder_by_default(self, create_quote):
        self.assertEqual(main(["novo"]), 0)
        create_quote.assert_called_once_with(DEFAULT_PROPOSALS_DIR)

    def test_saved_proposals_are_listed_with_newest_number_first(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / "0001-26-00 - Primeira.json").write_text("{}", encoding="utf-8")
            (directory / "0003-26-00 - Terceira.json").write_text("{}", encoding="utf-8")
            (directory / "0002-26-00 - Segunda.json").write_text("{}", encoding="utf-8")

            self.assertEqual(
                [path.name for path in proposal_paths(directory)],
                [
                    "0003-26-00 - Terceira.json",
                    "0002-26-00 - Segunda.json",
                    "0001-26-00 - Primeira.json",
                ],
            )

    @patch("estimativa.cli.edit_quote")
    def test_home_selects_a_proposal_by_number_for_editing(self, edit_quote):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            selected = directory / "0001-26-00 - Cliente - Obra.json"
            Quote().save(selected)

            with patch("builtins.input", side_effect=["2", "1", "0"]), redirect_stdout(StringIO()):
                self.assertEqual(home(directory), 0)

            edit_quote.assert_called_once_with(selected)

    @patch("estimativa.cli.home", return_value=0)
    def test_no_command_opens_the_home_menu(self, home_menu):
        self.assertEqual(main([]), 0)
        home_menu.assert_called_once_with()

    @patch("estimativa.cli.subprocess.Popen")
    def test_open_folder_uses_finder_on_macos(self, popen):
        with tempfile.TemporaryDirectory() as folder, patch("estimativa.cli.sys.platform", "darwin"):
            open_folder(Path(folder))

        self.assertEqual(popen.call_args.args[0], ["open", folder])

    @patch("estimativa.cli.export_xlsx")
    def test_excel_command_exports_next_to_json_by_default(self, export_xlsx):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(StringIO()):
            source = Path(folder) / "proposta.json"
            Quote().save(source)

            self.assertEqual(main(["excel", str(source)]), 0)

        export_xlsx.assert_called_once()
        args = export_xlsx.call_args.args
        self.assertEqual(args[1], source.with_suffix(".xlsx"))


if __name__ == "__main__":
    unittest.main()
