from models import Trade, Position

class RealTimePnLEngine:
    """Real-time PnL attribution with realized/unrealized split
    """
    
    def __init__(self, account_id: str = "system"):
        self.account_id = account_id
        self.positions: dict[str, Position] = {}
        self.realized_pnl: dict[str, float] = {}
        self.last_prices: dict[str, float] = {}
        
    def on_trade(self, trade: Trade):
        """Update position and realized PnL"""
        
        sym, qty, px = trade.symbol, trade.qty, trade.price
        
        if sym not in self.positions:
            self.positions[sym] = Position(account_id=self.account_id, symbol=sym)
        
        pos = self.positions[sym]
        prev_qty = pos.qty
        prev_cost = pos.avg_cost
        
        # Same Direction: Weighted Avg Cost
        if prev_qty * qty >= 0:
            new_qty = prev_qty + qty
            if new_qty != 0:
                pos.avg_cost = (prev_qty * prev_cost + qty * px) / new_qty
        
        # Opposite Direction: Realized PnL
        else:
            closing_qty = min(abs(prev_qty), abs(qty))
            self.realized_pnl[sym] = self.realized_pnl.get(sym, 0.0) + closing_qty * (px - prev_cost)
        
        pos.qty = prev_qty + qty
    
    def on_price(self, symbol: str, price: float):
        """Update latest market price"""
        self.last_prices[symbol] = price
        
    def get_position(self, symbol: str) -> Position:
        return self.positions.get(symbol, Position(account_id=self.account_id, symbol=symbol))
    
    def get_unrealized_pnl(self, symbol: str) -> float:
        """Compute unrealized PnL for symbol"""
        pos = self.get_position(symbol)
        
        if pos.qty == 0:
            return 0.0
        last_px = self.last_prices.get(symbol)
        if last_px is None:
            return 0.0
        return pos.unrealized_pnl(last_px)
    
    def get_total_pnl(self) -> float:
        """Total realized + unrealized PnL across all symbols"""
        return (
            sum(
                self.realized_pnl.get(sym, 0.0) + 
                self.get_unrealized_pnl(sym)
                for sym in self.positions)
            )
