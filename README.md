# git unneeded

Determine whether we don't need this clone (or some of its branches) anymore.

If a branch has been pushed/merged, we don't need to keep it.


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
