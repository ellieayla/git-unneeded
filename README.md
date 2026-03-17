# git unneeded

## Install

Via `uv`:

```sh
<!-- [[[cog
import cog
from subprocess import check_output
repo = check_output(["git", "remote", "get-url", "origin"], text=True).strip()
version = check_output(["git", "describe", "--tags", "--abbrev=0"], text=True).strip()
git_url_with_tag = "git+%s@%s" % (repo, version)
help = check_output(["uv", "tool", "run", git_url_with_tag, "--help"], text=True)
cog.out("uv tool install %s" % git_url_with_tag)
]]] -->
uv tool install git+https://github.com/ellieayla/git-unneeded@v1.0.0
<!-- [[[end]]] -->
```

## Usage

```sh
git unneeded -h
<!-- [[[cog
cog.out(help)
]]]> -->
<!-- [[[end]]] -->
```
