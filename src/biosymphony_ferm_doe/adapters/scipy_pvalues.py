"""SciPy adapter — real t and F distributions for analysis and doe_power.

Replaces the normal approximation used by the stdlib path with proper
Student-t and F distributions. Most useful for small designs (n < 30)
where the normal approximation's z-quantiles understate the critical
value and lead to optimistic MDEs / p-values.

Public API:

- :func:`t_test_two_sided_pvalue` (df, t_stat) → float p-value
- :func:`f_test_pvalue` (f_stat, df_num, df_den) → float p-value
- :func:`t_critical` (alpha, df) → float critical value at level α (two-sided)
- :func:`is_available()` → bool, returns True iff scipy.stats is importable

The module imports ``scipy.stats`` lazily; raising ``ImportError`` at the
top level would defeat the optional-adapter pattern (the parent
``adapters/__init__.py`` catches ``ImportError`` from this module on first
use and returns ``None``).
"""

from __future__ import annotations

from scipy import stats  # noqa: F401  fail at import time if scipy missing


def t_test_two_sided_pvalue(t_stat: float, df: int) -> float:
    """Two-sided p-value for the t-statistic at the given residual df."""
    if df <= 0:
        return float("nan")
    return float(2 * (1 - stats.t.cdf(abs(t_stat), df)))


def f_test_pvalue(f_stat: float, df_num: int, df_den: int) -> float:
    """One-sided p-value for the F-statistic (lack-of-fit and similar)."""
    if df_num <= 0 or df_den <= 0:
        return float("nan")
    return float(1 - stats.f.cdf(f_stat, df_num, df_den))


def t_critical(alpha: float, df: int) -> float:
    """Two-sided t critical value at significance ``alpha`` and ``df``."""
    if df <= 0:
        return float("nan")
    return float(stats.t.ppf(1 - alpha / 2, df))


def normal_quantile(p: float) -> float:
    """``z`` such that ``P(Z <= z) = p`` for standard normal Z."""
    return float(stats.norm.ppf(p))


def is_available() -> bool:
    return True


__all__ = ["t_test_two_sided_pvalue", "f_test_pvalue", "t_critical", "normal_quantile", "is_available"]
