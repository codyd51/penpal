import io
import os
import selectors
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Self, Optional

import yaml
from pydantic import BaseModel, Field

_ROOT_FOLDER = Path(__file__).parents[1]


class SnippetLanguage(Enum):
    SHELL = "shell"
    RUST = "rust"


class SnippetHeader(BaseModel):
    # Should this be a 'complete' program that can be run and tested?
    # is_executable: bool
    is_executable: bool = Field(default=False, alias="executable")
    lang: SnippetLanguage


@dataclass
class Snippet:
    path: Path
    header: SnippetHeader
    text: str

    @classmethod
    def from_file(cls, path: Path) -> Self:
        file_content = path.read_text()
        # Extract the YAML-formatted header from file
        marker = "###"
        metadata_split = file_content.split(marker)
        if len(metadata_split) != 2:
            raise ValueError(f'Could not split the metadata from the markdown; looked for "{marker}": {file_content}')

        raw_header = yaml.load(metadata_split[0], Loader=yaml.SafeLoader)
        header = SnippetHeader.parse_obj(raw_header)

        return cls(
            path=path,
            header=header,
            # Trim the initial newline
            text=metadata_split[1][1:],
        )

    @property
    def name(self) -> str:
        return self.path.name


class SnippetRepository:
    def __init__(self):
        chapter_1_snippets = _ROOT_FOLDER / "chapter_1" / "snippets"
        snippets = {}
        for file in chapter_1_snippets.iterdir():
            snippets[file.name] = Snippet.from_file(file)
        self.snippets = snippets

    def get(self, id: str) -> Snippet:
        return self.snippets[f"{id}.md"]

    def render_snippet(self, snippet: Snippet, strip_presentation_commands=False) -> str:
        print(f'render_snippet({snippet})')
        out = ""
        breaks = snippet.text.split("{{")
        for section in breaks:
            if "}}" in section:
                splits = section.split("}}")

                embedded_command_or_snippet_name = splits[0]

                # Some names denote special commands
                if embedded_command_or_snippet_name == "highlight":
                    if not strip_presentation_commands:
                        # Insert some styling tags
                        out += "{{< rawhtml >}}"
                        out += '<div style="background-color: #c2c439">'
                elif embedded_command_or_snippet_name == "/highlight":
                    if not strip_presentation_commands:
                        # End the styling tag
                        out += "</div>"
                        out += "{{< /rawhtml >}}"
                else:
                    # Treat this as an embedded snippet
                    embedded_snippet = self.get(embedded_command_or_snippet_name)
                    out += self.render_snippet(embedded_snippet)

                # Output whatever comes next
                section = splits[1]

            # Just text prior
            out += section
        return out


def test_render_snippets():
    repo = SnippetRepository()
    print(repo.render_snippet(repo.get("listing1")))
    print(repo.render_snippet(repo.get("listing2")))


def render_markdown():
    repo = SnippetRepository()
    content = _ROOT_FOLDER / "content" / "index.md"
    output = _ROOT_FOLDER / "generated-site" / "content" / "_index.md"

    text = content.read_text()
    parts = text.split("{{")
    out = ""
    for part in parts:
        if "}}" in part:
            splits = part.split("}}")
            snippet_name = splits[0]
            # Treat this as an embedded snippet
            embedded_snippet = repo.get(snippet_name)
            out += f"```{embedded_snippet.header.lang.value}\n"
            out += repo.render_snippet(embedded_snippet)
            out += f"```"

            # Output whatever comes next
            part = splits[1]

        # Output the non-templated text
        out += part

    output.write_text(out)


def run_and_check(cmd_list: list[str], cwd: Path = None, env_additions: Optional[dict[str, str]] = None) -> None:
    if cwd:
        print(f"{cwd}: {' '.join(cmd_list)}")
    else:
        print(f"{' '.join(cmd_list)}")
    env = os.environ.copy()
    if env_additions:
        for k, v in env_additions.items():
            env[k] = v
    env["PATH"] = f"/opt/homebrew/bin:{env['PATH']}"

    status = subprocess.run(cmd_list, cwd=cwd.as_posix() if cwd else None, env=env)
    if status.returncode != 0:
        raise RuntimeError(f'Running "{" ".join(cmd_list)}" failed with exit code {status.returncode}')


def run_and_capture_output(cmd_list: list[str], cwd: Path = None) -> (int, str):
    """Beware this will strip ASCII escape codes, so you'll lose colors."""
    # https://gist.github.com/nawatts/e2cdca610463200c12eac2a14efc0bfb
    # Start subprocess
    # bufsize = 1 means output is line buffered
    # universal_newlines = True is required for line buffering
    process = subprocess.Popen(
        cmd_list,
        cwd=cwd.as_posix() if cwd else None,
        bufsize=1,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )

    # Create callback function for process output
    buf = io.StringIO()

    def handle_output(stream, mask):
        # Because the process' output is line buffered, there's only ever one
        # line to read when this function is called
        line = stream.readline()
        buf.write(line)
        sys.stdout.write(line)

    # Register callback for an "available for read" event from subprocess' stdout stream
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, handle_output)

    # Loop until subprocess is terminated
    while process.poll() is None:
        # Wait for events and handle them with their registered callbacks
        events = selector.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)

    # Get process return code
    return_code = process.wait()
    selector.close()

    # Store buffered output
    output = buf.getvalue()
    buf.close()

    return return_code, output


def run_and_capture_output_and_check(cmd_list: list[str], cwd: Path = None) -> (int, str):
    return_code, output = run_and_capture_output(cmd_list, cwd=cwd)

    if return_code != 0:
        raise RuntimeError(f'Running "{" ".join(cmd_list)}" failed with exit code {return_code}')

    return return_code, output


def test_executables():
    repo = SnippetRepository()
    executable_snippets = [s for s in repo.snippets.values() if s.header.is_executable]
    generated_programs_dir = _ROOT_FOLDER / "generated-programs"

    for program_dir in generated_programs_dir.iterdir():
        print(f'Deleting {program_dir}...')
        shutil.rmtree(program_dir.as_posix())

    for executable_snippet in executable_snippets:
        print(f'Rendering {executable_snippet.name}')
        folder_name = executable_snippet.name.split(".md")[0]
        folder_path = generated_programs_dir / folder_name
        run_and_check(["cargo", "new", folder_name], cwd=generated_programs_dir)
        run_and_check(["cargo", "build"], cwd=folder_path)

        if True:
            main_file = folder_path / "src" / "main.rs"
            main_file.write_text(repo.render_snippet(executable_snippet, strip_presentation_commands=True))
            return_code, output = run_and_capture_output(["cargo", "run"], cwd=folder_path)
            print(return_code, output)


def main():
    test_executables()


if __name__ == '__main__':
    main()
