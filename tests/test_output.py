from dataclasses import dataclass
from functools import partial
from typing import cast

import pytest

from git_unneeded import Colors, Safe, Unsafe, git, print_if_not_quiet


@dataclass
class FakeRepo:
    working_dir: git.PathLike | None = None
    git_dir: git.PathLike | None = None


def test_print_if_quiet(capsys: pytest.CaptureFixture[str]) -> None:
    p = partial(print_if_not_quiet, quiet=True)
    p("111")

    r = capsys.readouterr()
    assert "111" not in r.out


def test_print_if_not_quiet(capsys: pytest.CaptureFixture[str]) -> None:
    p = partial(print_if_not_quiet, quiet=False)
    p("111")

    r = capsys.readouterr()
    assert "111" in r.out


@pytest.mark.parametrize("suggestions", [[], ["s1"], ["s5", "s6", "s7"]])
@pytest.mark.parametrize("fake_repo_object", [FakeRepo(working_dir="aaa"), FakeRepo(git_dir="aaa")], ids=repr)
@pytest.mark.parametrize("repo_path_in_repr", [True, False])
@pytest.mark.parametrize("safeness_class", [Safe, Unsafe])
def test_unsafe(fake_repo_object: FakeRepo, suggestions: list[str], repo_path_in_repr: bool, safeness_class: type[Safe | Unsafe]) -> None:

    repo = cast(git.Repo, fake_repo_object)
    u = safeness_class(repo, "reason", suggestions)

    r = u.format(with_repo=repo_path_in_repr)

    print(r)

    if repo_path_in_repr:
        assert "aaa" in r
    else:
        assert "aaa" not in r

    assert "Safe" in r or "Unsafe" in r
    assert "reason" in r

    assert all([" => " + s in r for s in suggestions])


def test_colors_balanced() -> None:
    fake_repo_object = FakeRepo(working_dir="aaa")
    repo = cast(git.Repo, fake_repo_object)

    text = Unsafe(repo, "reason name", ["s5", "s6"]).format()

    assert "\n" in text

    stack = 0

    pos = 5
    print(f"{text=}")
    for offset, character in enumerate(text):
        pos += 1
        if character == "\x1b":
            pos += 3
            print(" " * pos, "^", sep="", end=" - ")
            if text[offset:].startswith(Colors.RESET):
                print("Down")
                stack -= 1
            else:
                print("Up")
                stack += 1

    assert stack == 0
