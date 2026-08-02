global _rate
_rate = 0.075


def process(rows):
    total = 0.0
    lines = []
    for r in rows:
        p = r.split(",")
        q = int(p[2])
        price = float(p[3])
        total += q * price
        lines.append(p[1] + " x" + str(q) + " @ " + str(price))
    tax = round(total * _rate, 2)
    lines.append("TAX " + str(tax))
    lines.append("TOTAL " + str(round(total + tax, 2)))
    dup = []
    for l in lines:
        dup.append(l.upper() if l.startswith("T") else l)
    return dup
