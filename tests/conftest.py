import pytest
from unittest.mock import MagicMock
from models import Trade, Position

@pytest.fixture
def sample_trade() -> Trade:
    return Trade(symbol="AAPL", qty=100, price=150.0)

@pytest.fixture
def sample_position() -> Position:
    return Position(account_id="PM1", symbol="AAPL", qty=100, avg_cost=150.0)

@pytest.fixture
def mock_logger() -> MagicMock:
    return MagicMock()
