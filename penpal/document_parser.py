from dataclasses import dataclass

from penpal.lexer import TokenType
from penpal.markdown_parser import Command, MarkdownParser


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

