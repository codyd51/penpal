import shutil
from dataclasses import dataclass
from pathlib import Path

from spiderweb.markdown_parser import (
    MarkdownParser,
    TokenType,
    ShowCommand,
    UpdateCommand,
    ExecuteProgram,
    DefineSnippet,
    Command,
    CommandType,
    EmbedText,
    EmbedSnippet, SnippetProductionRule,
)
from spiderweb.snippet import SnippetRepository, SnippetHeader, SnippetLanguage, Snippet
from spiderweb.env import ROOT_FOLDER
from spiderweb.shell_utils import run_and_check, run_and_capture_output


def render_markdown2():
    repo = SnippetRepository()
    content = ROOT_FOLDER / "content" / "index.md"
    output = ROOT_FOLDER / "generated-site" / "content" / "_index.md"

    text = content.read_text()
    parser = MarkdownParser(text)
    output_text = ""
    while True:
        tokens_before_command = parser.read_tokens_until_command_begins()
        output_text += "".join((t.value for t in tokens_before_command))

        if parser.lexer.peek().type == TokenType.EOF:
            break

        command = parser.parse_command()
        print(f"Got command {command}")
        if isinstance(command, ShowCommand):
            # Treat this as an embedded snippet
            snippet = repo.get(command.snippet_name)
            output_text += f"```{snippet.header.lang.value}\n"
            output_text += repo.render_snippet(snippet)[0].text
            output_text += f"\n```\n"
        elif isinstance(command, UpdateCommand):
            # Update the snippet contents
            snippet = repo.get(command.snippet_name)
            print(f"Updating `{snippet}`...")
            snippet.text = command.update_data
            # Also show it
            output_text += f"_{snippet.header.file}_\n"
            output_text += f"```{snippet.header.lang.value}\n"
            output_text += repo.render_snippet(snippet)[0].text
            output_text += f"```\n"
        elif isinstance(command, ExecuteProgram):
            raise NotImplementedError()
            render_in_memory_program()
        elif isinstance(command, DefineSnippet):
            pass
        else:
            raise NotImplementedError(f"Unhandled command type {type(command)}")

    output.write_text(output_text)


@dataclass
class TextSection:
    text: str


@dataclass
class CommandSection:
    command: Command


DocumentSection = TextSection | CommandSection


def parse_next_command(parser: MarkdownParser) -> (TextSection | None, CommandSection | None):
    text_section = None
    tokens_before_command = parser.read_tokens_until_command_begins()
    # We may immediately start with a command
    if len(tokens_before_command):
        text_before_command = "".join(t.value for t in tokens_before_command)
        text_section = TextSection(text_before_command)

    if parser.lexer.peek().type == TokenType.EOF:
        return text_section, None

    command = parser.parse_command()
    match command:
        case DefineSnippet(type, header, snippet_name, content):
            # We'll need to scan forwards to gather any snippets that are referenced here, but are not defined yet
            # start_cursor = parser.lexer.cursor
            # _, next_command = parse_next_command(parser)
            # parser.lexerr.cursor = start_cursor
            pass
        case _:
            raise NotImplementedError(command)


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


def parse_document() -> list[DocumentSection]:
    repo = SnippetRepository()
    content = ROOT_FOLDER / "content" / "index.md"
    output = ROOT_FOLDER / "generated-site" / "content" / "_index.md"

    text = content.read_text()
    sections = parse_document_text(text)
    # output.write_text(output_text)
    # raise NotImplementedError(sections)
    return sections


SnippetName = str


@dataclass
class InlineSnippet:
    header: SnippetHeader
    name: SnippetName
    production_rules: list[SnippetProductionRule]


def render_snippet(defined_snippets: dict[SnippetName, InlineSnippet], snippet: InlineSnippet, is_nested: bool) -> str:
    out = str()
    if not is_nested:
        # First, open a code block and define the language
        out += f"\n```{snippet.header.lang.value}\n"

    for production_rule in snippet.production_rules:
        match production_rule:
            case EmbedText(text):
                out += text
            case EmbedSnippet(inner_snippet_name):
                inner_snippet = defined_snippets[inner_snippet_name]
                out += render_snippet(defined_snippets, inner_snippet, True)

    if not is_nested:
        # Close the code block
        out += "```\n"

    return out


def render_sections(sections: list[DocumentSection]) -> str:
    out = str()

    defined_snippets: dict[SnippetName, InlineSnippet] = dict()
    for section in sections:
        match section:
            case TextSection(text):
                out += text
            case CommandSection(command):
                match command:
                    case ShowCommand(_, snippet_name):
                        snippet = defined_snippets[snippet_name]
                        out += render_snippet(defined_snippets, snippet, False)

                    case DefineSnippet(_, header, snippet_name, production_rules):
                        # Nothing to output for definitions
                        # But track it in our defined snippets
                        defined_snippets[snippet_name] = InlineSnippet(header, snippet_name, production_rules)
                        print(f'Defined and tracked snippet {snippet_name}')
                    case command_type:
                        raise NotImplementedError(f"Don't know how to render a {command_type}")
    return out


def render_markdown(text: str) -> list[DocumentSection]:
    parser = MarkdownParser(text)
    output_text = ""
    while True:
        tokens_before_command = parser.read_tokens_until_command_begins()
        output_text += "".join((t.value for t in tokens_before_command))

        if parser.lexer.peek().type == TokenType.EOF:
            break

        command = parser.parse_command()
        print(f"Got command {command}")
        if isinstance(command, ShowCommand):
            # Treat this as an embedded snippet
            snippet = repo.get(command.snippet_name)
            output_text += f"```{snippet.header.lang.value}\n"
            output_text += repo.render_snippet(snippet)[0].text
            output_text += f"\n```\n"
        elif isinstance(command, UpdateCommand):
            # Update the snippet contents
            snippet = repo.get(command.snippet_name)
            print(f"Updating `{snippet}`...")
            snippet.text = command.update_data
            # Also show it
            output_text += f"_{snippet.header.file}_\n"
            output_text += f"```{snippet.header.lang.value}\n"
            output_text += repo.render_snippet(snippet)[0].text
            output_text += f"```\n"
        elif isinstance(command, ExecuteProgram):
            raise NotImplementedError()
            render_in_memory_program()
        elif isinstance(command, DefineSnippet):
            # We'll need to scan forwards to gather any snippets that are referenced here, but are not defined yet
            start_cursor = parser.lexer.cursor

            pass
        else:
            raise NotImplementedError(f"Unhandled command type {type(command)}")

    output.write_text(output_text)


def render_in_memory_program():
    repo = SnippetRepository()


def render_program(name: str) -> Path:
    repo = SnippetRepository()
    snippet = repo.get(name)
    program_name = snippet.generated_program_name
    if not snippet.header.is_executable:
        raise ValueError(f"Can only render programs for executable snippets, but {name} is not executable")
    generated_programs_dir = ROOT_FOLDER / "generated-programs"
    program_dir = generated_programs_dir / program_name

    print(f"Deleting {program_dir}...")
    shutil.rmtree(program_dir.as_posix())

    print(f"Rendering {program_name}")
    folder_path = generated_programs_dir / name
    run_and_check(["cargo", "new", name], cwd=generated_programs_dir)
    run_and_check(["cargo", "build"], cwd=folder_path)

    render_descriptions = repo.render_snippet(snippet, strip_presentation_commands=True)
    for desc in render_descriptions:
        path = folder_path / desc.file
        path.write_text(desc.text)
    return folder_path


def render_programs() -> list[Path]:
    repo = SnippetRepository()
    executable_snippets = [s for s in repo.snippets.values() if s.header.is_executable]
    generated_programs = []
    for snippet in executable_snippets:
        generated_programs.append(render_program(snippet.name))
    return generated_programs


def test_render_snippets():
    repo = SnippetRepository()
    print(repo.render_snippet(repo.get("listing1")))
    print(repo.render_snippet(repo.get("listing2")))


def test_executables():
    generated_program_paths = render_programs()
    for generated_program_path in generated_program_paths:
        return_code, output = run_and_capture_output(["cargo", "run"], cwd=generated_program_path)
        print(return_code, output)


def test_executable(name: str):
    generated_program_path = render_program(name)
    return_code, output = run_and_capture_output(["cargo", "run"], cwd=generated_program_path)
    print(return_code, output)


class TestRenderer:
    def test_parse_sections(self):
        src = """+++
title = "DNS Resolver: Receiving Packets"
date = "2023-06-14T22:20:08+01:00"

tags = []
+++

Let's get started.

```shell
$ cargo new dns_resolver --bin
$ cd dns_resolver
```

If you strip away our DNS resolver to the bare bones, its core runloop will be composed of a _request_ and a response_. Our general approach will be:

1. _Wait_ for a DNS request to arrive.
2. _Parse_ the request.
3. _Perform_ the lookup.
4. _Send_ the response.

To get us started, let's _wait_ for DNS queries to come in.

{{define main_runloop
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

{{define main_imports
lang: rust
###
use std::net::UdpSocket;
}}

{{define main_runloop_bind_to_socket
lang: rust
###
    let socket = UdpSocket::bind("127.0.0.1:53")
        .expect("Failed to bind to our local DNS port");
}}

{{show main_runloop}}
"""
        sections = parse_document_text(src)
        assert sections == [
            TextSection(
                (
                    "+++\n"
                    'title = "DNS Resolver: Receiving Packets"\n'
                    'date = "2023-06-14T22:20:08+01:00"\n'
                    "\n"
                    "tags = []\n"
                    "+++\n"
                    "\n"
                    "Let's get started.\n"
                    "\n"
                    "```shell\n"
                    "$ cargo new dns_resolver --bin\n"
                    "$ cd dns_resolver\n"
                    "```\n"
                    "\n"
                    "If you strip away our DNS resolver to the bare bones, its core runloop will be composed of a "
                    "_request_ and a response_. Our general approach will be:\n"
                    "\n"
                    "1. _Wait_ for a DNS request to arrive.\n"
                    "2. _Parse_ the request.\n"
                    "3. _Perform_ the lookup.\n"
                    "4. _Send_ the response.\n"
                    "\n"
                    "To get us started, let's _wait_ for DNS queries to come in.\n"
                    "\n"
                )
            ),
            CommandSection(
                command=DefineSnippet(
                    type=CommandType.DefineSnippet,
                    header=SnippetHeader(
                        lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file="src/main.rs"
                    ),
                    snippet_name="main_runloop",
                    content=[
                        EmbedSnippet(snippet_name="main_imports"),
                        EmbedText(
                            text="\n" "\n" "const " "MAX_DNS_UDP_PACKET_SIZE: " "usize = 512;\n" "\n" "fn main() {\n"
                        ),
                        EmbedSnippet(snippet_name="main_runloop_bind_to_socket"),
                        EmbedText(
                            text="\n"
                                 "    let mut receive_packet_buf = [0; MAX_DNS_UDP_PACKET_SIZE];\n"
                                 '    println!("Awaiting incoming packets...");\n'
                                 "    loop {\n"
                                 "        let (byte_count_received, sender_addr) = socket\n"
                                 "            .recv_from(&mut receive_packet_buf)\n"
                                 '            .expect("Failed to read from the socket");\n'
                                 "\n"
                                 "        println!(\"We've received a DNS query of {byte_count_received} bytes from "
                                 '{sender_addr:?}");\n'
                                 "    }\n"
                                 "}\n"
                        ),
                    ],
                )
            ),
            TextSection(text="\n\n"),
            CommandSection(
                command=DefineSnippet(
                    type=CommandType.DefineSnippet,
                    header=SnippetHeader(lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file=None),
                    snippet_name="main_imports",
                    content=[EmbedText(text="use " "std::net::UdpSocket;\n")],
                )
            ),
            TextSection(text="\n\n"),
            CommandSection(
                command=DefineSnippet(
                    type=CommandType.DefineSnippet,
                    header=SnippetHeader(lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file=None),
                    snippet_name="main_runloop_bind_to_socket",
                    content=[
                        EmbedText(
                            text="    let socket "
                                 "= "
                                 'UdpSocket::bind("127.0.0.1:53")\n'
                                 "        "
                                 '.expect("Failed '
                                 "to bind to our "
                                 "local DNS "
                                 'port");\n'
                        )
                    ],
                )
            ),
            TextSection(text="\n\n"),
            CommandSection(command=ShowCommand(type=CommandType.ShowSnippet, snippet_name="main_runloop")),
            TextSection(text="\n"),
        ]

    def test_render_snippet(self):
        sections = [
            CommandSection(
                command=DefineSnippet(
                    type=CommandType.DefineSnippet,
                    header=SnippetHeader(
                        lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file="src/main.rs"
                    ),
                    snippet_name="main_runloop",
                    content=[
                        EmbedSnippet(snippet_name="main_imports"),
                        EmbedText(
                            text="\n\nconst MAX_DNS_UDP_PACKET_SIZE: usize = 512;\n\nfn main() {\n"
                        ),
                        EmbedSnippet(snippet_name="main_runloop_bind_to_socket"),
                        EmbedText(
                            text=(
                                "\n"
                                "    let mut receive_packet_buf = [0; MAX_DNS_UDP_PACKET_SIZE];\n"
                                '    println!("Awaiting incoming packets...");\n'
                                "    loop {\n"
                                "        let (byte_count_received, sender_addr) = socket\n"
                                "            .recv_from(&mut receive_packet_buf)\n"
                                '            .expect("Failed to read from the socket");\n'
                                "\n"
                                "        println!(\"We've received a DNS query of {byte_count_received} bytes from "
                                '{sender_addr:?}");\n'
                                "    }\n"
                                "}\n"
                            )
                        ),
                    ],
                )
            ),
            TextSection(text="\n\n"),
            CommandSection(
                command=DefineSnippet(
                    type=CommandType.DefineSnippet,
                    header=SnippetHeader(lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file=None),
                    snippet_name="main_imports",
                    content=[EmbedText(text="use " "std::net::UdpSocket;\n")],
                )
            ),
            TextSection(text="\n\n"),
            CommandSection(
                command=DefineSnippet(
                    type=CommandType.DefineSnippet,
                    header=SnippetHeader(lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file=None),
                    snippet_name="main_runloop_bind_to_socket",
                    content=[
                        EmbedText(
                            text="    let socket "
                                 "= "
                                 'UdpSocket::bind("127.0.0.1:53")\n'
                                 "        "
                                 '.expect("Failed '
                                 "to bind to our "
                                 "local DNS "
                                 'port");\n'
                        )
                    ],
                )
            ),
            TextSection(text="\n\n"),
            CommandSection(command=ShowCommand(type=CommandType.ShowSnippet, snippet_name="main_runloop")),
            TextSection(text="\n"),
        ]

        assert render_sections(sections) == (
            '\n'
            '\n'
            '\n'
            '\n'
            '\n'
            '\n'
            '\n'
            '```rust\n'
            'use std::net::UdpSocket;\n'
            '\n'
            '\n'
            'const MAX_DNS_UDP_PACKET_SIZE: usize = 512;\n'
            '\n'
            'fn main() {\n'
            '    let socket = UdpSocket::bind("127.0.0.1:53")\n'
            '        .expect("Failed to bind to our local DNS port");\n'
            '\n'
            '    let mut receive_packet_buf = [0; MAX_DNS_UDP_PACKET_SIZE];\n'
            '    println!("Awaiting incoming packets...");\n'
            '    loop {\n'
            '        let (byte_count_received, sender_addr) = socket\n'
            '            .recv_from(&mut receive_packet_buf)\n'
            '            .expect("Failed to read from the socket");\n'
            '\n'
            '        println!("We\'ve received a DNS query of {byte_count_received} bytes '
            'from {sender_addr:?}");\n'
            '    }\n'
            '}\n'
            '```\n'
            '\n')
