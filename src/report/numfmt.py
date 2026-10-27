"""Number formatting shared by the report sections."""

from __future__ import annotations

INF = float("inf")


def num(x: float | None) -> str:
    """Result number: enough digits to read small ratios and large forces alike."""
    if x is None:
        return "-"
    if x == INF:
        return "inf"
    a = abs(x)
    if a >= 1000:
        return f"{x:,.0f}"
    if a >= 10:
        return f"{x:,.1f}"
    return f"{x:,.3f}"


def snum(x: float | str) -> str:
    """Calculation-step result: a little more precision on small values (factors, ratios)."""
    if isinstance(x, str):
        return x
    if x == INF:
        return "inf"
    if x == int(x) and abs(x) < 1e9:
        return f"{int(x):,}"
    a = abs(x)
    if a >= 1000:
        return f"{x:,.0f}"
    if a >= 100:
        return f"{x:,.1f}"
    if a >= 1:
        return f"{x:,.3f}"
    return f"{x:.4f}"


def inum(x: float) -> str:
    """Input value: shown as entered, with padding zeros dropped (10.0 -> 10, 1/32 -> 0.03125)."""
    return f"{x:,.5f}".rstrip("0").rstrip(".")


def ratio(x: float) -> str:
    """A drift ratio such as 0.0025 shown as the app's denominator form, 'h / 400'."""
    return f"h / {1 / x:,.0f}" if x > 0 else str(x)


def with_unit(x: float | None, unit: str) -> str:
    return "-" if x is None else f"{num(x)} {unit}".rstrip()


def dcr(x: float | None) -> str:
    if x is None:
        return "-"
    return "inf" if x == INF else f"{x:.2f}"
