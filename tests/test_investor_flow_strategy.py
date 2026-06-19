from math import nan

from invest_bot.strategy import InvestorFlowCustomStrategy, Signal


def test_investor_flow_custom_strategy_returns_buy_signal_for_supportive_flow_and_price():
    strategy = InvestorFlowCustomStrategy()

    result = strategy.evaluate(
        {"foreign_net_qty": 10.0, "institutional_net_qty": 5.0, "close": 105.0, "ma_20": 100.0}
    )

    assert result.signal is Signal.BUY
    assert "are positive" in result.reason
    assert result.indicators == {
        "foreign_net_qty": 10.0,
        "institutional_net_qty": 5.0,
        "close": 105.0,
        "ma_20": 100.0,
    }


def test_investor_flow_custom_strategy_returns_sell_signal_for_weak_flow_and_price():
    strategy = InvestorFlowCustomStrategy()

    result = strategy.evaluate(
        {"foreign_net_qty": -10.0, "institutional_net_qty": -5.0, "close": 95.0, "ma_20": 100.0}
    )

    assert result.signal is Signal.SELL
    assert "are negative" in result.reason
    assert result.indicators == {
        "foreign_net_qty": -10.0,
        "institutional_net_qty": -5.0,
        "close": 95.0,
        "ma_20": 100.0,
    }


def test_investor_flow_custom_strategy_returns_hold_signal_for_mixed_flow():
    strategy = InvestorFlowCustomStrategy()

    result = strategy.evaluate(
        {"foreign_net_qty": 10.0, "institutional_net_qty": -5.0, "close": 105.0, "ma_20": 100.0}
    )

    assert result.signal is Signal.HOLD
    assert "mixed signal" in result.reason
    assert result.indicators == {
        "foreign_net_qty": 10.0,
        "institutional_net_qty": -5.0,
        "close": 105.0,
        "ma_20": 100.0,
    }


def test_investor_flow_custom_strategy_returns_hold_signal_when_price_filter_disagrees_with_flow():
    strategy = InvestorFlowCustomStrategy()

    result = strategy.evaluate(
        {"foreign_net_qty": 10.0, "institutional_net_qty": 5.0, "close": 95.0, "ma_20": 100.0}
    )

    assert result.signal is Signal.HOLD
    assert "mixed signal" in result.reason
    assert result.indicators == {
        "foreign_net_qty": 10.0,
        "institutional_net_qty": 5.0,
        "close": 95.0,
        "ma_20": 100.0,
    }


def test_investor_flow_custom_strategy_returns_hold_with_missing_indicator_reason_and_empty_indicators():
    strategy = InvestorFlowCustomStrategy()

    result = strategy.evaluate({"foreign_net_qty": 10.0, "institutional_net_qty": 5.0, "close": 105.0})

    assert result.signal is Signal.HOLD
    assert result.reason == "Missing indicators: ma_20"
    assert result.indicators == {}



def test_investor_flow_custom_strategy_returns_hold_for_zero_baseline():
    strategy = InvestorFlowCustomStrategy()

    result = strategy.evaluate(
        {"foreign_net_qty": 10.0, "institutional_net_qty": 5.0, "close": 105.0, "ma_20": 0.0}
    )

    assert result.signal is Signal.HOLD
    assert result.reason == "Invalid baseline: ma_20 is zero."
    assert result.indicators == {}

def test_investor_flow_custom_strategy_treats_nan_as_missing_indicator():
    strategy = InvestorFlowCustomStrategy()

    result = strategy.evaluate(
        {"foreign_net_qty": 10.0, "institutional_net_qty": nan, "close": 105.0, "ma_20": 100.0}
    )

    assert result.signal is Signal.HOLD
    assert result.reason == "Missing indicators: institutional_net_qty"
    assert result.indicators == {}
