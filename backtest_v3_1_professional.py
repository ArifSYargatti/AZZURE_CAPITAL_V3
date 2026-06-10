"""
Production-Grade Backtest Engine v3.1
=====================================

A clean, maintainable backtesting framework using a single state-machine architecture:
Entry -> Manage -> Exit -> Reset lifecycle.

Integrates:
- PositionManager.manage_position() as the ONLY exit engine
- RiskManager.calculate_quantity()
- TradeLogger.log_trade()
- Strategy.check_entry()

Tracks: trade_count, wins, losses, gross_profit, gross_loss, net_pnl,
best_trade, worst_trade, equity, peak_equity, max_drawdown
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import json


# ============================================================================
# Enums & Data Classes
# ============================================================================

class PositionState(Enum):
    """State machine states for position lifecycle."""
    RESET = "RESET"
    ENTRY = "ENTRY"
    MANAGE = "MANAGE"
    EXIT = "EXIT"


@dataclass
class Trade:
    """Represents a completed trade."""
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    return_pct: float
    
    def to_dict(self) -> Dict:
        return {
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'pnl': self.pnl,
            'return_pct': self.return_pct,
        }


@dataclass
class Position:
    """Represents an active position."""
    entry_price: float
    entry_time: datetime
    quantity: float
    symbol: str = "SYMBOL"
    
    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L."""
        return (current_price - self.entry_price) * self.quantity
    
    def unrealized_return_pct(self, current_price: float) -> float:
        """Calculate unrealized return percentage."""
        if self.entry_price == 0:
            return 0.0
        return ((current_price - self.entry_price) / self.entry_price) * 100


@dataclass
class PerformanceMetrics:
    """Container for performance statistics."""
    trade_count: int = 0
    wins: int = 0
    losses: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_pnl: float = 0.0
    best_trade: float = float('-inf')
    worst_trade: float = float('inf')
    equity: float = 0.0
    peak_equity: float = 0.0
    max_drawdown: float = 0.0
    
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self.trade_count == 0:
            return 0.0
        return (self.wins / self.trade_count) * 100
    
    def profit_factor(self) -> float:
        """Calculate profit factor (gross_profit / abs(gross_loss))."""
        if self.gross_loss == 0:
            return float('inf') if self.gross_profit > 0 else 0.0
        return self.gross_profit / abs(self.gross_loss)
    
    def to_dict(self) -> Dict:
        return {
            'trade_count': self.trade_count,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate_%': round(self.win_rate(), 2),
            'gross_profit': round(self.gross_profit, 2),
            'gross_loss': round(self.gross_loss, 2),
            'profit_factor': round(self.profit_factor(), 2),
            'net_pnl': round(self.net_pnl, 2),
            'best_trade': round(self.best_trade, 2),
            'worst_trade': round(self.worst_trade, 2),
            'equity': round(self.equity, 2),
            'peak_equity': round(self.peak_equity, 2),
            'max_drawdown': round(self.max_drawdown, 2),
            'max_drawdown_%': round((self.max_drawdown / self.peak_equity * 100) if self.peak_equity > 0 else 0, 2),
        }


# ============================================================================
# Module Interfaces (Mock Implementations)
# ============================================================================

class Strategy:
    """
    Strategy interface for entry signal generation.
    
    Implement check_entry() to define your entry logic.
    """
    
    def check_entry(self, current_price: float, data: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if entry conditions are met.
        
        Args:
            current_price: Current market price
            data: Optional additional market data
            
        Returns:
            (should_enter: bool, entry_reason: Optional[str])
        """
        raise NotImplementedError("Subclass must implement check_entry()")


class RiskManager:
    """
    Risk management interface for position sizing.
    
    Implement calculate_quantity() to define your sizing logic.
    """
    
    def calculate_quantity(self, 
                          account_balance: float,
                          entry_price: float,
                          stop_loss_price: float) -> float:
        """
        Calculate position quantity based on risk parameters.
        
        Args:
            account_balance: Current account balance
            entry_price: Entry price
            stop_loss_price: Stop loss price
            
        Returns:
            quantity: Number of units to trade
        """
        raise NotImplementedError("Subclass must implement calculate_quantity()")


class PositionManager:
    """
    Position management interface for exit logic.
    
    Implement manage_position() as the ONLY exit engine.
    """
    
    def manage_position(self, 
                       position: Position,
                       current_price: float,
                       data: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
        """
        Evaluate if position should be closed (ONLY exit engine).
        
        Args:
            position: Active position
            current_price: Current market price
            data: Optional additional market data
            
        Returns:
            (should_exit: bool, exit_reason: Optional[str])
        """
        raise NotImplementedError("Subclass must implement manage_position()")


class TradeLogger:
    """
    Trade logging interface for recording executed trades.
    
    Implement log_trade() to define logging behavior.
    """
    
    def log_trade(self, trade: Trade) -> None:
        """
        Log a completed trade.
        
        Args:
            trade: Completed trade object
        """
        raise NotImplementedError("Subclass must implement log_trade()")


# ============================================================================
# State Machine Backtest Engine
# ============================================================================

class BacktestEngine:
    """
    Production-grade backtest engine with state-machine architecture.
    
    Lifecycle: Entry -> Manage -> Exit -> Reset
    
    Uses:
    - Strategy.check_entry() for entry signals
    - RiskManager.calculate_quantity() for position sizing
    - PositionManager.manage_position() as ONLY exit engine
    - TradeLogger.log_trade() for trade recording
    """
    
    def __init__(self,
                 strategy: Strategy,
                 risk_manager: RiskManager,
                 position_manager: PositionManager,
                 trade_logger: TradeLogger,
                 initial_balance: float = 10000.0):
        """
        Initialize backtest engine.
        
        Args:
            strategy: Strategy instance for entry signals
            risk_manager: RiskManager instance for position sizing
            position_manager: PositionManager instance for exit logic
            trade_logger: TradeLogger instance for trade recording
            initial_balance: Starting account balance
        """
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.position_manager = position_manager
        self.trade_logger = trade_logger
        
        # Core state
        self.state = PositionState.RESET
        self.position: Optional[Position] = None
        self.current_balance = initial_balance
        
        # Performance tracking
        self.metrics = PerformanceMetrics()
        self.metrics.equity = initial_balance
        self.metrics.peak_equity = initial_balance
        
        # Trade history
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        
    def _state_entry(self, 
                     current_price: float,
                     timestamp: datetime,
                     data: Optional[Dict] = None) -> bool:
        """
        ENTRY state: Check for entry signal and open position if triggered.
        
        Returns:
            True if position opened, False otherwise
        """
        should_enter, entry_reason = self.strategy.check_entry(current_price, data)
        
        if not should_enter:
            return False
        
        # Calculate position size
        stop_loss_price = current_price * 0.95  # Default 5% stop loss
        quantity = self.risk_manager.calculate_quantity(
            self.current_balance,
            current_price,
            stop_loss_price
        )
        
        if quantity <= 0:
            return False
        
        # Open position
        self.position = Position(
            entry_price=current_price,
            entry_time=timestamp,
            quantity=quantity
        )
        
        self.state = PositionState.MANAGE
        return True
    
    def _state_manage(self,
                      current_price: float,
                      timestamp: datetime,
                      data: Optional[Dict] = None) -> bool:
        """
        MANAGE state: Monitor position and check for exit signals.
        
        Returns:
            True if exit triggered, False otherwise
        """
        if self.position is None:
            self.state = PositionState.RESET
            return False
        
        should_exit, exit_reason = self.position_manager.manage_position(
            self.position,
            current_price,
            data
        )
        
        if not should_exit:
            return False
        
        # Transition to EXIT state
        self.state = PositionState.EXIT
        return True
    
    def _state_exit(self,
                    current_price: float,
                    timestamp: datetime) -> None:
        """
        EXIT state: Close position, calculate P&L, and log trade.
        """
        if self.position is None:
            self.state = PositionState.RESET
            return
        
        # Calculate P&L
        pnl = (current_price - self.position.entry_price) * self.position.quantity
        return_pct = ((current_price - self.position.entry_price) / self.position.entry_price) * 100
        
        # Update balance
        self.current_balance += pnl
        
        # Create trade record
        trade = Trade(
            entry_price=self.position.entry_price,
            exit_price=current_price,
            quantity=self.position.quantity,
            entry_time=self.position.entry_time,
            exit_time=timestamp,
            pnl=pnl,
            return_pct=return_pct
        )
        
        # Log trade
        self.trade_logger.log_trade(trade)
        self.trades.append(trade)
        
        # Update metrics
        self._update_metrics(pnl)
        
        # Transition to RESET state
        self.position = None
        self.state = PositionState.RESET
    
    def _state_reset(self) -> None:
        """
        RESET state: Clean state, ready for next entry.
        """
        self.position = None
        self.state = PositionState.ENTRY
    
    def _update_metrics(self, trade_pnl: float) -> None:
        """Update performance metrics after a trade closes."""
        self.metrics.trade_count += 1
        self.metrics.net_pnl += trade_pnl
        self.metrics.equity = self.current_balance
        
        if trade_pnl > 0:
            self.metrics.wins += 1
            self.metrics.gross_profit += trade_pnl
        else:
            self.metrics.losses += 1
            self.metrics.gross_loss += trade_pnl
        
        # Track best/worst trade
        if trade_pnl > self.metrics.best_trade:
            self.metrics.best_trade = trade_pnl
        if trade_pnl < self.metrics.worst_trade:
            self.metrics.worst_trade = trade_pnl
        
        # Update peak equity and max drawdown
        if self.current_balance > self.metrics.peak_equity:
            self.metrics.peak_equity = self.current_balance
        
        drawdown = self.metrics.peak_equity - self.current_balance
        if drawdown > self.metrics.max_drawdown:
            self.metrics.max_drawdown = drawdown
    
    def step(self,
             current_price: float,
             timestamp: datetime,
             data: Optional[Dict] = None) -> None:
        """
        Execute one step of the backtest state machine.
        
        Args:
            current_price: Current market price
            timestamp: Current timestamp
            data: Optional additional market data
        """
        # Execute state machine
        if self.state == PositionState.RESET:
            self._state_reset()
        
        if self.state == PositionState.ENTRY:
            self._state_entry(current_price, timestamp, data)
        
        if self.state == PositionState.MANAGE:
            self._state_manage(current_price, timestamp, data)
        
        if self.state == PositionState.EXIT:
            self._state_exit(current_price, timestamp)
        
        # Record equity
        self.equity_curve.append((timestamp, self.current_balance))
    
    def get_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        return self.metrics
    
    def get_trades(self) -> List[Trade]:
        """Get list of completed trades."""
        return self.trades
    
    def print_summary_report(self) -> None:
        """Print professional summary report."""
        print("\n" + "=" * 80)
        print(" " * 20 + "BACKTEST PERFORMANCE SUMMARY")
        print("=" * 80)
        
        metrics_dict = self.metrics.to_dict()
        
        print("\n📊 TRADE STATISTICS")
        print("-" * 80)
        print(f"  Total Trades:          {metrics_dict['trade_count']:>20}")
        print(f"  Winning Trades:        {metrics_dict['wins']:>20}")
        print(f"  Losing Trades:         {metrics_dict['losses']:>20}")
        print(f"  Win Rate:              {metrics_dict['win_rate_%']:>19.2f}%")
        
        print("\n💰 PROFITABILITY")
        print("-" * 80)
        print(f"  Gross Profit:          ${metrics_dict['gross_profit']:>19,.2f}")
        print(f"  Gross Loss:            ${metrics_dict['gross_loss']:>19,.2f}")
        print(f"  Net P&L:               ${metrics_dict['net_pnl']:>19,.2f}")
        print(f"  Profit Factor:         {metrics_dict['profit_factor']:>20.2f}")
        
        print("\n🎯 TRADE QUALITY")
        print("-" * 80)
        print(f"  Best Trade:            ${metrics_dict['best_trade']:>19,.2f}")
        print(f"  Worst Trade:           ${metrics_dict['worst_trade']:>19,.2f}")
        avg_trade = (metrics_dict['net_pnl'] / metrics_dict['trade_count']) if metrics_dict['trade_count'] > 0 else 0
        print(f"  Average Trade:         ${avg_trade:>19,.2f}")
        
        print("\n📈 ACCOUNT PERFORMANCE")
        print("-" * 80)
        print(f"  Starting Equity:       ${self.metrics.equity - self.metrics.net_pnl:>19,.2f}")
        print(f"  Ending Equity:         ${metrics_dict['equity']:>19,.2f}")
        print(f"  Peak Equity:           ${metrics_dict['peak_equity']:>19,.2f}")
        print(f"  Max Drawdown:          ${metrics_dict['max_drawdown']:>19,.2f}")
        print(f"  Max Drawdown %:        {metrics_dict['max_drawdown_%']:>19.2f}%")
        
        return_pct = ((self.current_balance - (self.metrics.equity - self.metrics.net_pnl)) 
                      / (self.metrics.equity - self.metrics.net_pnl) * 100) if (self.metrics.equity - self.metrics.net_pnl) > 0 else 0
        print(f"  Total Return %:        {return_pct:>19.2f}%")
        
        print("\n" + "=" * 80 + "\n")


# ============================================================================
# Example Usage & Testing
# ============================================================================

class SimpleStrategy(Strategy):
    """Example strategy: Buy on price crossing threshold."""
    
    def __init__(self, buy_threshold: float = 100.0):
        self.buy_threshold = buy_threshold
        self.has_position = False
    
    def check_entry(self, current_price: float, data: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
        """Enter when price crosses threshold (example logic)."""
        if not self.has_position and current_price < self.buy_threshold:
            return True, f"Price crossed threshold: {current_price:.2f}"
        return False, None


class SimpleRiskManager(RiskManager):
    """Example risk manager: Fixed position sizing."""
    
    def __init__(self, risk_per_trade: float = 0.02, max_position_size: float = 100.0):
        self.risk_per_trade = risk_per_trade
        self.max_position_size = max_position_size
    
    def calculate_quantity(self, 
                          account_balance: float,
                          entry_price: float,
                          stop_loss_price: float) -> float:
        """Calculate quantity based on risk percentage."""
        risk_amount = account_balance * self.risk_per_trade
        stop_distance = abs(entry_price - stop_loss_price)
        
        if stop_distance == 0:
            return 0
        
        quantity = risk_amount / stop_distance
        return min(quantity, self.max_position_size)


class SimplePositionManager(PositionManager):
    """Example position manager: Exit on profit target or stop loss."""
    
    def __init__(self, profit_target_pct: float = 0.05, stop_loss_pct: float = 0.02):
        self.profit_target_pct = profit_target_pct
        self.stop_loss_pct = stop_loss_pct
    
    def manage_position(self, 
                       position: Position,
                       current_price: float,
                       data: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
        """Check if position should be closed."""
        unrealized_return = position.unrealized_return_pct(current_price)
        
        if unrealized_return >= self.profit_target_pct * 100:
            return True, f"Profit target hit: {unrealized_return:.2f}%"
        
        if unrealized_return <= -self.stop_loss_pct * 100:
            return True, f"Stop loss hit: {unrealized_return:.2f}%"
        
        return False, None


class SimpleTradeLogger(TradeLogger):
    """Example trade logger: Print trade details."""
    
    def log_trade(self, trade: Trade) -> None:
        """Log trade to console."""
        print(f"✓ Trade closed | Entry: ${trade.entry_price:.2f} | Exit: ${trade.exit_price:.2f} | "
              f"Qty: {trade.quantity:.2f} | P&L: ${trade.pnl:.2f} ({trade.return_pct:.2f}%)")


def run_example_backtest():
    """Run a simple example backtest."""
    # Create strategy components
    strategy = SimpleStrategy(buy_threshold=105.0)
    risk_manager = SimpleRiskManager(risk_per_trade=0.02, max_position_size=50.0)
    position_manager = SimplePositionManager(profit_target_pct=0.05, stop_loss_pct=0.02)
    trade_logger = SimpleTradeLogger()
    
    # Create engine
    engine = BacktestEngine(
        strategy=strategy,
        risk_manager=risk_manager,
        position_manager=position_manager,
        trade_logger=trade_logger,
        initial_balance=10000.0
    )
    
    # Simulate price data
    prices = [
        110.0, 109.5, 108.0, 104.0, 103.0, 102.5, 104.0, 106.0, 108.0,
        107.0, 105.0, 103.0, 104.0, 106.0, 108.0, 110.0, 111.0, 109.0,
        107.0, 105.0, 104.0, 103.0, 102.0, 101.0, 100.0, 101.5, 103.0,
        104.5, 106.0, 107.0, 105.5, 104.0, 105.0, 106.5, 107.5, 106.0,
        105.0, 104.0, 103.0, 102.0
    ]
    
    # Run backtest
    print("\n🚀 Running backtest...")
    for i, price in enumerate(prices):
        timestamp = datetime(2024, 1, 1, hour=i % 24, minute=(i // 24) * 5)
        engine.step(price, timestamp)
        
        # Update strategy state (simplified)
        if engine.position is None:
            strategy.has_position = False
        else:
            strategy.has_position = True
    
    # Print summary
    engine.print_summary_report()
    
    # Print trade details
    print("\n📋 DETAILED TRADE LIST")
    print("-" * 80)
    if engine.trades:
        for i, trade in enumerate(engine.trades, 1):
            print(f"\nTrade #{i}")
            print(f"  Entry:  ${trade.entry_price:.2f} @ {trade.entry_time.isoformat()}")
            print(f"  Exit:   ${trade.exit_price:.2f} @ {trade.exit_time.isoformat()}")
            print(f"  Qty:    {trade.quantity:.2f}")
            print(f"  P&L:    ${trade.pnl:.2f} ({trade.return_pct:.2f}%)")
    else:
        print("No trades executed.")
    
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    run_example_backtest()
