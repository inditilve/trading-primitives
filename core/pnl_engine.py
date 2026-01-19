import logging
from collections import defaultdict

from models import Position, Trade

logger = logging.getLogger(__name__)


class RealTimePnLEngine:
    """Real-time PnL attribution with realized/unrealized split"""

    def __init__(self, account_id: str = "system"):
        self.account_id = account_id
        self.positions: dict[str, Position] = defaultdict(
            lambda: Position(account_id=self.account_id, symbol="")
        )
        self.realized_pnl: dict[str, float] = defaultdict(float)
        self.last_prices: dict[str, float] = defaultdict(float)
        logger.debug(f"RealTimePnLEngine initialized for account {account_id}")

    def on_trade(self, trade: Trade):
        """Update position and realized PnL"""

        # Validate trade
        if trade.qty == 0:
            logger.warning(f"Ignoring trade {trade.trade_id} with qty=0")
            return

        if trade.price < 0:
            logger.warning(f"Ignoring trade {trade.trade_id} with negative price")
            return

        sym, trade_qty, trade_price = trade.symbol, trade.qty, trade.price

        logger.info(
            f"Trade {trade.trade_id}: {sym} qty={trade_qty} price={trade_price:.2f} notional={trade.notional_value():.2f}"
        )

        if sym not in self.positions:
            self.positions[sym] = Position(account_id=self.account_id, symbol=sym)

        pos = self.positions[sym]
        prev_qty = pos.qty

        if prev_qty * trade_qty >= 0:
            self._handle_same_direction_trade(pos, trade_qty, trade_price)
        else:
            self._handle_opposite_direction_trade(pos, trade_qty, trade_price)

        pos.qty = prev_qty + trade_qty
        logger.debug(f"{sym}: Position updated to qty={pos.qty}")

    def _handle_same_direction_trade(self, pos: Position, trade_qty: int, trade_price: float):
        """Handle weighted average cost updates for same-direction trades"""
        sym = pos.symbol
        prev_qty = pos.qty
        prev_cost = pos.avg_cost
        new_qty = prev_qty + trade_qty
        if new_qty != 0:
            pos.avg_cost = (prev_qty * prev_cost + trade_qty * trade_price) / new_qty
            logger.debug(f"{sym}: avg_cost updated to {pos.avg_cost:.2f}")

    def _handle_opposite_direction_trade(self, pos: Position, trade_qty: int, trade_price: float):
        """Handle opposite-direction trade: realize PnL and update position."""
        sym = pos.symbol
        prev_qty = pos.qty
        prev_cost = pos.avg_cost
        closing_qty = min(abs(prev_qty), abs(trade_qty))

        self._realize_pnl(sym, closing_qty, trade_price, prev_cost, prev_qty)

        # After closing, check remaining qty
        new_qty = prev_qty + trade_qty

        if new_qty == 0:
            pos.avg_cost = 0.0
            logger.debug(f"{sym}: Position fully closed")
        elif prev_qty * new_qty > 0:
            logger.debug(f"{sym}: Partial close, avg_cost remains {prev_cost:.2f}")
        else:
            # Direction flipped: open new position at trade price
            pos.avg_cost = trade_price
            logger.debug(
                f"{sym}: Direction flipped, new position opened at {trade_price:.2f} "
                f"(qty={new_qty})"
            )

    def _realize_pnl(
        self,
        symbol: str,
        closing_qty: float,
        trade_price: float,
        prev_cost: float,
        prev_qty: float,
    ):
        """Calculate and log realized PnL."""
        sign = 1 if prev_qty > 0 else -1
        pnl_increment = closing_qty * (trade_price - prev_cost) * sign
        self.realized_pnl[symbol] += pnl_increment
        logger.info(
            f"{symbol}: Realized PnL {self.realized_pnl[symbol]:.2f} (closed {closing_qty} @ {trade_price:.2f} "
            f"vs cost {prev_cost:.2f})"
        )

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
        return sum(self.realized_pnl[sym] + self.get_unrealized_pnl(sym) for sym in self.positions)

    def get_long_positions(self) -> dict[str, Position]:
        """Get all long positions"""
        return {sym: pos for sym, pos in self.positions.items() if pos.is_long()}

    def get_short_positions(self) -> dict[str, Position]:
        """Get all short positions"""
        return {sym: pos for sym, pos in self.positions.items() if pos.is_short()}

    def get_open_positions(self) -> dict[str, Position]:
        """Get all open positions (non-zero qty)"""
        return {sym: pos for sym, pos in self.positions.items() if pos.is_open()}

    def get_pnl_by_symbol(self, symbol: str) -> dict[str, float]:
        """Get both realized and unrealized PnL for a symbol"""
        return {
            "realized": self.realized_pnl.get(symbol, 0.0),
            "unrealized": self.get_unrealized_pnl(symbol),
            "total": self.realized_pnl.get(symbol, 0.0) + self.get_unrealized_pnl(symbol),
        }

    def get_total_notional(self, last_prices: dict[str, float]) -> float:
        """Total notional value across all positions"""
        return sum(
            pos.notional_value(last_prices.get(pos.symbol, 0.0)) for pos in self.positions.values()
        )

    def log_summary(self, symbol: str | None = None) -> str:
        """Log engine summary for debugging"""
        if symbol:
            pos = self.get_position(symbol)
            realized = self.realized_pnl.get(symbol, 0.0)
            unrealized = self.get_unrealized_pnl(symbol)
            summary = (
                f"{symbol}: qty={pos.qty}, avg_cost={pos.avg_cost:.2f}, "
                f"realized={realized:.2f}, unrealized={unrealized:.2f}, "
                f"total={realized + unrealized:.2f}"
            )
        else:
            # All symbols
            positions_count = len(self.positions)
            total_realized = sum(self.realized_pnl.values())
            total_unrealized = sum(self.get_unrealized_pnl(sym) for sym in self.positions)
            summary = (
                f"Account {self.account_id}: {positions_count} symbols, "
                f"realized={total_realized:.2f}, unrealized={total_unrealized:.2f}, "
                f"total={self.get_total_pnl():.2f}"
            )

        logger.info(summary)
        return summary
