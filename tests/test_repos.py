from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from git import RemoteReference, Repo

import git_unneeded
from git_unneeded import Safe, Unsafe, repository_safe_to_delete


def test_repo_has_dirty_working_directory(temp_repo: Repo) -> None:
    working_directory = Path(temp_repo.working_dir)

    with open(working_directory / "newfile", "x") as f:
        f.write("newfile")

    reasons = list(repository_safe_to_delete(temp_repo, fetch=False))
    assert len(reasons) == 1

    r = reasons[0]

    assert isinstance(r, Unsafe)
    assert "newfile" in str(r)
    assert "Untracked files in working directory" in str(r)


def test_repo_has_dirty_index(temp_repo: Repo) -> None:
    working_directory = Path(temp_repo.working_dir)

    new_file_path = working_directory / "newfile"
    with open(new_file_path, "x") as f:
        f.write("newfile")

    temp_repo.index.add(items=[new_file_path])  # pyright: ignore[reportUnknownMemberType]

    reasons = list(repository_safe_to_delete(temp_repo))
    assert len(reasons) == 1

    r = reasons[0]

    assert isinstance(r, Unsafe)
    assert "is dirty" in str(r)
    assert "git status" in str(r)


def test_repo_is_up_to_date_with_remote(cloned_repo: Repo) -> None:
    reasons = list(repository_safe_to_delete(cloned_repo))

    assert len(reasons) == 0


def test_repo_with_extra_empty_branch_generates_one_safe(cloned_repo: Repo) -> None:

    branch_c = cloned_repo.create_head("new-c", commit=cloned_repo.active_branch.commit.hexsha)
    # not checked out, otherwise delete_head() will fail later

    reasons = list(repository_safe_to_delete(cloned_repo))
    assert len(reasons) == 1

    r = reasons[0]
    assert isinstance(r, Safe)
    assert "delete branch refs/heads/new-c" in r.reason  # is the order always stable?
    assert "also on refs/heads/new-b" in r.reason
    assert "git branch --verbose -d new-c" in r.suggestions

    # but it's ok after deleting that branch
    cloned_repo.delete_head(branch_c)

    after_reasons = list(repository_safe_to_delete(cloned_repo, fetch=False))
    assert len(after_reasons) == 0


def test_repo_with_extra_new_commit_generates_two_unsafe(cloned_repo: Repo) -> None:
    working_directory = Path(cloned_repo.working_dir)

    a_file = working_directory / "a.txt"
    with open(a_file, "x") as f:
        f.write("aaaa")

    cloned_repo.index.add(items=[a_file])  # pyright: ignore[reportUnknownMemberType]
    a_commit = cloned_repo.index.commit(message="test commit")

    reasons = list(repository_safe_to_delete(cloned_repo, fetch=True))
    assert len(reasons) == 2

    extra_commits_reason = reasons[0]
    assert isinstance(extra_commits_reason, Unsafe)
    assert "has commits" in extra_commits_reason.reason
    assert "git log" in extra_commits_reason.suggestions[0]
    assert a_commit.hexsha in extra_commits_reason.suggestions[1]

    active_reason = reasons[1]
    assert isinstance(extra_commits_reason, Unsafe)
    assert "might be active" in active_reason.reason

    # but it's ok after pushing that branch
    assert cloned_repo.active_branch.tracking_branch()
    cloned_repo.remotes[0].push(refspec="refs/heads/new-b:refs/heads/new-b", verbose=True)

    reasons = list(repository_safe_to_delete(cloned_repo, fetch=True))
    assert len(reasons) == 0


def test_repo_inactive_last_commit_old_and_behind_remote(cloned_repo: Repo) -> None:
    """
    Make a backdated commit and a second one, push both,
    and revert local branch back to the backdated commit.

    It looks like we pushed the backdated commit a week ago,
    and someone else made a commit since.

    Our local branch is now behind the upstream.
    """

    backdated_commit = cloned_repo.index.commit(message="backdated commit", commit_date=datetime.now(tz=UTC) - timedelta(days=3))
    _someone_else_made_this = cloned_repo.index.commit(message="someone else made a commit")

    assert cloned_repo.active_branch.tracking_branch()
    cloned_repo.remotes[0].push(refspec="refs/heads/new-b:refs/heads/new-b", verbose=True)

    verify_latest_commits = list(cloned_repo.iter_commits(rev=cloned_repo.active_branch, since="5.days.ago", date_order=True, max_count=5))
    print(verify_latest_commits)

    # revert our branch back to the backdated commit
    cloned_repo.active_branch.set_commit(backdated_commit)

    reasons = list(repository_safe_to_delete(cloned_repo, fetch=True))

    behind_remote_reason = reasons[0]
    inactive_reason = reasons[1]

    assert "is behind" in str(behind_remote_reason)
    assert "inactive" in str(inactive_reason)


def test_local_branch_unknown_to_remote(cloned_repo: Repo) -> None:
    h = cloned_repo.create_head("refs/heads/localbranch", commit=cloned_repo.active_branch.commit)
    h.checkout()

    local_commit = cloned_repo.index.commit(message="local commit", commit_date=datetime.now(tz=UTC) - timedelta(days=3))

    reasons = list(repository_safe_to_delete(cloned_repo, fetch=True))

    for r in reasons:
        match r.__class__.__name__, r:
            case "Safe", r:
                assert "delete branch refs/heads/new-b" in r.reason

            case "Unsafe", r:
                assert "branch localbranch is not known to remotes" in r.reason
                assert "has commits" in r.reason
                assert git_unneeded.describe_commit_one_line(local_commit) in r.suggestions

            case classname, r:  # pragma: no cover
                raise ValueError(f"Unexpected reason class {classname}: {r}")


def test_upstream_is_gone(cloned_repo: Repo) -> None:
    """Issue #1"""

    # Deleting like vvv doesn't result in the state where "... but the upstream is gone" is seen.
    # remote_git_repo.delete_head("new-b", force=True)  # git branch -D new-b

    cloned_repo.refs["main"].checkout()
    pil = cloned_repo.remote("origin").push("new-b", delete=True)
    assert pil[0].summary == "[deleted]\n"  # delete remote ref

    switch_result = cloned_repo.git.switch("new-b")
    assert "but the upstream is gone" in switch_result

    new_b = cloned_repo.branches["new-b"]
    tracking_branch = new_b.tracking_branch()

    assert isinstance(tracking_branch, RemoteReference)
    assert tracking_branch.path == "refs/remotes/origin/new-b"

    with pytest.raises(ValueError):
        tracking_branch.commit

    with pytest.raises(ValueError) as e:
        tracking_branch.dereference_recursive(tracking_branch.repo, tracking_branch.path)
    assert e.value.args[0] == "Reference at 'refs/remotes/origin/new-b' does not exist"

    reasons = list(repository_safe_to_delete(cloned_repo, fetch=True))
    assert "It was probably deleted" in str(reasons[0])
