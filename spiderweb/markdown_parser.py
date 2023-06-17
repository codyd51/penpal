from dataclasses import dataclass
from enum import Enum
from typing import Self

import yaml

from spiderweb.lexer import TokenType, Lexer, Token, TestLexer
from spiderweb.snippet import SnippetHeader, SnippetLanguage


@dataclass
class EmbedSnippet:
    snippet_name: str


@dataclass
class EmbedText:
    text: str


SnippetProductionRule = EmbedSnippet | EmbedText


class CommandType(Enum):
    UpdateSnippet = (0,)
    ShowSnippet = (1,)
    ExecuteProgram = (2,)
    DefineSnippet = (3,)

    @classmethod
    def from_str(cls, s: str) -> Self:
        return {
            "update": CommandType.UpdateSnippet,
            "show": CommandType.ShowSnippet,
            "execute": CommandType.ExecuteProgram,
            "define": CommandType.DefineSnippet,
        }[s]


@dataclass
class UpdateCommand:
    type: CommandType
    snippet_name: str
    update_data: str


@dataclass
class ShowCommand:
    type: CommandType
    snippet_name: str


@dataclass
class ExecuteProgram:
    type: CommandType


@dataclass
class DefineSnippet:
    type: CommandType
    # TODO(PT): Replace with InlineSnippet
    header: SnippetHeader
    snippet_name: str
    content: list[SnippetProductionRule]


Command = UpdateCommand | ShowCommand | ExecuteProgram | DefineSnippet


class MarkdownParser:
    BEGIN_COMMAND_SEQ = [TokenType.LeftBrace, TokenType.LeftBrace]
    END_COMMAND_SEQ = [TokenType.RightBrace, TokenType.RightBrace]

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

    def read_tokens_until_command_ends(self) -> list[Token]:
        out = []
        # Handle nested commands
        while True:
            tokens_before_nested_command = self.read_tokens_until_any_sequence(
                [self.BEGIN_COMMAND_SEQ, self.END_COMMAND_SEQ]
            )
            print("".join(t.value for t in tokens_before_nested_command))
            # What's next?
            peek = self.lexer.peek()
            # A double-peek would be nice to be totally sure of our state
            if peek.type == TokenType.LeftBrace:
                print(f"Found a nested command!")
            elif peek.type == TokenType.RightBrace:
                print(f"Found the end of a command")
            else:
                raise ValueError(f"Unexpected token type {peek.type}")
            return

    def parse_snippet_production_rules(self) -> list[SnippetProductionRule]:
        out = []
        while True:
            # Handle nested commands
            tokens_before_nested_command = self.read_tokens_until_any_sequence(
                [self.BEGIN_COMMAND_SEQ, self.END_COMMAND_SEQ]
            )
            # We might immediately have an embed-snippet rule
            if len(tokens_before_nested_command):
                text_before_nested_command = "".join(t.value for t in tokens_before_nested_command)
                out.append(EmbedText(text_before_nested_command))

            # What's next?
            peek = self.lexer.peek()
            # A double-peek would be nice to be totally sure of our state
            if peek.type == TokenType.LeftBrace:
                print(f"Found a nested snippet!")
                self.match_command_open()
                embedded_snippet_name = self.match_word()
                self.match_command_close()
                out.append(EmbedSnippet(embedded_snippet_name))
            elif peek.type == TokenType.RightBrace:
                print(f"Found the end of a command")
                self.match_command_close()
                break
            else:
                raise ValueError(f"Unexpected token type {peek.type}")

        return out

    def read_str_until_seq(self, delimiter_seq: list[TokenType]) -> str:
        tokens = self.read_tokens_until_sequence(delimiter_seq)
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
        return self.expect_seq(self.END_COMMAND_SEQ)

    def match_word(self) -> str:
        return self.expect(TokenType.Word).value

    def parse_command(self) -> Command:
        # Expect two braces
        self.match_command_open()
        # Command name
        command_name = self.expect(TokenType.Word)
        command_type = CommandType.from_str(command_name.value)
        print(f"Found command name {command_name} of type {command_type}")
        if command_type == CommandType.UpdateSnippet:
            self.expect(TokenType.Space)
            snippet_name = self.expect(TokenType.Word)
            self.expect(TokenType.Newline)
            update_data = self.read_tokens_until_sequence(self.END_COMMAND_SEQ)
            self.match_command_close()
            print(f"snippet name {snippet_name} {update_data}")

            return UpdateCommand(
                type=CommandType.UpdateSnippet,
                snippet_name=snippet_name.value,
                update_data="".join([t.value for t in update_data]),
            )
        elif command_type == CommandType.ShowSnippet:
            self.expect(TokenType.Space)
            snippet_name = self.expect(TokenType.Word)
            self.match_command_close()
            print(f"snippet name {snippet_name}")

            return ShowCommand(
                type=CommandType.ShowSnippet,
                snippet_name=snippet_name.value,
            )
        elif command_type == CommandType.ExecuteProgram:
            self.match_command_close()
            return ExecuteProgram(type=CommandType.ExecuteProgram)
        elif command_type == CommandType.DefineSnippet:
            self.expect(TokenType.Space)
            snippet_name = self.read_str_until(TokenType.Newline)
            header_separator = [TokenType.Hash, TokenType.Hash, TokenType.Hash]
            header_str = self.read_str_until_seq(header_separator)
            header_dict = yaml.load(header_str, Loader=yaml.SafeLoader)
            header = SnippetHeader.parse_obj(header_dict)
            self.expect_seq(header_separator)
            self.expect(TokenType.Newline)
            content = self.parse_snippet_production_rules()
            return DefineSnippet(
                type=CommandType.DefineSnippet,
                snippet_name=snippet_name,
                header=header,
                content=content,
            )
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
            type=CommandType.UpdateSnippet,
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
            type=CommandType.DefineSnippet,
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
}
"""
                ),
            ],
        )
