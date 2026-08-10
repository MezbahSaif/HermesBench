global _counts
_counts = {}


def summarize(lines):
    _counts.clear()
    for line in lines:
        lvl = line.split(" ")[1]
        _counts[lvl] = _counts.get(lvl, 0) + 1
    top = []
    for k in sorted(_counts):
        top.append(k + ":" + str(_counts[k]))
    return top
