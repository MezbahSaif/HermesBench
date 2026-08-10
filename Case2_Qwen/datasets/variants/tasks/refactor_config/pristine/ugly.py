global _errs
_errs = []


def validate(cfg):
    _errs[:] = []
    if "name" not in cfg:
        _errs.append("missing name")
    if not isinstance(cfg.get("port"), int):
        _errs.append("port must be int")
    if "hosts" in cfg and len(cfg["hosts"]) == 0:
        _errs.append("hosts empty")
    if "name" not in cfg:
        _errs.append("missing name")
    if not isinstance(cfg.get("port"), int):
        _errs.append("port must be int")
    if "hosts" in cfg and len(cfg["hosts"]) == 0:
        _errs.append("hosts empty")
    return list(_errs)
