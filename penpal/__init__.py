from pathlib import Path

from penpal.env import CHAPTER_1_ROOT, ROOT_FOLDER
from penpal.render import (
    parse_document_text, DocumentRenderer,
)
from penpal.shell_utils import run_and_check, run_and_capture_output
from penpal.snippet import SnippetRepository


INPUT = ROOT_FOLDER / "content" / "index.md"
OUTPUT = ROOT_FOLDER / "generated-site" / "content" / "_index.md"

INPUT = Path("/Users/philliptennen/Documents/axle-blog/content/blog/literate_programming/index-in.md")
OUTPUT = Path("/Users/philliptennen/Documents/axle-blog/content/blog/literate_programming/index.md")


def main():
    sections = parse_document_text(INPUT.read_text())
    renderer = DocumentRenderer(sections)
    output_text = renderer.render()
    OUTPUT.write_text(output_text)


if __name__ == "__main__":
    main()
