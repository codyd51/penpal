from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Self

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


class SnippetRepository:
    def __init__(self):
        chapter_1_snippets = _ROOT_FOLDER / "chapter_1" / "snippets"
        snippets = {}
        for file in chapter_1_snippets.iterdir():
            snippets[file.name] = Snippet.from_file(file)
        self.snippets = snippets
        print(snippets)

    def get(self, id: str) -> Snippet:
        return self.snippets[f"{id}.md"]

    def render_snippet(self, snippet: Snippet) -> str:
        print(f'render_snippet({snippet})')
        out = ""
        breaks = snippet.text.split("{{")
        for section in breaks:
            if "}}" in section:
                splits = section.split("}}")

                embedded_command_or_snippet_name = splits[0]

                # Some names denote special commands
                if embedded_command_or_snippet_name == "highlight":
                    # Insert some styling tags
                    out += "{{< rawhtml >}}"
                    out += '<div style="background-color: #c2c439">'
                elif embedded_command_or_snippet_name == "/highlight":
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


def render_snippets():
    repo = SnippetRepository()
    print(repo.render_snippet(repo.get("listing1")))
    print(repo.render_snippet(repo.get("listing2")))


def main():
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

    # print(out)
    output.write_text(out)


if __name__ == '__main__':
    main()
