"""Exceptions raised by the cs2_inspect package."""

from __future__ import annotations


class MalformedInspectLinkError(ValueError):
    """Raised when an inspect URL or hex payload fails validation.

    Inherits from ValueError for backward compatibility with callers that
    catch ``ValueError``.
    """
