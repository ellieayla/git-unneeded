# git unneeded

Did you clone a large amount of git repos? Is `~/workspace/` a giant mess? Need to declutter?

If a remote exists and all branches have been pushed (or merged), and you trust the remote git host to stay up, maybe we don't need to keep the local copy. If a branch has been pushed/merged, we don't need to keep them.

But if there's local branch refs for commits that have _never been pushed_, maybe they should be pushed first. Or at least reviewed.

`git unneeded` will report whether deleting branches/repo would be safe, or whether there's stuff that needs attention. Doesn't delete anything for you. Can be happily run with a giant shell glob or from xargs.


## Install

With uv: `uv tool install git-unneeded`

With pipx: `pipx install git-unneeded`


## Usage

```sh
git unneeded -h
```
<!-- [[[cog
    import os
    os.environ["COLUMNS"] = "80"
    from argparse_help_markdown import run
    run(filename="git_unneeded.py", include_usage=True, writer=None)
]]] -->
```
usage: git_unneeded.py [-h] [--color {never,always,auto}] [--debug] [--quiet]
                       [--oneline] [--skip-unknown-directories] [--no-fetch]
                       [--no-search-parent]
                       [directory ...]
```

| Options | Values  | Help |
| ------- | ------- | ---- |
| *positional arguments* | |
| <pre>directory</pre> | Default: `.` | GIT\_DIR. Default current directory. |
| *options* | |
| <pre>-h --help</pre> | Flag. | show this help message and exit |
| <pre>--color</pre> | Choice: `never`, `always`, `auto`<br/>Default: `auto` |  |
| <pre>--debug</pre> | Flag. | Exact git commands and decisions. |
| <pre>--quiet -q -s</pre> | Flag. | Just safe/not, no justification. |
| <pre>--oneline</pre> | Flag. | Just output directory\\0True. Implies --quiet. |
| <pre>--skip-unknown-directories</pre> | Flag. | If a passed directory isn\'t a git repo, skip it. Not considered a failure. |
| <pre>--no-fetch</pre> | Flag. | Don\'t connect to any configured remotes. Local cache might be old. |
| <pre>--no-search-parent</pre> | Flag. | Don\'t search up parent directories for .git. |
<!-- [[[end]]] -->

So for the annoying case of too many repos;

```sh
$ find ~/workspace -maxdepth 2 -name .git -type d -print0 | xargs -0 git unneeded --no-fetch
```
