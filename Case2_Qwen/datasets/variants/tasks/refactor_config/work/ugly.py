def validate(cfg):
    errs = []
    if "name" not in cfg:
        errs.append("missing name")
    if not isinstance(cfg.get("port"), int):
        errs.append("port must be int")
    if "hosts" in cfg and len(cfg["hosts"]) == 0:
        errs.append("hosts empty")
    return errs
