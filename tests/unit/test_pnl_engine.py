import pytest
from core.pnl_engine import RealTimePnLEngine
from models import Trade, Position

@pytest.mark.unit
class TestRealTimePnLEngine:
    """Unit tests for RealTimePnLEngine
    """
    
    @pytest.fixture
    def engine(self):
        return RealTimePnLEngine(account_id="test_account")
    
    def test_initial_state_empty(self, engine):
        """Test: engine starts with zero positions and PnL"""
        assert engine.get_total_pnl() == 0.0
        assert len(engine.positions) == 0
        assert len(engine.realized_pnl) == 0
        assert len(engine.last_prices) == 0
    
    def test_on_trade_buy_creates_position(self, engine):
        """Test: buying 100@150 creates Position object"""
        trade = Trade(symbol="AAPL", qty=100, price=150.0)
        engine.on_trade(trade)
        
        pos: Position = engine.get_position("AAPL")
        assert pos.symbol == "AAPL"
        assert pos.qty == 100
        assert pos.avg_cost == 150.0
        assert pos.is_long()
        assert not pos.is_short()
    
    def test_position_object_attributes(self, engine):
        """Test: Position object attributes"""
        
        trade = Trade(symbol="AAPL", qty=100, price=150.0)
        engine.on_trade(trade)
        
        pos: Position = engine.get_position("AAPL")
        assert pos.account_id == "test_account"
        assert pos.symbol == "AAPL"
        assert pos.position_id is not None
        assert pos.updated_at is not None
    
