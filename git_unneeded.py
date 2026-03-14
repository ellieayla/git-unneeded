#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "gitpython>=3.1.46",
# ]
# ///

"""
Determine whether we don't need this clone (or some of its branches) anymore.

If a branch has been pushed/merged, we don't need to keep it.
"""

import logging
import os
import subprocess
import sys
from argparse import ArgumentParser, Namespace
from collections.abc import Iterable, Generator, Sequence
from datetime import datetime, timedelta, timezone
from textwrap import indent
from typing import IO

import git

logger = logging.getLogger()


class Colors:
    """Minimal piece of stdlib _colorize"""

    RESET = "\x1b[0m"
    BOLD_RED = "\x1b[1;31m"
    BOLD_GREEN = "\x1b[1;32m"
    BOLD_BLUE = "\x1b[1;34m"
    BOLD = "\x1b[1m"

    INTENSE_GREEN = "\x1b[92m"
    GREEN = "\x1b[32m"

    @classmethod
    def disable(cls) -> None:
        for attr in cls.__dict__.keys():
            if not attr.startswith("__"):
                setattr(cls, attr, "")

    @classmethod
    def can(cls, file: IO[str] | IO[bytes]) -> bool:
        # overrides
        if os.environ.get("NO_COLOR", None):
            return False
        if os.environ.get("FORCE_COLOR", None):
            return True
        if os.environ.get("TERM", None) == "dumb":
            return False

        if not hasattr(file, "fileno"):
            return False

        try:
            return os.isatty(file.fileno())
        except OSError:
            return hasattr(file, "isatty") and file.isatty()


def find_my_fork(repo: git.Repo, mine: list[str]) -> git.Remote:
    for remote in repo.remotes:
        for url in remote.urls:
            for m in mine:
                logger.debug(f"Checking {remote.name=} {url=} vs {m=}")
                if url.startswith(m):
                    return remote

    raise ValueError("No remote configured matching my prefixes.")


class EnvDefaultList(list[str]):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name
        self.extend([x for x in os.environ.get(self.name, "").split(",") if x.strip()])

    def __str__(self) -> str:
        return f"env:{self.name} (currently {list(iter(self))})"


def get_mine_from_gh() -> Iterable[str]:

    assumed_host_prefixes = [
        "https://github.com/",
        "git@github.com:",
    ]
    cache = ["--cache", "100h"]
    k = subprocess.check_output(["gh", "api", "/user/orgs", "--jq", ".[].login", *cache], text=True).splitlines()
    yield from [f"{host}{org}" for host in assumed_host_prefixes for org in k]

    j = subprocess.check_output(["gh", "api", "/user", "--jq", ".login", *cache], text=True).splitlines()
    yield from [f"{host}{user}" for host in assumed_host_prefixes for user in j]


class Safe:
    _major_color = Colors.GREEN
    repo_path: git.PathLike
    reason: str
    suggestions: Sequence[str]

    def __init__(self, repo: git.Repo, reason: str, suggestions: Sequence[str] = ()) -> None:
        if repo.working_dir:
            self.repo_path = repo.working_dir
        else:
            self.repo_path = repo.git_dir
        self.reason = reason
        self.suggestions = suggestions

    def format(self, with_repo: bool = False) -> str:
        repo_chunk = f" - {Colors.RESET} - {self.repo_path}" if with_repo else ""
        return "\n".join([
            f"{self._major_color}{self.__class__.__name__}{Colors.RESET}{Colors.BOLD}:{Colors.RESET} {self.reason}{repo_chunk}"
        ] + [f"{Colors.RESET}  => {suggestion}{Colors.RESET}" for suggestion in self.suggestions])

    def __str__(self) -> str:
        return self.format()

class Unsafe(Safe):
    _major_color = Colors.BOLD_RED


def is_main_branch(branch: git.Head) -> bool:
    return branch.path in ('refs/heads/main', 'refs/heads/master')


def describe_commit_one_line(c: git.Commit) -> str:
    return f"{c.hexsha} {c.committed_datetime} {c.committer}: {c.summary}"


def repository_safe_to_delete(repo: git.Repo, fetch=True) -> Generator[Safe | Unsafe, None, None]:
    repo_logger = logger.getChild(str(repo.git_dir))

    repo_logger.debug("starting vvvv")
    if repo.is_dirty(untracked_files=True, working_tree=True, index=True):
        if repo.untracked_files:
            yield Unsafe(
                repo,
                "Untracked files in working directory",
                repo.untracked_files[:10]
            )
        else:
            yield Unsafe(repo, "Repo is dirty.", ("Run git status for details.",))
    
    if fetch:
        for r in repo.remotes:
            # fetch up to date information for each remote.
            # this might download data. Oh well.
            repo_logger.info(f"Fetching remote {r=}")
            r.fetch(verbose=True)  # needs network access to update

    pretend_deleted_local_branches: list[git.Head] = []

    for subject_branch in repo.branches:

        if is_main_branch(subject_branch):
            # special case two branches we probably never want to consider "branched"
            continue

        for possibly_merged_into_branch in sorted(repo.branches, key=is_main_branch, reverse=True):  # sort main first
            if subject_branch == possibly_merged_into_branch:
                continue  # that's us, skip

            if possibly_merged_into_branch in pretend_deleted_local_branches:
                continue  # already pretend-deleted, so it's not a safe place to keep commits

            subject_branch_commits = list(repo.iter_commits(f"{possibly_merged_into_branch.path}..{subject_branch.path}"))

            if subject_branch_commits == []:
                yield Safe(
                    repo,
                    f"delete branch {subject_branch.path} @ {subject_branch.commit} - also on {possibly_merged_into_branch.path}",
                    [
                        f"git branch --points-at {possibly_merged_into_branch.name}",
                        f"git branch --verbose -d {subject_branch.name}",
                    ]
                )
                pretend_deleted_local_branches.append(subject_branch)
                break

    if pretend_deleted_local_branches:
        repo_logger.debug(f"{pretend_deleted_local_branches=}")

    for b in repo.branches:

        bl = repo_logger.getChild(f"branch={b.name}")

        tracking_branch = b.tracking_branch()
        if not tracking_branch:
            # is this branch a simple rename of or fully contained in some other branch?
            if b not in pretend_deleted_local_branches:
                yield Unsafe(
                    repo,
                    f"Local branch {b.name} is not known to remotes, and has commits.",
                    [r.url for r in repo.remotes] + [describe_commit_one_line(b.commit)]
                )
            continue

        # branch b tracks remote branch
        if tracking_branch.commit == b.commit:
            # common & fast path
            bl.info(f"Branch {b.path} and remote {tracking_branch.path} point to same commit {b.commit}")
            continue

        bl.info(f"Local branch {b.path} points to commit {b.commit}")
        bl.info(f"Remote branch {tracking_branch.path} points to commit {tracking_branch.commit}")

        # refs point to different commits.
        # is one ahead of the other? Or did they diverge?

        remote_has_commits_we_dont_have = list(repo.iter_commits(f"{b.path}..{tracking_branch.path}"))
        if remote_has_commits_we_dont_have:
            bl.info(f"{tracking_branch.path=} has commits we don't have on {b.path}: {remote_has_commits_we_dont_have}")

        we_have_commits_remote_doesnt_have = list(repo.iter_commits(f"{tracking_branch.path}..{b.path}"))
        if we_have_commits_remote_doesnt_have:
            yield Unsafe(
                repo,
                f"Local branch {b.path} has commits that {tracking_branch.path} lacks.",
                [
                    f"git log {tracking_branch.path}..{b.path}"
                ] + [
                    describe_commit_one_line(c) for c in we_have_commits_remote_doesnt_have
                ]
            )
        elif not is_main_branch(b):
            # don't bother saying that main could be deleted
            yield Safe(
                repo,
                f"Local branch {b.path} is behind {tracking_branch.path}.",
                [
                    f"git branch --all --contains {b.commit}"
                ]
            )
        try:
            latest_commits = list(repo.iter_commits(rev=b, since="2.days.ago", date_order=True, max_count=5))
        except ValueError:
            # does not have any commits yet
            latest_commits = []

        if latest_commits:
            lc = latest_commits[0]
            age_ago: timedelta = datetime.now(tz=timezone.utc) - lc.committed_datetime
            hours_ago = int(age_ago.total_seconds()/3600)
            if age_ago < timedelta(days=2):
                yield Unsafe(
                    repo,
                    f"Branch {b} might be active - last commit was {hours_ago} hours ago.",
                    [describe_commit_one_line(c) for c in latest_commits]
                )
            else:
                yield Safe(
                    repo,
                    f"Branch {b} might be inactive - last commit was {hours_ago} hours ago.",
                    [describe_commit_one_line(c) for c in latest_commits]
                )

    repo_logger.debug("finished ^^^^")


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("directory", nargs="*", default=["."], help="GIT_DIR. Default current directory.")
    parser.add_argument("--color", choices=("never", "always", "auto"), default="auto")
    parser.add_argument("--debug", action="store_true", help="Exact git commands and decisions.")
    parser.add_argument("--quiet", "-q", "-s", action="store_true", help="Just safe/not, no justification.")
    parser.add_argument("--skip-unknown-directories", action="store_true", help="If a passed directory isn't a git repo, skip it. Not considered a failure.")
    parser.add_argument("--no-fetch", dest="fetch_remotes", action="store_false", help="Don't connect to any configured remotes. Local cache might be old.")
    parser.add_argument("--no-search-parent", dest="search_parent_directories", action="store_false", help="Normally search parent for .git. If set, fail instead.")

    args: Namespace = parser.parse_args()

    if args.color == "auto":
        args.color = "always" if Colors.can(sys.stdout) else "never"
    if args.color == "never":
        Colors.disable()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING)
    logger.root.name = parser.prog

    exit_code = 0

    def p(*_args, **_kwargs):
        """Print only if not quiet."""
        if not args.quiet:
            print(*_args, **_kwargs)


    repo_objects: list[git.Repo] = []
    repo_directory: os.PathLike[str]
    for repo_directory in args.directory:
        try:
            repo_objects.append(
                git.Repo(repo_directory, search_parent_directories=args.search_parent_directories)
            )
        except git.InvalidGitRepositoryError:
            if args.skip_unknown_directories:
                logger.warning(f"{repo_directory}: .git not found. Skipping.")
                continue
            parser.error(f"{repo_directory}: .git not found. Run from inside a cloned repository or pass on command-line.")
    
    for repo in repo_objects:
        safe_to_delete_repo = True

        assert repo
        simple_repo_pathname: git.PathLike = repo.working_dir or repo.git_dir

        print(f"{Colors.BOLD}{simple_repo_pathname}{Colors.RESET}")

        with repo: # cleanup open files
            reasons = repository_safe_to_delete(repo, fetch=args.fetch_remotes)

        for reason in reasons:
            if isinstance(reason, Unsafe):
                safe_to_delete_repo = False
                exit_code = 1

            p(indent(str(reason), prefix=f" {Colors.BOLD_BLUE}|{Colors.RESET} "))

        p("")  # add a newline if not quiet

        if safe_to_delete_repo:
            print(f"It's safe to delete repo directory: {simple_repo_pathname}")
        else:
            print(f"Not safe to delete repo: {simple_repo_pathname}")

        print()
    return exit_code

if __name__ == "__main__":
    raise SystemExit(main())
