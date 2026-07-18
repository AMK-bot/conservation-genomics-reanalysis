#!/usr/bin/env python3
"""Run the Streamlit AppTest smoke suite with this Python interpreter.

The runner captures the complete unittest output in a log and writes a short,
stable Markdown result suitable for tracking in the repository.  It does not
start a Streamlit server or execute any bioinformatics.
"""

from __future__ import annotations

import argparse
import platform
import re
import shlex
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", default="tests/test_streamlit_app.py")
    parser.add_argument("--out-md", default="results/APP_SMOKE.md")
    parser.add_argument("--log", default="results/logs/app_smoke.log")
    parser.add_argument("--timeout", type=int, default=180)
    return parser.parse_args()


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _write_result(
    output: Path,
    *,
    passed: bool,
    test_display: str,
    test_count: int | None,
    return_code: int | str,
) -> None:
    count_text = str(test_count) if test_count is not None else "not parsed"
    status = "PASS" if passed else "FAIL"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "# Streamlit application smoke test\n\n"
        f"- **Status:** **{status}**\n"
        f"- **Test:** `{test_display}`\n"
        f"- **Interpreter:** Python {platform.python_version()}\n"
        f"- **Tests run:** {count_text}\n"
        f"- **Return code:** `{return_code}`\n\n"
        "The suite executes every peafowl filter/structure state and every wolf GERP/ROH "
        "sensitivity state through Streamlit's in-process application test harness. No server "
        "or heavy analysis is started.\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    test = _resolve(root, args.test)
    out_md = _resolve(root, args.out_md)
    log = _resolve(root, args.log)
    test_display = test.relative_to(root).as_posix() if test.is_relative_to(root) else str(test)

    log.parent.mkdir(parents=True, exist_ok=True)
    if not test.is_file():
        message = f"missing smoke test: {test_display}\n"
        log.write_text(message, encoding="utf-8")
        _write_result(
            out_md,
            passed=False,
            test_display=test_display,
            test_count=None,
            return_code="not run",
        )
        print(message, end="", file=sys.stderr)
        raise SystemExit(1)

    command = [sys.executable, str(test)]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=args.timeout,
            check=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        return_code: int | str = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stderr += f"\nTIMEOUT after {args.timeout} seconds\n"
        return_code = "timeout"
        timed_out = True

    combined = stdout + "\n" + stderr
    count_match = re.search(r"Ran\s+(\d+)\s+tests?\s+in", combined)
    test_count = int(count_match.group(1)) if count_match else None
    passed = not timed_out and return_code == 0 and test_count is not None and bool(
        re.search(r"(?m)^OK\s*$", combined)
    )

    display_command = ["python", test_display]
    log.write_text(
        f"Command: {shlex.join(display_command)}\n"
        f"Interpreter: {sys.executable}\n"
        f"Return code: {return_code}\n\n"
        f"--- stdout ---\n{stdout.rstrip()}\n\n"
        f"--- stderr ---\n{stderr.rstrip()}\n",
        encoding="utf-8",
    )
    _write_result(
        out_md,
        passed=passed,
        test_display=test_display,
        test_count=test_count,
        return_code=return_code,
    )

    print(f"app smoke: {'PASS' if passed else 'FAIL'} ({test_count or 0} tests)")
    print(f"result: {out_md.relative_to(root) if out_md.is_relative_to(root) else out_md}")
    print(f"log: {log.relative_to(root) if log.is_relative_to(root) else log}")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
