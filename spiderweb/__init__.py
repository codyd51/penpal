from spiderweb.env import CHAPTER_1_ROOT, ROOT_FOLDER
from spiderweb.render import render_programs, render_program, test_executable
from spiderweb.shell_utils import run_and_check, run_and_capture_output
from spiderweb.snippet import SnippetRepository


def main():
    #render_programs()
    test_executable("listing3")
    #render_markdown()
    #test_executables()


if __name__ == '__main__':
    main()
