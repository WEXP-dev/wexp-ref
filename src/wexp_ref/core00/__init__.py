"""Revision-scoped support for the first published Core -00 vector slice."""

from wexp_ref.core00.evaluator import Core00InputError, evaluate
from wexp_ref.core00.package import PackageError, run_package

__all__ = ["Core00InputError", "PackageError", "evaluate", "run_package"]
