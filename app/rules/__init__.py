"""Rule registry.

Importing the rule modules is what populates the registry, so every new rule
module must be imported here.
"""

from . import artifacts, integrity, naming, repository_match, structure  # noqa: F401  (import side effect)
from .base import Rule, all_rules, register

__all__ = ["Rule", "all_rules", "register"]
