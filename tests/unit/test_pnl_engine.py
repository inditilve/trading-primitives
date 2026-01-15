import pytest
from core.pnl_engine import RealTimePnLEngine
from models import Trade, Position

@pytest.mark.unit
class TestRealTimePnLEngine:
    """Unit tests for RealTimePnLEngine
    """
    
    @pytest.fixture
    def engine(self) -> RealTimePnLEngine:
        return RealTimePnLEngine(account_id="test_account")
    
    def test_initial_state_empty(self, engine: RealTimePnLEngine):
        """Test: engine starts with zero positions and PnL"""
        assert engine.get_total_pnl() == 0.0
        assert len(engine.positions) == 0
        assert len(engine.realized_pnl) == 0
        assert len(engine.last_prices) == 0
    
    def test_on_trade_buy_creates_position(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Test: buying 100@150 creates Position object"""
        engine.on_trade(sample_trade)
        
        pos: Position = engine.get_position("AAPL")
        assert pos.symbol == "AAPL"
        assert pos.qty == sample_trade.qty
        assert pos.avg_cost == sample_trade.price
        assert pos.is_long()
        assert not pos.is_short()
    
    def test_position_object_attributes(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Test: Position object attributes"""
        engine.on_trade(sample_trade)
        
        pos: Position = engine.get_position("AAPL")
        assert pos.account_id == "test_account"
        assert pos.symbol == "AAPL"
        assert pos.position_id is not None
        assert pos.updated_at is not None
        
    def test_on_trade_same_direction_updates_wavg_cost(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Test: buying more increases qty and updates avg cost"""
        trade_buy_more = Trade(symbol="AAPL", qty=50, price=160.0)
        
        engine.on_trade(sample_trade)
        engine.on_trade(trade_buy_more)
        
        pos: Position = engine.get_position("AAPL")
        assert pos.qty == 150
        assert pos.avg_cost == (sample_trade.notional_value() + 50 * 160.0) / sample_trade.price
    
    def test_on_trade_opposite_direction_realizes_pnl(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Test: selling at profit realizes PnL and closes position"""
        trade_sell = Trade(symbol="AAPL", qty=-sample_trade.qty, price=160.0)
        
        engine.on_trade(sample_trade)
        engine.on_trade(trade_sell)
        
        pos: Position = engine.get_position("AAPL")
        assert pos.qty == 0
        
        realized_pnl = engine.realized_pnl["AAPL"]
        assert realized_pnl == sample_trade.qty * (160.0 - sample_trade.price)
    
    def test_on_price_updates_last_price_and_unrealized_pnl(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Test: updating price computes unrealized PnL correctly"""
        engine.on_trade(sample_trade)
        engine.on_price("AAPL", 160.0)
        
        unrealized_pnl = engine.get_unrealized_pnl("AAPL")
        assert unrealized_pnl == sample_trade.qty * (160.0 - sample_trade.price)
        assert engine.last_prices["AAPL"] == 160.0
        
    def test_get_total_pnl_combines_realized_and_unrealized(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Test: total PnL sums realized and unrealized correctly"""
        trade_sell_partial = Trade(symbol="AAPL", qty=-50, price=160.0)
        
        engine.on_trade(sample_trade)  # Buy 100@150
        engine.on_trade(trade_sell_partial)  # Sell 50@160
        engine.on_price("AAPL", 155.0)  # Update price to 155
        
        realized_pnl = engine.realized_pnl["AAPL"]
        expected_realized_pnl = 50 * (160.0 - sample_trade.price)
        assert realized_pnl == expected_realized_pnl
        
        unrealized_pnl = engine.get_unrealized_pnl("AAPL")
        expected_unrealized_pnl = 50 * (155.0 - sample_trade.price)
        assert unrealized_pnl == expected_unrealized_pnl
        
        total_pnl = engine.get_total_pnl()
        expected_total_pnl = expected_realized_pnl + expected_unrealized_pnl
        assert total_pnl == expected_total_pnl
    
    def test_on_trade_flips_position_direction(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Test: selling more than current position flips direction and updates avg cost"""
        trade_sell_more = Trade(symbol="AAPL", qty=-150, price=160.0)
        
        engine.on_trade(sample_trade)  # Buy 100@150
        engine.on_trade(trade_sell_more)  # Sell 150@140
        
        pos: Position = engine.get_position("AAPL")
        assert pos.qty == -50  # Short 50 shares
        assert pos.is_short()
        assert pos.avg_cost == 160.0  # New avg cost is sell price
        
        realized_pnl = engine.realized_pnl["AAPL"]
        assert realized_pnl == 100 * (160.0 - 150.0)
        
        trade_buy_more = Trade(symbol="AAPL", qty=100, price=155.0)
        engine.on_trade(trade_buy_more)  # Buy 100@155 to cover and go long
        pos = engine.get_position("AAPL")
        assert pos.qty == 50  # Long 50 shares
        assert pos.is_long()
        assert pos.avg_cost == 155.0  # New avg cost is buy price
        realized_pnl = engine.realized_pnl["AAPL"]
        assert realized_pnl == 100 * (160.0 - 150.0) + 50 * (160.0 - 155.0)
        
        