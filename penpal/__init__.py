from penpal.env import CHAPTER_1_ROOT, ROOT_FOLDER
from penpal.render import (
    render_programs,
    render_program,
    parse_document_text,
)
from penpal.shell_utils import run_and_check, run_and_capture_output
from penpal.snippet import SnippetRepository


def main():
    content = ROOT_FOLDER / "content" / "index.md"
    sections = parse_document_text(content.read_text())
    output_text = render_sections(sections)
    output_file = ROOT_FOLDER / "generated-site" / "content" / "_index.md"
    output_file.write_text(output_text)


if __name__ == "__main__":
    main()
