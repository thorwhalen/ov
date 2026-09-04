"""Characterization tests pinning the ``ov`` command-line surface.

``tests/cli_goldens/ov.json`` was recorded from the *argh* implementation of
:mod:`ov.__main__` before the migration to :mod:`cw`, with
``cw.testing.characterize``. Every assertion below compares today's CLI against
the grammar argh produced, not against something written by hand afterwards.

What is pinned, and why each one matters here:

1. **The grammar** -- every command, flag, short flag and default, via the
   recorded ``usage:`` line and full stdout/stderr of 16 ``argv`` vectors.
2. **Generator egress.** *Every* command in this CLI is a generator function.
   argh consumed them and printed one line per yielded item; an egress that
   merely did ``print(result)`` would print ``<generator object ...>``. The
   dedicated test below drives ``runs`` against a fabricated store and asserts
   the exact line-per-item bytes, because the golden cannot: ``runs`` with the
   default store lists whatever the recording machine happened to have captured.
3. **The exit codes.** ``cw.run`` *returns* the exit code where argh exited by
   itself, so ``main()`` must hand it back and the ``__main__`` guard must
   ``raise SystemExit(main())``. Drop either and argument errors exit 0.
4. **No arguments prints usage to stdout and exits 0** -- argh's behaviour,
   which plain argparse with a required subparser does not have.

The golden is replayed non-strictly: ``--help`` bodies are compared but a pure
formatting difference is reported rather than failed, because CPython rewrites
argparse's own option column between versions. At migration time the *strict*
comparison was empty on CPython 3.10 and 3.12 alike.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cw.testing import assert_replay

GOLDEN_PATH = Path(__file__).parent / "cli_goldens" / "ov.json"

# ``prog`` is pinned to "ov" inside main(), so the ``python -m`` form and the
# console script produce byte-identical output. Driving the module form keeps
# the test independent of PATH and of the ``.exe`` shim on Windows.
CLI = [sys.executable, "-m", "ov"]


@pytest.fixture(scope="module")
def golden():
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_cli_surface_matches_the_argh_recorded_golden(golden):
    """The whole grammar, replayed against what argh produced."""
    assert_replay(golden, prog=CLI)


def test_golden_carries_no_machine_specific_prog():
    """A golden that names an absolute path can only replay on one computer."""
    raw = GOLDEN_PATH.read_text(encoding="utf-8")
    assert "/Users/" not in raw and "\\\\Users\\\\" not in raw
    assert json.loads(raw)["prog"] == ["ov"]


def _run(*argv):
    return subprocess.run(CLI + list(argv), capture_output=True, text=True, timeout=120)


def test_no_arguments_prints_usage_to_stdout_and_exits_zero():
    """argh's behaviour, preserved. Plain argparse would exit 2 to stderr."""
    r = _run()
    assert r.returncode == 0
    assert r.stdout.startswith("usage: ov")
    assert r.stderr == ""


@pytest.mark.parametrize(
    "argv",
    [
        ("no-such-command",),
        ("observe", "--no-such-flag"),
        ("observe",),  # missing the required positional
    ],
)
def test_argument_errors_exit_two(argv):
    """Guards `raise SystemExit(main())` / `return cw.run(...)`.

    Without them the exit code is swallowed and every one of these exits 0.
    """
    assert _run(*argv).returncode == 2


def test_a_generator_command_prints_one_line_per_yielded_item(tmp_path):
    """`runs` yields; the CLI must print its items, not the generator object.

    This is the property the golden cannot cover, and the one most likely to
    regress silently: the output of a generator command is only wrong at
    runtime, never at parse time, so no ``--help`` diff would ever show it.
    """
    import io

    import cw

    from ov.__main__ import COMMANDS

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    for run_id in ("run_bbb", "run_aaa"):  # written out of order on purpose
        (runs_dir / f"{run_id}.json").write_text("{}", encoding="utf-8")

    out = io.StringIO()
    code = cw.dispatch(COMMANDS, ["runs", "--store", str(tmp_path)], out=out)

    assert code == 0
    assert out.getvalue() == "run_aaa\nrun_bbb\n"


def test_an_empty_generator_command_prints_nothing(tmp_path):
    """The zero-item case: no output, exit 0 -- not an empty ``repr``."""
    import io

    import cw

    from ov.__main__ import COMMANDS

    (tmp_path / "runs").mkdir()
    out = io.StringIO()
    code = cw.dispatch(COMMANDS, ["runs", "--store", str(tmp_path)], out=out)

    assert code == 0
    assert out.getvalue() == ""


def test_commands_list_is_what_the_parser_dispatches():
    """`COMMANDS` is the single source of truth the help text is built from."""
    from ov.__main__ import COMMANDS

    names = [f.__name__ for f in COMMANDS]
    assert names == [
        "observe",
        "analyze",
        "diff",
        "report",
        "synopsis",
        "overview",
        "evidence",
        "check",
        "runs",
        "mcp",
    ]

    help_text = _run("--help").stdout
    for name in names:
        assert name in help_text
