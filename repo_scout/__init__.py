"""Repo Scout: static, checkable evidence about a public GitHub repository."""

from importlib import metadata

try:
    # Read the version from the installed distribution rather than repeating it
    # here. A sibling tool in this portfolio shipped 0.2.0 announcing itself as
    # 0.1.0 because the number was written in two places; there were three here.
    __version__ = metadata.version("repo-scout")
except metadata.PackageNotFoundError:  # pragma: no cover - running from a tree
    __version__ = "0+unknown"

__all__ = ["__version__"]
