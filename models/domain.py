from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4


def generate_id() -> str:
    return str(uuid4())


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Trade:
    """
    A single trade execution
    """

    symbol: str
    qty: int  # +ve buy, -ve sell
    price: float
    trade_id: str = field(default_factory=generate_id)
    order_id: str | None = None  # Link to parent order
    timestamp: datetime = field(default_factory=datetime.now().astimezone)

    def notional_value(self) -> float:
        return abs(self.qty) * self.price


@dataclass
class Position:
    """
    Account position on a symbol
    """

    account_id: str
    symbol: str
    qty: int = 0
    avg_cost: float = 0.0
    position_id: str = field(default_factory=generate_id)
    updated_at: datetime = field(default_factory=datetime.now().astimezone)

    def is_long(self) -> bool:
        return self.qty > 0

    def is_short(self) -> bool:
        return self.qty < 0

    def notional_value(self, current_price: float) -> float:
        """Current market value of the position"""
        return self.qty * current_price

    def unrealized_pnl(self, current_price: float) -> float:
        """Unrealized PnL at current price"""

        if self.qty == 0:
            return 0.0
        return self.qty * (current_price - self.avg_cost)

    def is_open(self) -> bool:
        """Check if position has any qty"""
        return self.qty != 0

    def is_closed(self) -> bool:
        """Check if position is flat"""
        return self.qty == 0
