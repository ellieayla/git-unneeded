from pathlib import Path

from git import Repo

from git_unneeded import describe_commit_one_line


def test_render_one_line_summary_of_commit(temp_repo: Repo) -> None:
    working_directory = Path(temp_repo.working_dir)

    new_file_path = working_directory / "newfile"
    with open(new_file_path, "x") as f:
        f.write("newfile")

    temp_repo.index.add(items=[new_file_path])  # pyright: ignore[reportUnknownMemberType]
    temp_repo.index.commit(message="first commit")

    c = temp_repo.head.commit
    text = describe_commit_one_line(c)

    assert "first commit" in text
    assert "\n" not in text
