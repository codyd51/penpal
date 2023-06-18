from dataclasses import dataclass

from penpal.lexer import TokenType
from penpal.markdown_parser import Command, MarkdownParser, DefineSnippet, EmbedSnippet, EmbedText, ShowCommand
from penpal.snippet import SnippetHeader, SnippetLanguage


@dataclass
class TextSection:
    text: str


@dataclass
class CommandSection:
    command: Command


DocumentSection = TextSection | CommandSection


def parse_document_text(text: str) -> list[DocumentSection]:
    output_sections = []
    parser = MarkdownParser(text)
    while True:
        tokens_before_command = parser.read_tokens_until_command_begins()
        # We may immediately start with a command
        if len(tokens_before_command):
            text_before_command = "".join(t.value for t in tokens_before_command)
            output_sections.append(TextSection(text_before_command))

        if parser.lexer.peek().type == TokenType.EOF:
            break

        output_sections.append(CommandSection(parser.parse_command()))

    return output_sections


class TestDocumentParser:
    def test_newlines(self):
        src = """{{define main_runloop
file: src/main.rs
lang: rust
###
{{main_module_definitions}}

const MAX_DNS_UDP_PACKET_SIZE: usize = 512;
}}


{{define main_module_definitions
lang: rust
}}

{{show main_runloop}}
"""
        sections = parse_document_text(src)
        assert sections == [
            CommandSection(
                command=DefineSnippet(
                    header=SnippetHeader(
                        lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file="src/main.rs"
                    ),
                    snippet_name="main_runloop",
                    content=[
                        EmbedSnippet(snippet_name="main_module_definitions"),
                        EmbedText(text="\n\nconst MAX_DNS_UDP_PACKET_SIZE: usize = 512;"),
                    ],
                )
            ),
            TextSection(text="\n\n\n"),
            CommandSection(
                command=DefineSnippet(
                    header=SnippetHeader(lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file=None),
                    snippet_name="main_module_definitions",
                    content=[],
                )
            ),
            TextSection(text="\n"),
            CommandSection(command=ShowCommand(snippet_name="main_runloop")),
            TextSection(text="\n"),
        ]
