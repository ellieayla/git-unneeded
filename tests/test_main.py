import sys
from collections.abc import Iterable
from contextlib import nullcontext
from dataclasses import dataclass
from itertools import tee
from pathlib import Path
from typing import cast
from unittest import mock

import pytest
from git import PathLike, Repo

import git_unneeded


@dataclass
class FakeRepo:
    """Minimal git.Repo object with properties for printing."""
    working_dir: PathLike | None = None
    git_dir: PathLike | None = None


@pytest.fixture(autouse=True)
def mocked_repository_safe_to_delete() -> Iterable[mock.Mock]:
    with mock.patch.object(git_unneeded, "repository_safe_to_delete") as m:
        yield m


def main(*args: str | Path | PathLike | None) -> int:
    """
    Mock sys.argv with passed arguments (dropping None), and call git_unneeded.main().
    
    Pass any returned value or thrown exception back up to caller.
    """

    string_args = [str(x) for x in args if x is not None]
    with mock.patch.object(sys, "argv", new=["app", *string_args]):
        try:
            return git_unneeded.main()
        finally:
            pass


def assert_same_as[T](value: T, iterable: Iterable[T]) -> None:
    __tracebackhide__ = True

    stashed, shared = tee(iterable)

    rep = "".join([f"\n  item {position} = {value}" for position, value in enumerate(stashed)])

    if value:
        if not all(shared):
            pytest.fail(f"one of these things is not equal to {value}:\n[" + rep + "\n]")
    else:
        if any(shared):
            pytest.fail(f"one of these things is not equal to {value}:\n[" + rep + "\n]")


@pytest.mark.xfail(strict=True)
@pytest.mark.parametrize(
    ("value", "not_that"),
    [
        (True, False),
        (False, 5)
    ]
)
def test_verify_assert_same_as_helper_fn(value: bool | int, not_that: bool | int) -> None:
    assert_same_as(value, [not_that])


produces = nullcontext  # stand-in for pytest.raises(...) which returns its argument


def test_verify_mocked_repository_safe_to_delete_fixture(mocked_repository_safe_to_delete: mock.Mock) -> None:
    repo = cast(Repo, FakeRepo(working_dir=""))
    assert callable(mocked_repository_safe_to_delete)
    mocked_repository_safe_to_delete.return_value = [git_unneeded.Safe(repo, "whatever", ["s1"])]
    assert [git_unneeded.Safe(repo, "whatever", ["s1"])] == mocked_repository_safe_to_delete("whatever")


def test_help_on_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        assert 0 == main(tmp_path, "--help")

    out, err = capsys.readouterr()
    assert "" == err
    assert "usage:" in out
    assert "--no-search-parent" in out


def test_no_repo_found_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        assert 0 == main(tmp_path)

    out, err = capsys.readouterr()
    assert "" == out
    assert "usage:" in err
    assert ".git not found" in err


@pytest.mark.parametrize("color_on", (True, False))
def test_color_switches(temp_repo: Repo, color_on: bool, capsys: pytest.CaptureFixture[str]) -> None:
    reset_string = "\x1b[0m"

    assert 0 == main(str(temp_repo.working_dir), "--color", "always" if color_on else "never")
    out, err = capsys.readouterr()
    assert "" == err

    assert_same_as(color_on, [
        reset_string in out
    ])


def test_color_autodetection_of_tty(tmp_path: Path, mocked_repository_safe_to_delete: mock.Mock) -> None:
    with mock.patch("sys.stdout") as mocked_stdout:
        mocked_stdout
        del mocked_stdout.fileno
        assert not hasattr(sys.stdout, "fileno")
        main(str(tmp_path), "--color", "auto", "--skip-unknown-directories")

    # main called Colors.disable()
    assert git_unneeded.Colors.RESET == ""


@pytest.mark.parametrize("setenv, color_enabled", [
    (("NO_COLOR", "1"), False),
    (("FORCE_COLOR", "1"), True),
    (("TERM", "dumb"), False),
])
def test_color_automatically_disabled_if_env_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setenv: tuple[str,str], color_enabled: bool, mocked_repository_safe_to_delete: mock.Mock) -> None:
    
    with monkeypatch.context() as m:
        m.setenv(name=setenv[0], value=setenv[1])
        with mock.patch("sys.stdout", spec=sys.stdout):
            main(str(tmp_path), "--color", "auto", "--skip-unknown-directories")

    # main called Colors.disable()
    assert_same_as(color_enabled, [
        git_unneeded.Colors.RESET != ""
    ])


@pytest.mark.parametrize("debug_logging_on", (True, False))
def test_debug_switch(temp_repo: Repo, debug_logging_on: bool) -> None:

    assert 0 == main(str(temp_repo.working_dir), "--debug" if debug_logging_on else None)


@pytest.mark.parametrize("quiet_mode_on", (True, False))
def test_quiet_switch(temp_repo: Repo, quiet_mode_on: bool, capsys: pytest.CaptureFixture[str], mocked_repository_safe_to_delete: mock.Mock) -> None:
    """Print reasons only when not in quiet mode."""

    mocked_repository_safe_to_delete.return_value = [
        git_unneeded.Safe(
            temp_repo, "justifications do not appear in quiet mode", ["suggestions do not appear either"]
        )
    ]

    assert 0 == main(str(temp_repo.working_dir), "--quiet" if quiet_mode_on else None)

    out, _err = capsys.readouterr()

    assert_same_as(quiet_mode_on, [
        "justifications do not appear in quiet mode" not in out,
        "suggestions do not appear either" not in out,
    ])


@pytest.mark.parametrize("one_line_output_mode_on", (True, False))
def test_one_line_output_switch(temp_repo: Repo, one_line_output_mode_on: bool, capsys: pytest.CaptureFixture[str], mocked_repository_safe_to_delete: mock.Mock) -> None:

    mocked_repository_safe_to_delete.return_value = [
        git_unneeded.Safe(
            temp_repo, "justifications do not appear in oneline mode", ["suggestions do not appear either"]
        )
    ]

    assert 0 == main(str(temp_repo.working_dir), "--oneline" if one_line_output_mode_on else None)

    out, _err = capsys.readouterr()

    assert_same_as(
        one_line_output_mode_on,
        [
            "justifications do not appear in oneline mode" not in out,
            out == f"{temp_repo.working_dir}\0True\n",
        ]
    )


@pytest.mark.parametrize("ignore_missing_dir_on", (True, False))
def test_skip_unknown_directories(tmp_path: Path, ignore_missing_dir_on: bool) -> None:
    if ignore_missing_dir_on:
        assert 0 == main(str(tmp_path), "--skip-unknown-directories")

    else:
        with pytest.raises(SystemExit) as e:
            main(str(tmp_path))
        assert e.value.args[0] == 2


@pytest.mark.parametrize("search_parent_directories_on", (True, False))
def test_search_parent_directories(temp_repo: Repo, search_parent_directories_on: bool, capsys: pytest.CaptureFixture[str], mocked_repository_safe_to_delete: mock.Mock) -> None:
    working_dir = Path(temp_repo.working_dir)
    subdir = working_dir / "subdir"
    subdir.mkdir()


    if search_parent_directories_on:
        assert 0 == main(str(subdir))
        assert mocked_repository_safe_to_delete.called
    else:
        with pytest.raises(SystemExit):
            main(str(subdir), "--no-search-parent")
        assert not mocked_repository_safe_to_delete.called

    if not search_parent_directories_on:
        _out, err = capsys.readouterr()
        assert "not found" in err


@pytest.mark.parametrize("no_fetch_switch", (True, False))
def test_no_fetch(temp_repo: Repo, no_fetch_switch: bool, mocked_repository_safe_to_delete: mock.Mock) -> None:

    main(temp_repo.working_dir, "--no-fetch" if no_fetch_switch else None)

    assert 1 == mocked_repository_safe_to_delete.call_count

    assert mocked_repository_safe_to_delete.call_args.kwargs.get("fetch") is not no_fetch_switch


def test_unsafe_to_delete_repo_shows_reasons_and_exits_1(temp_repo: Repo, capsys: pytest.CaptureFixture[str], mocked_repository_safe_to_delete: mock.Mock) -> None:
    mocked_repository_safe_to_delete.return_value = [
        git_unneeded.Unsafe(
            temp_repo, "justifications", ["suggestions"]
        )
    ]

    assert 1 == main(str(temp_repo.working_dir), "--color=never")
    out, err = capsys.readouterr()

    assert "| Unsafe: justifications" in out
    assert "|   => suggestions" in out


def test_iterate_over_multiple_repos(tmp_path: Path, capsys: pytest.CaptureFixture[str], mocked_repository_safe_to_delete: mock.Mock) -> None:

    def _repo_in_subdir(name: str) -> str:
        subdir_path = tmp_path / name
        subdir_path.mkdir()
        Repo.init(subdir_path)
        return str(subdir_path.absolute())

    subdir_names = ("subdir-a", "subdir-b")
    main(*list([_repo_in_subdir(x) for x in subdir_names]))

    # both repos checked
    assert 2 == mocked_repository_safe_to_delete.call_count

