import pytest
from core.pnl_engine import RealTimePnLEngine
from models import Trade, Position

@pytest.mark.unit
class TestRealTimePnLEngine:
    """Unit tests for RealTimePnLEngine"""
    
    @pytest.fixture
    def engine(self) -> RealTimePnLEngine:
        return RealTimePnLEngine(account_id="test_account")
    
    
    """Basic Tests"""
    def test_initial_state_empty(self, engine: RealTimePnLEngine):
        """Engine starts with zero positions and PnL"""
        assert engine.get_total_pnl() == 0.0
        assert len(engine.positions) == 0
        assert len(engine.realized_pnl) == 0
        assert len(engine.last_prices) == 0
    
    def test_on_trade_buy_creates_position(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Processing Trade creates Position object"""
        engine.on_trade(sample_trade)
        
        pos: Position = engine.get_position("AAPL")
        assert pos.symbol == "AAPL"
        assert pos.qty == sample_trade.qty
        assert pos.avg_cost == sample_trade.price
        assert pos.is_long()
        assert not pos.is_short()
    
    def test_position_object_attributes(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Position object attributes are set correctly"""
        engine.on_trade(sample_trade)
        
        pos: Position = engine.get_position("AAPL")
        assert pos.account_id == "test_account"
        assert pos.symbol == "AAPL"
        assert pos.position_id is not None
        assert pos.updated_at is not None
    
    def test_get_position_nonexistent_symbol(self, engine: RealTimePnLEngine):
        """Getting non-existent position returns empty Position"""
        pos = engine.get_position("NONEXIST")
        assert pos.qty == 0
        assert pos.avg_cost == 0.0

    
    """Same Direction Tests"""
    def test_on_trade_same_direction_updates_wavg_cost(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Buying more increases qty and updates avg cost"""
        trade_buy_more = Trade(symbol="AAPL", qty=50, price=160.0)
        
        engine.on_trade(sample_trade)
        engine.on_trade(trade_buy_more)
        
        pos: Position = engine.get_position("AAPL")
        assert pos.qty == 150
        assert pos.avg_cost == (sample_trade.notional_value() + 50 * 160.0) / sample_trade.price
    
    def test_same_direction_multiple_buys(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Multiple buys at different prices update weighted avg correctly"""
        engine.on_trade(sample_trade)
        engine.on_trade(Trade(symbol="AAPL", qty=50, price=160.0))
        engine.on_trade(Trade(symbol="AAPL", qty=50, price=140.0))
        
        pos = engine.get_position("AAPL")
        assert pos.qty == 200
        # (100*150 + 50*160 + 50*140) / 200 = 30000 / 200 = 150
        assert pos.avg_cost == 150.0
    
    def test_same_direction_short_sell_more(self, engine: RealTimePnLEngine):
        """Selling more when short updates weighted avg"""
        engine.on_trade(Trade(symbol="AAPL", qty=-100, price=160.0))
        engine.on_trade(Trade(symbol="AAPL", qty=-50, price=155.0))
        
        pos = engine.get_position("AAPL")
        assert pos.qty == -150
        assert pos.is_short()
        assert pos.avg_cost == (100 * 160.0 + 50 * 155.0) / 150
    
    def test_same_direction_no_realized_pnl(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Same direction trades don't realize PnL"""
        engine.on_trade(sample_trade)
        engine.on_trade(Trade(symbol="AAPL", qty=50, price=160.0))
        assert engine.realized_pnl["AAPL"] == 0.0
    
    
    """Opposite Direction Tests"""
    def test_on_trade_opposite_direction_realizes_pnl(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Selling at profit realizes PnL and closes position"""
        trade_sell = Trade(symbol="AAPL", qty=-sample_trade.qty, price=160.0)
        
        engine.on_trade(sample_trade)
        engine.on_trade(trade_sell)
        
        pos: Position = engine.get_position("AAPL")
        assert pos.qty == 0
        
        realized_pnl = engine.realized_pnl["AAPL"]
        assert realized_pnl == sample_trade.qty * (160.0 - sample_trade.price)
    
    def test_opposite_direction_sell_at_loss(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Selling at loss realizes negative PnL"""
        engine.on_trade(sample_trade)
        engine.on_trade(Trade(symbol="AAPL", qty=-sample_trade.qty, price=140.0))
        
        assert engine.realized_pnl["AAPL"] == sample_trade.qty * (140.0 - 150.0)
    
    def test_opposite_direction_short_cover_at_profit(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Covering short at lower price realizes profit"""
        engine.on_trade(Trade(symbol="AAPL", qty=-sample_trade.qty, price=160.0))
        engine.on_trade(sample_trade)
        
        assert engine.realized_pnl["AAPL"] == sample_trade.qty * (160.0 - sample_trade.price)
    
    def test_opposite_direction_partial_close(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Partial close realizes PnL on closed portion only"""
        engine.on_trade(sample_trade)
        engine.on_trade(Trade(symbol="AAPL", qty=-50, price=160.0))
        
        pos = engine.get_position("AAPL")
        assert pos.qty == 50
        assert pos.avg_cost == sample_trade.price  # Avg cost stays same
        assert engine.realized_pnl["AAPL"] == 50 * (160.0 - sample_trade.price)
    
    def test_opposite_direction_short_partial_cover(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Partially covering short position"""
        engine.on_trade(Trade(symbol="AAPL", qty=-100, price=150.0))
        engine.on_trade(Trade(symbol="AAPL", qty=50, price=145.0))
        
        pos = engine.get_position("AAPL")
        assert pos.qty == -50
        assert pos.avg_cost == 150.0  # Avg cost stays same
        assert engine.realized_pnl["AAPL"] == 50 * (150.0 - 145.0)
    
    
    """Direction Flip Tests"""
    def test_on_trade_flips_position_direction(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Selling more than current position flips direction and updates avg cost"""
        trade_sell_more = Trade(symbol="AAPL", qty=-150, price=160.0)
        
        engine.on_trade(sample_trade)  # Buy 100@150
        engine.on_trade(trade_sell_more)  # Sell 150@140
        
        pos: Position = engine.get_position("AAPL")
        assert pos.qty == -50  # Short 50 shares
        assert pos.is_short()
        assert pos.avg_cost == 160.0  # New avg cost is sell price
        
        realized_pnl = engine.realized_pnl["AAPL"]
        assert realized_pnl == sample_trade.qty * (160.0 - sample_trade.price)
        
        trade_buy_more = Trade(symbol="AAPL", qty=100, price=155.0)
        engine.on_trade(trade_buy_more)  # Buy 100@155 to cover and go long
        pos = engine.get_position("AAPL")
        assert pos.qty == 50  # Long 50 shares
        assert pos.is_long()
        assert pos.avg_cost == 155.0  # New avg cost is buy price
        realized_pnl = engine.realized_pnl["AAPL"]
        assert realized_pnl == sample_trade.qty * (160.0 - sample_trade.price) + 50 * (160.0 - 155.0)
    
    
    """Price Update Tests"""
    def test_on_price_updates_last_price_and_unrealized_pnl(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Updating price computes unrealized PnL correctly"""
        engine.on_trade(sample_trade)
        engine.on_price("AAPL", 160.0)
        
        unrealized_pnl = engine.get_unrealized_pnl("AAPL")
        assert unrealized_pnl == sample_trade.qty * (160.0 - sample_trade.price)
        assert engine.last_prices["AAPL"] == 160.0

    def test_on_price_short_position_unrealized_pnl(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Unrealized PnL for short position"""
        engine.on_trade(Trade(symbol="AAPL", qty=-sample_trade.qty, price=sample_trade.price))
        engine.on_price("AAPL", 140.0)
        
        unrealized_pnl = engine.get_unrealized_pnl("AAPL")
        assert unrealized_pnl == -sample_trade.qty * (140.0 - sample_trade.price)
        assert unrealized_pnl == sample_trade.qty * (sample_trade.price - 140.0)
    
    def test_on_price_zero_position_zero_unrealized_pnl(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Closed position has zero unrealized PnL"""
        engine.on_trade(sample_trade)
        engine.on_trade(Trade(symbol="AAPL", qty=-sample_trade.qty, price=160.0))
        engine.on_price("AAPL", 200.0)  # Price doesn't matter
        
        unrealized_pnl = engine.get_unrealized_pnl("AAPL")
        assert unrealized_pnl == 0.0


    """Total PnL Tests"""
    def test_get_total_pnl_combines_realized_and_unrealized(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Total PnL sums realized and unrealized correctly"""
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
    
    def test_get_total_pnl_multiple_symbols(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Total PnL across multiple symbols"""
        engine.on_trade(sample_trade)
        engine.on_trade(Trade(symbol="MSFT", qty=50, price=300.0))
        engine.on_trade(Trade(symbol="AAPL", qty=-sample_trade.qty, price=160.0))  # Close AAPL
        engine.on_price("MSFT", 310.0)
        
        aapl_realized = engine.realized_pnl["AAPL"]
        msft_unrealized = engine.get_unrealized_pnl("MSFT")
        total = engine.get_total_pnl()
        
        assert aapl_realized == 1000.0
        assert msft_unrealized == 500.0
        assert total == 1500.0
    
    def test_get_total_pnl_zero_when_no_positions(self, engine: RealTimePnLEngine):
        """Total PnL is zero with no positions"""
        assert engine.get_total_pnl() == 0.0
    
    """Multi-Symbol Tests"""
    def test_multiple_symbols_independent_positions(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Positions for different symbols are independent"""
        engine.on_trade(sample_trade)
        engine.on_trade(Trade(symbol="MSFT", qty=50, price=300.0))
        engine.on_trade(Trade(symbol="GOOGL", qty=-25, price=2000.0))
        
        aapl_pos = engine.get_position("AAPL")
        msft_pos = engine.get_position("MSFT")
        googl_pos = engine.get_position("GOOGL")
        
        assert aapl_pos.qty == sample_trade.qty
        assert msft_pos.qty == 50
        assert googl_pos.qty == -25
        assert aapl_pos.avg_cost == sample_trade.price
        assert msft_pos.avg_cost == 300.0
        assert googl_pos.avg_cost == 2000.0
    
    def test_multiple_symbols_independent_pnl(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """PnL calculations independent per symbol"""
        engine.on_trade(sample_trade)
        engine.on_trade(Trade(symbol="MSFT", qty=100, price=300.0))
        
        engine.on_trade(Trade(symbol="AAPL", qty=-sample_trade.qty, price=160.0))
        engine.on_price("MSFT", 310.0)
        
        assert engine.realized_pnl["AAPL"] == 1000.0
        assert engine.realized_pnl.get("MSFT", 0.0) == 0.0
        assert engine.get_unrealized_pnl("MSFT") == 1000.0
    
    """Filter and Summary Tests"""
    def test_get_long_positions(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Filter long positions only"""
        engine.on_trade(sample_trade)  # AAPL long
        engine.on_trade(Trade(symbol="MSFT", qty=-50, price=300.0))  # MSFT short
        
        long_pos = engine.get_long_positions()
        assert "AAPL" in long_pos
        assert "MSFT" not in long_pos

    def test_get_short_positions(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Filter short positions only"""
        engine.on_trade(sample_trade)  # AAPL long
        engine.on_trade(Trade(symbol="MSFT", qty=-50, price=300.0))  # MSFT short
        
        short_pos = engine.get_short_positions()
        assert "MSFT" in short_pos
        assert "AAPL" not in short_pos

    def test_get_pnl_by_symbol(self, engine: RealTimePnLEngine, sample_trade: Trade):
        """Get realized + unrealized breakdown for one symbol"""
        engine.on_trade(sample_trade)  # Buy 100@150
        engine.on_trade(Trade(symbol="AAPL", qty=-50, price=160.0))  # Sell 50@160
        engine.on_price("AAPL", 155.0)  # Mark at 155
        
        pnl = engine.get_pnl_by_symbol("AAPL")
        assert pnl["realized"] == 500.0  # 50 * (160 - 150)
        assert pnl["unrealized"] == 250.0  # 50 * (155 - 150)
        assert pnl["total"] == 750.0

    def test_get_total_notional(self, engine: RealTimePnLEngine):
        """Calculate total notional value across all positions"""
        engine.on_trade(Trade(symbol="AAPL", qty=100, price=150.0))
        engine.on_trade(Trade(symbol="MSFT", qty=50, price=300.0))
        
        last_prices = {"AAPL": 160.0, "MSFT": 310.0}
        total = engine.get_total_notional(last_prices)
        # AAPL: 100 * 160 = 16000
        # MSFT: 50 * 310 = 15500
        # Total: 31500
        assert total == 31500.0