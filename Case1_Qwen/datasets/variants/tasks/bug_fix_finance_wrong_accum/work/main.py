"""Invoice processing utilities.

Provides parsing and totals for a small invoicing tool.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class LineItem:
    sku: str
    name: str
    qty: int
    unit_price: float


def parse_lines(rows: list[str]) -> list[LineItem]:
    """Parse 'sku,name,qty,price' rows into LineItem objects.

    Malformed rows are skipped.
    """
    items = []
    for row in rows:
        parts = [p.strip() for p in row.split(",")]
        if len(parts) != 4:
            continue
        try:
            items.append(LineItem(parts[0], parts[1], int(parts[2]),
                                  float(parts[3])))
        except ValueError:
            continue
    return items


def compute_subtotal(items: list[LineItem]) -> float:
    total = 0.0
    for it in items:
        total += it.unit_price * it.qty
    return round(total, 2)


def apply_bulk_discount(subtotal: float, min_amount: float = 500.0,
                        rate: float = 0.10) -> float:
    """Subtotals at or above min_amount get rate % off."""
    if subtotal >= min_amount:
        return round(subtotal * (1.0 - rate), 2)
    return round(subtotal, 2)


def compute_tax(amount: float, tax_rate: float = 0.075) -> float:
    return round(amount * tax_rate, 2)
