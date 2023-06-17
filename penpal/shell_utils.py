import io
import os
import selectors
import subprocess
import sys
from pathlib import Path
from typing import Optional


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
