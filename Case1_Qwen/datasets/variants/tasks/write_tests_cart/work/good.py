class Cart:
    def __init__(self):
        self.items = []

    def add(self, sku: str, price: float, qty: int = 1) -> None:
        self.items.append((sku, price, qty))

    def total(self) -> float:
        raw = sum(p * q for _, p, q in self.items)
        return round(raw, 2)

    def apply_promo(self, code: str) -> float:
        base = self.total()
        if code == "SAVE10":
            return round(base * 0.9, 2)
        if code == "SAVE50":
            return round(base * 0.5, 2)
        return base
