from dataclasses import dataclass
from enum import Enum, auto
from typing import Self

import yaml

from penpal.lexer import TokenType, Lexer, Token
from penpal.snippet import SnippetHeader, SnippetLanguage


@dataclass
class EmbedSnippet:
    snippet_name: str


@dataclass
class EmbedText:
    text: str


SnippetProductionRule = EmbedSnippet | EmbedText


class CommandType(Enum):
    UpdateSnippet = auto()
    ShowSnippet = auto()
    ExecuteProgram = auto()
    DefineSnippet = auto()
    GenerateProgram = auto()

    @classmethod
    def from_str(cls, s: str) -> Self:
        return {
            "update": CommandType.UpdateSnippet,
            "show": CommandType.ShowSnippet,
            "execute": CommandType.ExecuteProgram,
            "define": CommandType.DefineSnippet,
            "generate": CommandType.GenerateProgram,
        }[s]


@dataclass
class UpdateCommand:
    snippet_name: str
    update_data: str


@dataclass
class ShowCommand:
    snippet_name: str


@dataclass
class ExecuteProgram:
    pass


@dataclass
class DefineSnippet:
    header: SnippetHeader
    snippet_name: str
    content: list[SnippetProductionRule]


@dataclass
class GenerateProgram:
    pass


Command = (
    UpdateCommand
    | ShowCommand
    | ExecuteProgram
    | DefineSnippet
    | GenerateProgram
)


class MarkdownParser:
    BEGIN_COMMAND_SEQ = [TokenType.LeftBrace, TokenType.LeftBrace]
    END_COMMAND_SEQ = [TokenType.RightBrace, TokenType.RightBrace]
    END_MULTI_LINE_COMMAND_SEQ = [TokenType.Newline, *END_COMMAND_SEQ]

    def __init__(self, text: str) -> None:
        self.text = self
        self.lexer = Lexer(text)

    def read_tokens_until(self, break_on_type: TokenType) -> list[Token]:
        tokens = []
        while True:
            next_tok = self.lexer.peek()
            if next_tok.type in [break_on_type, TokenType.EOF]:
                break
            tokens.append(self.lexer.next())
        return tokens

    def read_tokens_until_any_sequence(self, break_on_any_of_sequences: list[list[TokenType]]) -> list[Token]:
        for break_on_sequence in break_on_any_of_sequences:
            if len(break_on_sequence) < 1:
                raise ValueError("Need at least one type to break on")

        tokens = []
        while True:
            next_tok = self.lexer.peek()
            if next_tok.type == TokenType.EOF:
                return tokens
            tokens.append(self.lexer.next())

            for break_on_sequence in break_on_any_of_sequences:
                # Look back at the last few tokens and see if it matches the break sequence
                last_few_tokens = tokens[-len(break_on_sequence) :]
                if [t.type for t in last_few_tokens] == break_on_sequence:
                    # Strip the break tokens
                    tokens = tokens[: -len(break_on_sequence)]
                    # Rewind the cursor
                    self.lexer.cursor = last_few_tokens[0].start_pos
                    return tokens

    def read_tokens_until_sequence(self, break_on_sequence: list[TokenType]) -> list[Token]:
        return self.read_tokens_until_any_sequence([break_on_sequence])

    def read_tokens_until_command_begins(self) -> list[Token]:
        return self.read_tokens_until_sequence(self.BEGIN_COMMAND_SEQ)

    def parse_snippet_production_rules(self) -> list[SnippetProductionRule]:
        out = []
        while True:
            # Handle nested commands
            tokens_before_nested_command = self.read_tokens_until_any_sequence(
                [self.BEGIN_COMMAND_SEQ, self.END_MULTI_LINE_COMMAND_SEQ, [*self.END_COMMAND_SEQ]]
            )
            # We might immediately have an embed-snippet rule, so it's not a guarantee that there will be text before
            # the first command.
            if len(tokens_before_nested_command):
                text_before_nested_command = "".join(t.value for t in tokens_before_nested_command)
                out.append(EmbedText(text_before_nested_command))

            # What's next?
            if self.lexer.peek_next_token_types_match(self.BEGIN_COMMAND_SEQ):
                self.match_command_open()
                embedded_snippet_name = self.match_word()
                self.match_command_close()
                out.append(EmbedSnippet(embedded_snippet_name))
            else:
                self.match_command_close()
                break

        return out

    def read_str_until_seq(self, delimiter_seq: list[TokenType]) -> str:
        tokens = self.read_tokens_until_sequence(delimiter_seq)
        return "".join(t.value for t in tokens)

    def read_str_until_any_seq(self, delimiter_seqs: list[list[TokenType]]) -> str:
        tokens = self.read_tokens_until_any_sequence(delimiter_seqs)
        return "".join(t.value for t in tokens)

    def read_str_until(self, delimiter: TokenType) -> str:
        return self.read_str_until_seq([delimiter])

    def expect(self, token_type: TokenType) -> Token:
        next_tok = self.lexer.next()
        if next_tok.type != token_type:
            raise RuntimeError(f"Expected {token_type}, but found {next_tok}")
        return next_tok

    def expect_seq(self, token_types: list[TokenType]) -> list[Token]:
        return [self.expect(tok_type) for tok_type in token_types]

    def match_command_open(self) -> list[Token]:
        return self.expect_seq(self.BEGIN_COMMAND_SEQ)

    def match_command_close(self) -> list[Token]:
        # Most characters to least characters
        delimiters = [
            [TokenType.Newline, *self.END_COMMAND_SEQ, TokenType.Newline],
            [TokenType.Newline, *self.END_COMMAND_SEQ],
            [*self.END_COMMAND_SEQ, TokenType.Newline],
            [*self.END_COMMAND_SEQ]
        ]
        for delimiter in delimiters:
            if self.lexer.peek_next_token_types_match(delimiter):
                return self.expect_seq(delimiter)
        raise ValueError("Failed to match a command close!")

    def match_word(self) -> str:
        return self.expect(TokenType.Word).value

    def parse_command__update(self) -> UpdateCommand:
        self.expect(TokenType.Space)
        snippet_name = self.expect(TokenType.Word)
        self.expect(TokenType.Newline)
        update_data = self.read_tokens_until_sequence(self.END_MULTI_LINE_COMMAND_SEQ)
        self.match_command_close()
        print(f"Parsing update, snippet name {snippet_name} {update_data}")

        return UpdateCommand(
            snippet_name=snippet_name.value,
            update_data="".join([t.value for t in update_data]),
        )

    def parse_command__show(self) -> ShowCommand:
        self.expect(TokenType.Space)
        snippet_name = self.expect(TokenType.Word)
        self.match_command_close()
        print(f"snippet name {snippet_name}")

        return ShowCommand(snippet_name=snippet_name.value)

    def parse_command__execute(self) -> ExecuteProgram:
        self.match_command_close()
        return ExecuteProgram()

    def parse_command__define(self) -> DefineSnippet:
        self.expect(TokenType.Space)
        snippet_name = self.read_str_until(TokenType.Newline)
        separate_head_from_content = [TokenType.Hash, TokenType.Hash, TokenType.Hash]
        terminate_shorthand_definition = [TokenType.Newline, TokenType.RightBrace, TokenType.RightBrace]
        header_str = self.read_str_until_any_seq([separate_head_from_content, terminate_shorthand_definition])
        header_dict = yaml.load(header_str, Loader=yaml.SafeLoader)
        header = SnippetHeader.parse_obj(header_dict)
        if self.lexer.peek_next_token_types_match(terminate_shorthand_definition):
            self.expect_seq([*terminate_shorthand_definition, TokenType.Newline])
            # Shorthand empty definition
            return DefineSnippet(
                snippet_name=snippet_name,
                header=header,
                content=[]
            )
        else:
            self.expect_seq([*separate_head_from_content, TokenType.Newline])
            content = self.parse_snippet_production_rules()
            return DefineSnippet(
                snippet_name=snippet_name,
                header=header,
                content=content,
            )

    def parse_command__generate(self) -> GenerateProgram:
        self.match_command_close()
        return GenerateProgram()

    def parse_command(self) -> Command:
        # Expect two braces
        self.match_command_open()
        # Command name
        command_name = self.expect(TokenType.Word)
        command_type = CommandType.from_str(command_name.value)
        print(f"Found command name {command_name.value} of type {command_type}")
        if command_type == CommandType.UpdateSnippet:
            return self.parse_command__update()
        elif command_type == CommandType.ShowSnippet:
            return self.parse_command__show()
        elif command_type == CommandType.ExecuteProgram:
            return self.parse_command__execute()
        elif command_type == CommandType.DefineSnippet:
            return self.parse_command__define()
        elif command_type == CommandType.GenerateProgram:
            return self.parse_command__generate()
        else:
            raise NotImplementedError(command_type)


class TestMarkdownParser:
    def test(self):
        source = """To get started, let's add `bitvec` to our crate's dependencies.

Now, let's start modeling the DNS header format! Make a new file, `packet_header_layout.rs`.
{{update main_imports
use std::net::UdpSocket;

use packet_header_layout;
}}
"""
        parser = MarkdownParser(source)
        tokens = parser.read_tokens_until(TokenType.LeftBrace)
        assert "".join([t.value for t in tokens]) == (
            "To get started, let's add `bitvec` to our crate's dependencies.\n"
            "\n"
            "Now, let's start modeling the DNS header format! Make a new file, "
            "`packet_header_layout.rs`.\n"
        )

        command = parser.parse_command()
        assert command == UpdateCommand(
            snippet_name="main_imports",
            update_data=("use std::net::UdpSocket;\n" "\n" "use packet_header_layout;\n"),
        )

    def test_define(self):
        source = """{{define main_runloop
file: src/main.rs
lang: rust
###
{{main_imports}}

const MAX_DNS_UDP_PACKET_SIZE: usize = 512;

fn main() {
{{main_runloop_bind_to_socket}}
    let mut receive_packet_buf = [0; MAX_DNS_UDP_PACKET_SIZE];
    println!("Awaiting incoming packets...");
    loop {
        let (byte_count_received, sender_addr) = socket
            .recv_from(&mut receive_packet_buf)
            .expect("Failed to read from the socket");

        println!("We've received a DNS query of {byte_count_received} bytes from {sender_addr:?}");
    }
}
}}
"""
        parser = MarkdownParser(source)
        tokens_before_command = parser.read_tokens_until_command_begins()
        text_before_command = "".join((t.value for t in tokens_before_command))
        assert text_before_command == ""

        command = parser.parse_command()
        assert command == DefineSnippet(
            snippet_name="main_runloop",
            header=SnippetHeader(
                lang=SnippetLanguage.RUST,
                file="src/main.rs",
            ),
            content=[
                EmbedSnippet("main_imports"),
                EmbedText(
                    """

const MAX_DNS_UDP_PACKET_SIZE: usize = 512;

fn main() {
"""
                ),
                EmbedSnippet("main_runloop_bind_to_socket"),
                EmbedText(
                    """
    let mut receive_packet_buf = [0; MAX_DNS_UDP_PACKET_SIZE];
    println!("Awaiting incoming packets...");
    loop {
        let (byte_count_received, sender_addr) = socket
            .recv_from(&mut receive_packet_buf)
            .expect("Failed to read from the socket");

        println!("We've received a DNS query of {byte_count_received} bytes from {sender_addr:?}");
    }
}"""
                ),
            ],
        )

    def test_parse_define(self):
        src = """{{define main_runloop
file: src/main.rs
lang: rust
###
{{main_module_definitions}}

const MAX_DNS_UDP_PACKET_SIZE: usize = 512;
}}"""
        parser = MarkdownParser(src)
        assert parser.parse_command() == DefineSnippet(
            header=SnippetHeader(
                lang=SnippetLanguage.RUST,
                is_executable=False,
                dependencies=[],
                file='src/main.rs'
            ),
            snippet_name='main_runloop',
            content=[
                EmbedSnippet(snippet_name='main_module_definitions'),
                EmbedText(text=
                    (
                        '\n'
                        'const MAX_DNS_UDP_PACKET_SIZE: usize = 512;'
                    )
                )
            ]
        )

    def test_embed_snippet_in_define(self):
        src = """{{define cargo_toml
file: Cargo.toml
lang: toml
###
[package]
name = "dns_resolver"
version = "0.1.0"
edition = "2021"

{{cargo_toml_dependencies}}
}}
"""
        parser = MarkdownParser(src)
        assert parser.parse_command() == DefineSnippet(
            header=SnippetHeader(
                lang=SnippetLanguage.TOML,
                is_executable=False,
                dependencies=[],
                file='Cargo.toml'
            ),
            snippet_name='cargo_toml',
            content=[
                EmbedText(text=
                    (
                        '[package]\n'
                        'name = "dns_resolver"\n'
                        'version = "0.1.0"\n'
                        'edition = "2021"\n'
                        '\n'
                    )
                ),
                EmbedSnippet(snippet_name='cargo_toml_dependencies')
            ]
        )
