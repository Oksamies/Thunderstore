from __future__ import annotations

import re
from functools import total_ordering
from typing import Tuple, Union

# Package version numbers are always strict major.minor.patch (see
# PACKAGE_VERSION_REGEX in consts.py). This module replaces the removed
# distutils.version.StrictVersion: for these inputs StrictVersion ordering is
# identical to integer-tuple ordering, so comparisons are preserved exactly.
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


@total_ordering
class PackageVersionNumber:
    """A strict major.minor.patch version number.

    Drop-in replacement for the distutils StrictVersion usage this codebase
    relied on, restricted to the exact ``\\d+.\\d+.\\d+`` format it enforces.
    Raises ValueError on any other input (matching StrictVersion's contract).
    """

    __slots__ = ("version",)

    def __init__(self, version: Union[str, "PackageVersionNumber"]):
        if isinstance(version, PackageVersionNumber):
            self.version: Tuple[int, ...] = version.version
            return
        if not isinstance(version, str) or not _VERSION_RE.match(version):
            raise ValueError(f"Invalid version number: {version!r}")
        self.version = tuple(int(part) for part in version.split("."))

    def __str__(self) -> str:
        return ".".join(str(part) for part in self.version)

    def __repr__(self) -> str:
        return f"PackageVersionNumber('{self}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PackageVersionNumber):
            return NotImplemented
        return self.version == other.version

    def __lt__(self, other: "PackageVersionNumber") -> bool:
        if not isinstance(other, PackageVersionNumber):
            return NotImplemented
        return self.version < other.version

    def __hash__(self) -> int:
        return hash(self.version)
