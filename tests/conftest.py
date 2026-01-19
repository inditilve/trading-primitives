import pytest

from models import Side, Trade


@pytest.fixture
def sample_trade() -> Trade:
    """Standard buy trade for testing"""
    return Trade(
        symbol="AAPL",
        side=Side.BUY,
        qty=100,
        price=150.0,
    )
