"""Configuration validator module."""


def _check_name(cfg):
    """Check if 'name' key exists in config.

    Args:
        cfg: Configuration dictionary to validate.

    Returns:
        List of error messages (empty if validation passes).
    """
    errors = []
    if "name" not in cfg:
        errors.append("missing name")
    return errors


def _check_port(cfg):
    """Check if 'port' value is an integer.

    Args:
        cfg: Configuration dictionary to validate.

    Returns:
        List of error messages (empty if validation passes).
    """
    errors = []
    if not isinstance(cfg.get("port"), int):
        errors.append("port must be int")
    return errors


def _check_hosts(cfg):
    """Check if 'hosts' key exists and is non-empty.

    Args:
        cfg: Configuration dictionary to validate.

    Returns:
        List of error messages (empty if validation passes).
    """
    errors = []
    if "hosts" in cfg and len(cfg["hosts"]) == 0:
        errors.append("hosts empty")
    return errors


def validate(cfg):
    """Validate configuration dictionary.

    Performs comprehensive validation on the provided config by checking
    name, port, and hosts fields through dedicated helper functions.

    Args:
        cfg: Configuration dictionary to validate.

    Returns:
        List of error messages found during validation. Empty if valid.
    """
    errors = []

    errors.extend(_check_name(cfg))
    errors.extend(_check_port(cfg))
    errors.extend(_check_hosts(cfg))

    return errors
