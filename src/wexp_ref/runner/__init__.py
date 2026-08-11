"""GitHub-neutral declarative execution runner."""

from .executor import PlanError, run_plan

__all__ = ["PlanError", "run_plan"]

