import argparse
from pathlib import Path

from penpal.env import ROOT_FOLDER
from penpal.render import (
    parse_document_text, DocumentRenderer,
)


INPUT = ROOT_FOLDER / "content" / "index.md"
OUTPUT = ROOT_FOLDER / "generated-site" / "content" / "_index.md"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file')
    parser.add_argument('output_file')
    args = parser.parse_args()
    sections = parse_document_text(Path(args.input_file).read_text())
    renderer = DocumentRenderer(sections)
    output_text = renderer.render()
    Path(args.output_file).write_text(output_text)


if __name__ == '__main__':
    main()
