import shutil
from pathlib import Path

from spiderweb import SnippetRepository, ROOT_FOLDER, run_and_check, run_and_capture_output


def render_markdown():
    repo = SnippetRepository()
    content = ROOT_FOLDER / "content" / "index.md"
    output = ROOT_FOLDER / "generated-site" / "content" / "_index.md"

    text = content.read_text()
    parts = text.split("{{")
    out = ""
    for part in parts:
        # Handle commands
        if part.startswith("-update"):
            part_split_by_newline = part.split("\n")
            snippet_name = part_split_by_newline[0].split(" ")[1]
            print(f'Updating snippet name {snippet_name}')
            # Scan until the closing brace
            remaining_text = "\n".join(part_split_by_newline)[1:]
            new_text = remaining_text.split("}}>>")[0]
            print(f'new text: {new_text}')

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
    generated_programs_dir = ROOT_FOLDER / "generated-programs"
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
