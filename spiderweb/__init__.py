import shutil
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Self, Optional

import yaml
from pydantic import BaseModel, Field
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from spiderweb.shell_utils import run_and_check, run_and_capture_output

_ROOT_FOLDER = Path(__file__).parents[1]
_CHAPTER_1_ROOT = Path(__file__).parents[1] / "chapter_1"
_CONTENT_ROOT = Path(__file__).parents[1] / "content"


class SnippetLanguage(Enum):
    SHELL = "shell"
    RUST = "rust"


class SnippetHeader(BaseModel):
    lang: SnippetLanguage
    # Should this be a 'complete' program that can be run and tested?
    is_executable: bool = Field(default=False, alias="executable")
    # This snippet 'depends' on another snippet to form a complete program
    dependencies: list[str] = Field(default=[], alias="depends-on")
    # The path within the crate that this snippet should be rendered to
    file: Optional[str] = Field(default=None)

    def __str__(self) -> str:
        return f'Header(lang={self.lang.value}, is_executable={self.is_executable}, dependencies={self.dependencies}, file={self.file})'


@dataclass
class Snippet:
    path: Path
    header: SnippetHeader
    text: str

    def __repr__(self) -> str:
        return f'Snippet(path={self.path.relative_to(_ROOT_FOLDER)}, header={self.header})'

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

    @property
    def generated_program_name(self) -> str:
        if not self.header.is_executable:
            raise ValueError(f"Can only be used for executable snippets")
        return self.path.name.split(".md")[0]


@dataclass
class SnippetRenderDescription:
    text: str
    file: Optional[Path]


class SnippetRepository:
    def __init__(self):
        chapter_1_snippets = _CHAPTER_1_ROOT / "snippets"
        snippets = {}
        for file in chapter_1_snippets.iterdir():
            snippets[file.name] = Snippet.from_file(file)
        self.snippets = snippets

    def get(self, id: str) -> Snippet:
        return self.snippets[f"{id}.md"]

    def render_snippet(self, snippet: Snippet, strip_presentation_commands=False) -> list[SnippetRenderDescription]:
        render_descriptions = []
        # First, render any dependencies of this snippet
        for dep in snippet.header.dependencies:
            dep_snippet = self.get(dep)
            render_descriptions.extend(self.render_snippet(dep_snippet, strip_presentation_commands=strip_presentation_commands))

        print(f'render_snippet({snippet})')
        breaks = snippet.text.split("{{")
        this_snippet_text = ""
        for section in breaks:
            if "}}" in section:
                splits = section.split("}}")

                embedded_command_or_snippet_name = splits[0]

                # Some names denote special commands
                if embedded_command_or_snippet_name == "highlight":
                    if not strip_presentation_commands:
                        # Insert some styling tags
                        this_snippet_text += "{{< rawhtml >}}"
                        this_snippet_text += '<div style="background-color: #4a4a00">'
                elif embedded_command_or_snippet_name == "/highlight":
                    if not strip_presentation_commands:
                        # End the styling tag
                        this_snippet_text += "</div>"
                        this_snippet_text += "{{< /rawhtml >}}"
                else:
                    # Treat this as an embedded snippet
                    embedded_snippet_render_description = self.get(embedded_command_or_snippet_name)
                    # Ensure embedded snippets don't specify an output path
                    if embedded_snippet_render_description.header.file:
                        raise ValueError(f"Did not expect an embedded snippet to want to be rendered to a specific path, but specified {embedded_snippet_render_description.header.file}")
                    this_snippet_text += self.render_snippet(embedded_snippet_render_description)[0].text

                # Output whatever comes next
                section = splits[1]

            # Just text prior
            this_snippet_text += section
        render_descriptions.append(
            SnippetRenderDescription(text=this_snippet_text, file=snippet.header.file)
        )
        return render_descriptions


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
            out += repo.render_snippet(embedded_snippet)[0].text
            out += f"```"

            # Output whatever comes next
            part = splits[1]

        # Output the non-templated text
        out += part

    output.write_text(out)


def render_program(name: str) -> Path:
    repo = SnippetRepository()
    snippet = repo.get(name)
    program_name = snippet.generated_program_name
    if not snippet.header.is_executable:
        raise ValueError(f"Can only render programs for executable snippets, but {name} is not executable")
    generated_programs_dir = _ROOT_FOLDER / "generated-programs"
    program_dir = generated_programs_dir / program_name

    print(f'Deleting {program_dir}...')
    shutil.rmtree(program_dir.as_posix())

    print(f'Rendering {program_name}')
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

    if False:
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

            render_descriptions = repo.render_snippet(executable_snippet, strip_presentation_commands=True)
            print(render_descriptions)
            for desc in render_descriptions:
                path = folder_path / desc.file
                path.write_text(desc.text)
            generated_programs.append(folder_path)

    return generated_programs


def test_executables():
    generated_program_paths = render_programs()
    for generated_program_path in generated_program_paths:
        return_code, output = run_and_capture_output(["cargo", "run"], cwd=generated_program_path)
        print(return_code, output)


def test_executable(name: str):
    generated_program_path = render_program(name)
    return_code, output = run_and_capture_output(["cargo", "run"], cwd=generated_program_path)
    print(return_code, output)


class EventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        # print(event)
        print(f'Rendering markdown in response to {event}...')
        try:
            render_markdown()
            render_programs()
        except Exception as e:
            print(f'Failed to render to markdown: {e}')
            raise


def main():
    #render_programs()
    test_executable("listing3")
    #render_markdown()
    #test_executables()
    event_handler = EventHandler()
    observer = Observer()
    observer.schedule(event_handler, _CONTENT_ROOT.as_posix(), recursive=True)
    observer.schedule(event_handler, _CHAPTER_1_ROOT.as_posix(), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == '__main__':
    main()
