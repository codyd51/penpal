from dataclasses import dataclass
from enum import Enum, auto
from typing import Self

Cursor = int


class TokenType(Enum):
    EOF = (auto(),)
    Word = (auto(),)
    Comma = (auto(),)
    LeftBrace = (auto(),)
    RightBrace = (auto(),)
    Space = (auto(),)
    Newline = (auto(),)
    Hash = (auto(),)

    @classmethod
    def try_from_str(cls, s: str) -> Self | None:
        mapping = {
            ",": TokenType.Comma,
            "{": TokenType.LeftBrace,
            "}": TokenType.RightBrace,
            " ": TokenType.Space,
            "\n": TokenType.Newline,
            "#": TokenType.Hash,
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
    def __init__(self, text: str) -> None:
        self.text = text
        self.cursor = 0

    def _consume_token(self) -> Token:
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
        token = self._consume_token()
        self.cursor = token.end_pos
        return token

    def peek(self) -> Token:
        return self.peek_n(1)[0]

    def peek_n(self, n: int) -> list[Token]:
        start_cursor = self.cursor
        tokens = [self.next() for _ in range(n)]
        self.cursor = start_cursor
        return tokens

    def peek_next_token_types_match(self, next_types: list[TokenType]) -> bool:
        peek_tokens = self.peek_n(len(next_types))
        return [p.type for p in peek_tokens] == next_types


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
