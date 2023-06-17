from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Self

import yaml
from pydantic import BaseModel, Field

from penpal import ROOT_FOLDER, CHAPTER_1_ROOT


class SnippetLanguage(Enum):
    SHELL = "shell"
    RUST = "rust"
    TOML = "toml"


class SnippetHeader(BaseModel):
    lang: SnippetLanguage
    # Should this be a 'complete' program that can be run and tested?
    is_executable: bool = Field(default=False, alias="executable")
    # This snippet 'depends' on another snippet to form a complete program
    dependencies: list[str] = Field(default=[], alias="depends-on")
    # The path within the crate that this snippet should be rendered to
    file: Optional[str] = Field(default=None)

    def __str__(self) -> str:
        return f"Header(lang={self.lang.value}, is_executable={self.is_executable}, dependencies={self.dependencies}, file={self.file})"


@dataclass
class Snippet:
    path: Path
    header: SnippetHeader
    text: str

    def __repr__(self) -> str:
        return f"Snippet(path={self.path.relative_to(ROOT_FOLDER)}, header={self.header})"

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
        chapter_1_snippets = CHAPTER_1_ROOT / "snippets"
        snippets = {}
        for file in chapter_1_snippets.iterdir():
            print(f"parsing {file.as_posix()}")
            snippets[file.name] = Snippet.from_file(file)
        self.snippets = snippets

    def get(self, id: str) -> Snippet:
        return self.snippets[f"{id}.md"]

    def render_snippet(self, snippet: Snippet, strip_presentation_commands=False) -> list[SnippetRenderDescription]:
        render_descriptions = []
        # First, render any dependencies of this snippet
        for dep in snippet.header.dependencies:
            dep_snippet = self.get(dep)
            render_descriptions.extend(
                self.render_snippet(dep_snippet, strip_presentation_commands=strip_presentation_commands)
            )

        print(f"render_snippet({snippet})")
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
                    # if embedded_snippet_render_description.header.file:
                    #    raise ValueError(f"Did not expect an embedded snippet to want to be rendered to a specific path, but specified {embedded_snippet_render_description.header.file}")
                    this_snippet_text += self.render_snippet(embedded_snippet_render_description)[0].text

                # Output whatever comes next
                section = splits[1]

            # Just text prior
            this_snippet_text += section
        render_descriptions.append(SnippetRenderDescription(text=this_snippet_text, file=snippet.header.file))
        return render_descriptions
