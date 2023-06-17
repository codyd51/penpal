import shutil
from pathlib import Path

from spiderweb.markdown_parser import MarkdownParser, TokenType, ShowCommand, UpdateCommand
from spiderweb.snippet import SnippetRepository
from spiderweb.env import ROOT_FOLDER
from spiderweb.shell_utils import run_and_check, run_and_capture_output


def render_markdown():
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
        print(f'Got command {command}')
        if isinstance(command, ShowCommand):
            # Treat this as an embedded snippet
            snippet = repo.get(command.snippet_name)
            output_text += f"```{snippet.header.lang.value}\n"
            output_text += repo.render_snippet(snippet)[0].text
            output_text += f"\n```\n"
        elif isinstance(command, UpdateCommand):
            # Update the snippet contents
            snippet = repo.get(command.snippet_name)
            print(f'Updating `{snippet}`...')
            snippet.text = command.update_data
            # Also show it
            output_text += f"_{snippet.header.file}_\n"
            output_text += f"```{snippet.header.lang.value}\n"
            output_text += repo.render_snippet(snippet)[0].text
            output_text += f"```\n"
        else:
            raise NotImplementedError(f"Unhandled command type {type(command)}")

    output.write_text(output_text)


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
