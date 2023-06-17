import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from penpal.document_parser import DocumentSection, TextSection, CommandSection, parse_document_text
from penpal.markdown_parser import (
    ShowCommand,
    UpdateCommand,
    DefineSnippet,
    CommandType,
    EmbedText,
    EmbedSnippet,
    SnippetProductionRule,
)
from penpal.snippet import SnippetRepository, SnippetHeader, SnippetLanguage
from penpal.env import ROOT_FOLDER
from penpal.shell_utils import run_and_check, run_and_capture_output


SnippetName = str
ProductionRuleIndex = int
StringIndex = int


@dataclass
class InlineSnippet:
    header: SnippetHeader
    name: SnippetName
    production_rules: list[SnippetProductionRule]


class DocumentRenderer:
    def __init__(self, document_sections: DocumentSection) -> None:
        self.document_sections = document_sections
        self.defined_snippets: dict[SnippetName, InlineSnippet] = dict()
        self.rendered_snippets: list[InlineSnippet] = list()

    @staticmethod
    def render_text_section(text_section: TextSection) -> str:
        return text_section.text

    def render_command__show(self, command: ShowCommand) -> str:
        out = str()
        snippet_name = command.snippet_name
        print(f"ShowCommand({snippet_name})")
        snippet = self.defined_snippets[snippet_name]
        rendered_snippet_text, _ = render_snippet(self.defined_snippets, snippet, False, None)
        file_name = (
                snippet.header.file
                or find_parent_snippet(self.defined_snippets, self.rendered_snippets, snippet_name).header.file
        )
        out += f"_{file_name}_"
        out += rendered_snippet_text
        print(rendered_snippet_text)
        self.rendered_snippets.append(snippet)
        return out

    def render_command__define(self, command: DefineSnippet) -> str:
        # Nothing to output for definitions
        # But track it in our defined snippets
        snippet_name = command.snippet_name
        self.defined_snippets[snippet_name] = InlineSnippet(command.header, snippet_name, command.content)
        print(f"Defined and tracked snippet {snippet_name}")
        return str()

    def render_command__update(self, command: UpdateCommand) -> str:
        out = str()
        snippet_name = command.snippet_name
        print(f"Updating {snippet_name}")
        existing_snippet = self.defined_snippets[snippet_name]
        # Currently snippets can just be updated with new text, and cannot be updated to include new
        # production rules
        # It would be straightforward to support the former, though.
        existing_snippet.production_rules = [EmbedText(command.update_data)]

        # Now, render the updated snippet
        # This snippet may not exist at the top level, and may only ever appear as a sub-snippet within
        # another snippet.
        # Therefore, we need to iterate the snippets to find the last time this snippet was used, to
        # be able to show where the update happens in the context of the source code.
        parent_snippet = find_parent_snippet(self.defined_snippets, self.rendered_snippets, snippet_name)
        # Replace the specified rule
        production_rule_idx = find_embedded_snippet_in_production_rules(parent_snippet, snippet_name)
        # print(f'Replacing {snippet_name} at index {production_rule_idx} in {parent_snippet.name}')
        # parent_snippet.production_rules[production_rule_idx].text = updated_content

        # Display the update
        rendered_snippet_text, rule_idx_to_start_idxs = render_snippet(
            self.defined_snippets, parent_snippet, False, production_rule_idx
        )
        highlight_start = rule_idx_to_start_idxs[production_rule_idx]
        print(f"Found start of highlight at {highlight_start}")
        highlight_end = (
            rule_idx_to_start_idxs[production_rule_idx + 1]
            if production_rule_idx < (len(parent_snippet.production_rules) - 1)
            else len(rendered_snippet_text)
        )
        newline_counter = 0
        for i, ch in enumerate(reversed(rendered_snippet_text[:highlight_start])):
            if ch == "\n":
                newline_counter += 1
            if newline_counter == 2:
                context_start = highlight_start - i
                break
        newline_counter = 0
        for i, ch in enumerate(rendered_snippet_text[highlight_end:]):
            if ch == "\n":
                newline_counter += 1
            if newline_counter == 3:
                context_end = highlight_end + i
                break

        file_name = existing_snippet.header.file or parent_snippet.header.file
        out += f"_{file_name}_\n"
        out += f"```rust\n"
        out += rendered_snippet_text[context_start:context_end]
        out += f"\n```\n"
        self.rendered_snippets.append(parent_snippet)

        return out

    def render_command_section(self, command_section: CommandSection) -> str:
        out = str()
        command = command_section.command
        match command:
            case ShowCommand(_):
                out += self.render_command__show(command)

            case DefineSnippet(_):
                out += self.render_command__define(command)

            case UpdateCommand(_):
                out += self.render_command__update(command)

            case command_type:
                raise NotImplementedError(f"Don't know how to render a {command_type}")
        return out

    def render(self) -> str:
        out = str()
        for section in self.document_sections:
            match section:
                case TextSection():
                    out += self.render_text_section(section)
                case CommandSection():
                    out += self.render_command_section(section)

        return out


def render_snippet(
    defined_snippets: dict[SnippetName, InlineSnippet],
    snippet: InlineSnippet,
    is_nested: bool,
    highlight_snippet_idx: int | None,
) -> (str, dict[ProductionRuleIndex, StringIndex]):
    out = str()
    rules_to_start_idx = dict()
    if not is_nested:
        # First, open a code block and define the language
        out += f"\n```{snippet.header.lang.value}\n"

    for i, production_rule in enumerate(snippet.production_rules):
        rules_to_start_idx[i] = len(out)

        should_highlight_this_production = i == highlight_snippet_idx
        if should_highlight_this_production:
            # Insert some styling tags
            out += "{{< rawhtml >}}"
            out += '<div style="background-color: #4a4a00">'

        match production_rule:
            case EmbedText(text):
                out += text
            case EmbedSnippet(inner_snippet_name):
                inner_snippet = defined_snippets[inner_snippet_name]
                rendered_subsnippet, _ = render_snippet(defined_snippets, inner_snippet, True, None)
                out += rendered_subsnippet

        if should_highlight_this_production:
            # End the styling tag
            out += "</div>"
            out += "{{< /rawhtml >}}"

    if not is_nested:
        # Close the code block
        out += "\n```\n"

    return out, rules_to_start_idx


def find_parent_snippet(
    defined_snippets: dict[SnippetName, InlineSnippet],
    recently_displayed_snippets: list[InlineSnippet],
    this_snippet_name: SnippetName,
) -> InlineSnippet:
    # Start from the back, so we can reach the most-up-to-date snippets first
    for recently_displayed_snippet in reversed(recently_displayed_snippets):
        for production_rule in recently_displayed_snippet.production_rules:
            if isinstance(production_rule, EmbedSnippet):
                if production_rule.snippet_name == this_snippet_name:
                    return recently_displayed_snippet

    # Now try searching in non-displayed snippets
    for _, parent_snippet in defined_snippets.items():
        for production_rule in parent_snippet.production_rules:
            if isinstance(production_rule, EmbedSnippet):
                if production_rule.snippet_name == this_snippet_name:
                    return parent_snippet

    raise ValueError(f"Failed to find a displayed parent for {this_snippet_name}")


def find_embedded_snippet_in_production_rules(parent_snippet: InlineSnippet, embedded_snippet_name: SnippetName) -> int:
    for i, production_rule in enumerate(parent_snippet.production_rules):
        if isinstance(production_rule, EmbedSnippet) and production_rule.snippet_name == embedded_snippet_name:
            return i
    raise ValueError(f"Failed to find an embedding for {embedded_snippet_name} within {parent_snippet.name}")


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


def _test_render_snippets():
    repo = SnippetRepository()
    print(repo.render_snippet(repo.get("listing1")))
    print(repo.render_snippet(repo.get("listing2")))


def _test_executables():
    generated_program_paths = render_programs()
    for generated_program_path in generated_program_paths:
        return_code, output = run_and_capture_output(["cargo", "run"], cwd=generated_program_path)
        print(return_code, output)


def _test_executable(name: str):
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
                            "}"
                        ),
                    ],
                )
            ),
            TextSection(text="\n\n"),
            CommandSection(
                command=DefineSnippet(
                    header=SnippetHeader(lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file=None),
                    snippet_name="main_imports",
                    content=[EmbedText(text="use std::net::UdpSocket;")],
                )
            ),
            TextSection(text="\n\n"),
            CommandSection(
                command=DefineSnippet(
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
                            'port");'
                        )
                    ],
                )
            ),
            TextSection(text="\n\n"),
            CommandSection(command=ShowCommand(snippet_name="main_runloop")),
            TextSection(text="\n"),
        ]

    def test_render_snippet(self):
        sections = [
            CommandSection(
                command=DefineSnippet(
                    header=SnippetHeader(
                        lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file="src/main.rs"
                    ),
                    snippet_name="main_runloop",
                    content=[
                        EmbedSnippet(snippet_name="main_imports"),
                        EmbedText(text="\n\nconst MAX_DNS_UDP_PACKET_SIZE: usize = 512;\n\nfn main() {\n"),
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
                    header=SnippetHeader(lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file=None),
                    snippet_name="main_imports",
                    content=[EmbedText(text="use std::net::UdpSocket;\n")],
                )
            ),
            TextSection(text="\n\n"),
            CommandSection(
                command=DefineSnippet(
                    header=SnippetHeader(lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file=None),
                    snippet_name="main_runloop_bind_to_socket",
                    content=[
                        EmbedText(
                            text=(
                                '    let socket = UdpSocket::bind("127.0.0.1:53")\n'
                                '        .expect("Failed to bind to our local DNS port");\n'
                            )
                        )
                    ],
                )
            ),
            TextSection(text="\n\n"),
            CommandSection(command=ShowCommand(snippet_name="main_runloop")),
            TextSection(text="\n"),
        ]

        renderer = DocumentRenderer(sections)
        assert renderer.render() == (
            "\n"
            "\n"
            "\n"
            "\n"
            "\n"
            "\n"
            "_src/main.rs_\n"
            "```rust\n"
            "use std::net::UdpSocket;\n"
            "\n"
            "\n"
            "const MAX_DNS_UDP_PACKET_SIZE: usize = 512;\n"
            "\n"
            "fn main() {\n"
            '    let socket = UdpSocket::bind("127.0.0.1:53")\n'
            '        .expect("Failed to bind to our local DNS port");\n'
            "\n"
            "    let mut receive_packet_buf = [0; MAX_DNS_UDP_PACKET_SIZE];\n"
            '    println!("Awaiting incoming packets...");\n'
            "    loop {\n"
            "        let (byte_count_received, sender_addr) = socket\n"
            "            .recv_from(&mut receive_packet_buf)\n"
            '            .expect("Failed to read from the socket");\n'
            "\n"
            "        println!(\"We've received a DNS query of {byte_count_received} bytes "
            'from {sender_addr:?}");\n'
            "    }\n"
            "}\n\n"
            "```\n"
            "\n"
        )

    @pytest.mark.xfail(True, reason="Not implemented yet")
    def test_update_top_level_snippet(self):
        raise NotImplementedError()

    def test_update_second_level_snippet(self):
        sections = [
            CommandSection(
                command=DefineSnippet(
                    header=SnippetHeader(
                        lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file="src/main.rs"
                    ),
                    snippet_name="top_level_snippet",
                    content=[
                        EmbedText("Top-level snippet text.\n"),
                        EmbedSnippet("second_level_snippet"),
                    ],
                )
            ),
            CommandSection(
                command=DefineSnippet(
                    header=SnippetHeader(lang=SnippetLanguage.RUST, is_executable=False, dependencies=[], file=None),
                    snippet_name="second_level_snippet",
                    content=[EmbedText(text="Second-level snippet text.\n")],
                )
            ),
            CommandSection(command=ShowCommand(snippet_name="top_level_snippet")),
            CommandSection(
                command=UpdateCommand(
                    snippet_name="second_level_snippet",
                    update_data="Updated second-level snippet text!",
                )
            ),
        ]

        renderer = DocumentRenderer(sections)
        assert renderer.render() == (
            "\n"
            "```rust\n"
            "Top-level snippet text.\n"
            "Second-level snippet text.\n"
            "```\n"
            "\n"
            "```rust\n"
            "Top-level snippet text.\n"
            '{{< rawhtml >}}<div style="background-color: #4a4a00">Updated second-level '
            "snippet text!</div>{{< /rawhtml >}}```\n"
        )
