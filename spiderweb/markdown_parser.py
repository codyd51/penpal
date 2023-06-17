from dataclasses import dataclass
from enum import Enum, auto
from typing import Self

Cursor = int


class TokenType(Enum):
    EOF = auto(),
    Word = auto(),
    Comma = auto(),
    LeftBrace = auto(),
    RightBrace = auto(),
    Space = auto(),
    Newline = auto(),

    @classmethod
    def try_from_str(cls, s: str) -> Self | None:
        mapping = {
            ",": TokenType.Comma,
            "{": TokenType.LeftBrace,
            "}": TokenType.RightBrace,
            " ": TokenType.Space,
            "\n": TokenType.Newline,
        }
        if s in mapping:
            return mapping[s]
        return None


@dataclass
class Token:
    type: TokenType
    value: str
    start_pos: int
    end_pos: int

    @classmethod
    def eof(cls, text_len: int) -> Self:
        return cls(
            type=TokenType.EOF,
            value="",
            start_pos=text_len,
            end_pos=text_len,
        )


class Lexer:
    _DELIMITERS_TO_TYPES = {
        ",": TokenType.Comma,
        "{": TokenType.LeftBrace,
        "}": TokenType.RightBrace,
        " ": TokenType.Space,
        "\n": TokenType.Newline,
    }

    def __init__(self, text: str) -> None:
        self.text = text
        self.cursor = 0

    def peek(self) -> Token:
        if self.cursor >= len(self.text):
            return Token.eof(len(self.text))

        chars = []
        start_pos = self.cursor
        cursor = self.cursor
        while True:
            ch = self.text[cursor]
            # Is it a one-character delimiter?
            if token_type := TokenType.try_from_str(ch):
                # If we're at the start of the word, we can return here
                if not len(chars):
                    return Token(type=token_type, value=ch, start_pos=start_pos, end_pos=cursor + 1)
                else:
                    # Finish the current word
                    break

            cursor += 1
            chars.append(ch)

            # Did we reach EOF?
            if cursor >= len(self.text):
                break

        return Token(type=TokenType.Word, value="".join(chars), start_pos=start_pos, end_pos=cursor)

    def next(self) -> Token:
        token = self.peek()
        self.cursor = token.end_pos
        return token


class TestLexer:
    def test(self):
        text = """this, is a {test}.\nfoo"""
        lexer = Lexer(text)
        assert lexer.peek() == Token(TokenType.Word, "this", 0, 4)
        assert lexer.next() == Token(TokenType.Word, "this", 0, 4)
        assert lexer.peek() == Token(TokenType.Comma, ",", 4, 5)
        assert lexer.peek() == Token(TokenType.Comma, ",", 4, 5)
        assert lexer.next() == Token(TokenType.Comma, ",", 4, 5)
        assert lexer.next() == Token(TokenType.Space, " ", 5, 6)

        assert lexer.peek() == Token(TokenType.Word, "is", 6, 8)
        assert lexer.peek() == Token(TokenType.Word, "is", 6, 8)
        assert lexer.next() == Token(TokenType.Word, "is", 6, 8)

        assert lexer.peek() == Token(TokenType.Space, " ", 8, 9)
        assert lexer.next() == Token(TokenType.Space, " ", 8, 9)

        assert lexer.peek() == Token(TokenType.Word, "a", 9, 10)
        assert lexer.next() == Token(TokenType.Word, "a", 9, 10)
        assert lexer.next() == Token(TokenType.Space, " ", 10, 11)
        assert lexer.next() == Token(TokenType.LeftBrace, "{", 11, 12)
        assert lexer.next() == Token(TokenType.Word, "test", 12, 16)
        assert lexer.next() == Token(TokenType.RightBrace, "}", 16, 17)
        assert lexer.next() == Token(TokenType.Word, ".", 17, 18)
        assert lexer.next() == Token(TokenType.Newline, "\n", 18, 19)
        assert lexer.next() == Token(TokenType.Word, "foo", 19, 22)
        assert lexer.peek() == Token(TokenType.EOF, "", 22, 22)
        assert lexer.peek() == Token(TokenType.EOF, "", 22, 22)
        assert lexer.peek() == Token(TokenType.EOF, "", 22, 22)
        assert lexer.next() == Token(TokenType.EOF, "", 22, 22)
        assert lexer.next() == Token(TokenType.EOF, "", 22, 22)
        assert lexer.next() == Token(TokenType.EOF, "", 22, 22)


class CommandType(Enum):
    UpdateSnippet = 0,
    ShowSnippet = 1,

    @classmethod
    def from_str(cls, s: str) -> Self:
        return {
            "update": CommandType.UpdateSnippet,
            "show": CommandType.ShowSnippet,
        }[s]


@dataclass
class Command:
    type: CommandType


@dataclass
class UpdateCommand(Command):
    snippet_name: str
    update_data: str


@dataclass
class ShowCommand(Command):
    snippet_name: str


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

    def read_tokens_until_sequence(self, break_on_sequence: list[TokenType]) -> list[Token]:
        if len(break_on_sequence) < 1:
            raise ValueError("Need at least one type to break on")

        tokens = []
        while True:
            next_tok = self.lexer.peek()
            if next_tok.type == TokenType.EOF:
                break
            tokens.append(self.lexer.next())

            # Look back at the last few tokens and see if it matches the break sequence
            last_few_tokens = tokens[-len(break_on_sequence):]
            if [t.type for t in last_few_tokens] == break_on_sequence:
                # Strip the break tokens
                tokens = tokens[:-len(break_on_sequence)]
                # Rewind the cursor
                self.lexer.cursor = last_few_tokens[0].start_pos
                break
        return tokens

    def read_tokens_until_command_begins(self) -> list[Token]:
        return self.read_tokens_until_sequence(self.BEGIN_COMMAND_SEQ)

    def read_tokens_until_command_ends(self) -> list[Token]:
        return self.read_tokens_until_sequence(self.END_COMMAND_SEQ)

    def expect(self, token_type: TokenType) -> Token:
        next_tok = self.lexer.next()
        if next_tok.type != token_type:
            raise RuntimeError(f"Expected {token_type}, but found {next_tok}")
        return next_tok

    def expect_seq(self, token_types: list[TokenType]) -> list[Token]:
        return [self.expect(tok_type) for tok_type in token_types]

    def parse_command(self) -> Command:
        # Expect two braces
        self.expect_seq(MarkdownParser.BEGIN_COMMAND_SEQ)
        # Command name
        command_name = self.expect(TokenType.Word)
        command_type = CommandType.from_str(command_name.value)
        print(f'Found command name {command_name} of type {command_type}')
        if command_type == CommandType.UpdateSnippet:
            self.expect(TokenType.Space)
            snippet_name = self.expect(TokenType.Word)
            self.expect(TokenType.Newline)
            update_data = self.read_tokens_until_sequence([TokenType.RightBrace, TokenType.RightBrace])
            self.expect_seq(MarkdownParser.END_COMMAND_SEQ)
            print(f'snippet name {snippet_name} {update_data}')

            return UpdateCommand(
                type=CommandType.UpdateSnippet,
                snippet_name=snippet_name.value,
                update_data="".join([t.value for t in update_data])
            )
        elif command_type == CommandType.ShowSnippet:
            self.expect(TokenType.Space)
            snippet_name = self.expect(TokenType.Word)
            self.expect_seq(MarkdownParser.END_COMMAND_SEQ)
            print(f'snippet name {snippet_name}')

            return ShowCommand(
                type=CommandType.ShowSnippet,
                snippet_name=snippet_name.value,
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
            '\n'
            "Now, let's start modeling the DNS header format! Make a new file, "
            '`packet_header_layout.rs`.\n'
        )

        command = parser.parse_command()
        assert command == UpdateCommand(
            type=CommandType.UpdateSnippet,
            snippet_name="main_imports",
            update_data=(
                'use std::net::UdpSocket;\n'
                '\n'
                'use packet_header_layout;\n'
            )
        )


if __name__ == '__main__':
    TestLexer().test()