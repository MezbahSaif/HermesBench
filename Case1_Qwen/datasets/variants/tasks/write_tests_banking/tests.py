"""
Tests for Account class - validates correct implementation (pristine/good.py)
and catches bugs in work/buggy.py.

Key difference detected between good.py and buggy.py:
- good.transfer() calls self.withdraw(amount) first, validating sufficient funds
  before moving money. This raises ValueError on insufficient funds.
- buggy.transfer() just adds to recipient's balance without checking sender's
  balance, so transfers with insufficient funds silently succeed (wrong).
"""


def _load_module(path: str, name: str):
    """Load a module from a file path with a unique name to avoid conflicts."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_account(code: str):
    """Create an Account from the work/buggy.py module."""
    buggy = _load_module(
        __import__("os").path.join(__file__.rsplit("tests", 1)[0], "work", "buggy.py"),
        f"test_bug_{code}",
    )
    return buggy.Account("Alice")


def test_deposit_and_withdraw():
    """Test basic deposit and withdraw functionality."""
    a = _make_account("DEPO")
    assert a.deposit(10.0) == 10.0
    assert a.withdraw(5.0) == 5.0

    b = _make_account("WITHD")
    assert b.deposit(100.0) == 100.0
    assert b.withdraw(30.0) == 70.0


def test_deposit_validation():
    """Deposit with invalid amounts should raise ValueError."""
    a = _make_account("DEPZERO")
    try:
        a.deposit(0.0)
        assert False, "Expected ValueError for zero deposit"
    except ValueError as e:
        assert "must be positive" in str(e)

    b = _make_account("DEPNEG")
    try:
        b.deposit(-5.0)
        assert False, "Expected ValueError for negative deposit"
    except ValueError as e:
        assert "must be positive" in str(e)


def test_withdraw_insufficient_funds_raises():
    """Withdraw with insufficient funds should raise ValueError."""
    a = _make_account("WITHDINSUFF")
    try:
        a.deposit(10.0)
        a.withdraw(25.0)  # buggy doesn't check, good raises here
        assert False, "Expected ValueError for insufficient funds"
    except ValueError as e:
        assert "insufficient funds" in str(e)


def test_transfer_moves_funds_correctly():
    """Transfer should move money from sender to receiver."""
    a = _make_account("TRANS")
    b = _make_account("RECV")

    result = a.transfer(b, 30.0)
    assert a.balance == 70.0
    assert b.balance == 30.0


def test_transfer_insufficient_funds_raises():
    """Transfer with insufficient funds should raise ValueError."""
    a = _make_account("TRANSINSUFF")
    b = _make_account("RECV2")

    try:
        a.transfer(b, 25.0)  # buggy won't check, good raises here
        assert False, "Expected ValueError for insufficient funds in transfer"
    except ValueError as e:
        assert "insufficient funds" in str(e)


def test_transfer_preserves_return_value():
    """Transfer should return the sender's remaining balance."""
    a = _make_account("TRANSRET")
    b = _make_account("RECV3")

    result = a.transfer(b, 20.0)
    assert result == 80.0


def test_transfer_zero_amount_raises():
    """Transfer with zero amount should raise ValueError."""
    a = _make_account("TRANSFERO")
    b = _make_account("RECV4")

    try:
        a.transfer(b, 0.0)
        assert False, "Expected ValueError for zero transfer"
    except ValueError as e:
        assert "must be positive" in str(e)


def test_transfer_negative_amount_raises():
    """Transfer with negative amount should raise ValueError."""
    a = _make_account("TRANSNEG")
    b = _make_account("RECV5")

    try:
        a.transfer(b, -10.0)
        assert False, "Expected ValueError for negative transfer"
    except ValueError as e:
        assert "must be positive" in str(e)


def test_transfer_exact_balance():
    """Transfer of exact balance should work correctly."""
    a = _make_account("EXACT")
    b = _make_account("RECV6")

    result = a.transfer(b, 100.0)
    assert a.balance == 0.0
    assert b.balance == 100.0
    assert result == 0.0


if __name__ == "__main__":
    test_deposit_and_withdraw()
    print("test_deposit_and_withdraw PASSED")

    test_deposit_validation()
    print("test_deposit_validation PASSED")

    test_withdraw_insufficient_funds_raises()
    print("test_withdraw_insufficient_funds_raises PASSED")

    test_transfer_moves_funds_correctly()
    print("test_transfer_moves_funds_correctly PASSED")

    test_transfer_insufficient_funds_raises()
    print("test_transfer_insufficient_funds_raises PASSED")

    test_transfer_preserves_return_value()
    print("test_transfer_preserves_return_value PASSED")

    test_transfer_zero_amount_raises()
    print("test_transfer_zero_amount_raises PASSED")

    test_transfer_negative_amount_raises()
    print("test_transfer_negative_amount_raises PASSED")

    test_transfer_exact_balance()
    print("test_transfer_exact_balance PASSED")

    print("\nAll tests passed!")
