"""Repo Scout: static, checkable evidence about a public GitHub repository."""

# The one place the version is written. `pyproject.toml` reads it from here, so
# a build cannot disagree with the running code.
#
# It used to be read the other way round, from installed distribution metadata,
# which reported `0+unknown` from a fresh clone and -- worse -- in a zipapp
# reported whatever version of `repo-scout` happened to be installed in the
# environment instead of the code actually executing. A sibling tool in this
# portfolio shipped 0.2.0 announcing itself as 0.1.0 because the number was
# written twice; there were three copies here.
__version__ = "0.2.0"

__all__ = ["__version__"]
