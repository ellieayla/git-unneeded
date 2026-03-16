
from collections.abc import Iterable, Generator
from pathlib import Path
from unittest import mock

import pytest
from git import Repo, RemoteReference
from git.cmd import Git

import git_unneeded


class MockedColors(git_unneeded.Colors):
    ...


@pytest.fixture(autouse=True)
def mock_colors_class() -> Generator[None, None, None]:
    """Replace Colors with a copy so main() can clobber it, restore afterward."""

    reset_string = "\x1b[0m"

    # HACK: copy over colors to mock
    for k, v in git_unneeded.Colors.__dict__.items():
        if k.upper() == k:
            setattr(MockedColors, k, v)

    with mock.patch.object(git_unneeded, "Colors", new=MockedColors):
        try:
            yield
        finally:
            pass

    # make sure it was restored properly.
    assert git_unneeded.Colors.RESET == reset_string


def print_repo_details_at_cleanup(repo: Repo) -> None:
    print("working dir files:")
    working_dir = Path(repo.working_dir)
    for filename in working_dir.iterdir():
        print(f"  {filename.relative_to(working_dir)}")
    
    if repo.heads:
        print("Commits:")
        for x in repo.iter_commits(all=True):
            print(f" {x}\t{str(x.summary)}")

        print("Branches:")
        for b in repo.branches:
            print(f" {b!r}")

        print("Refs:")
        for r in repo.refs:
            print(f" {r!r} @ {r.commit}")


@pytest.fixture
def temp_repo(tmp_path: Path) -> Iterable[Repo]:
    p = tmp_path / "R"
    p.mkdir()

    repo = Repo.init(p)
    yield repo

    print_repo_details_at_cleanup(repo)


@pytest.fixture
def cloned_repo(tmp_path: Path) -> Iterable[Repo]:

    upstream_path = tmp_path / "Upstream"
    upstream_path.mkdir()

    repo = Repo.init(upstream_path)

    original_branch = repo.active_branch

    new_file_path = upstream_path / "file.txt"
    with open(new_file_path, "x") as f:
        f.write("file content")

    repo.index.add(items=[new_file_path]) # pyright: ignore[reportUnknownMemberType]
    first_commit = repo.index.commit(message="first commit")
    
    new_branch_b = repo.create_head("new-b", commit=first_commit.hexsha)
    new_branch_b.checkout()

    file_2_path = upstream_path / "file2.txt"
    with open(file_2_path, "x") as f:
        f.write("file 2 content")

    repo.index.add(items=[file_2_path]) # pyright: ignore[reportUnknownMemberType]
    second_commit = repo.index.commit(message="commit 2", parent_commits=[first_commit])
    print_repo_details_at_cleanup(repo)
    #new_branch_b = repo.create_head("new-b", commit=second_commit.hexsha)
    #repo.head.reference = new_branch_b

    # switch back to main branch
    original_branch.checkout()

    clone_path = tmp_path / "Clone"
    clone_path.mkdir()

    clone = Repo.clone_from(url=upstream_path, to_path=clone_path)


    # set up tracking for all branches
    for remote_branch in repo.branches:
        git_cli = Git(clone_path)
        git_cli.checkout(remote_branch.name)

    yield clone

    print_repo_details_at_cleanup(clone)
