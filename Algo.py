import MetaTrader5 as mt
import time
import pandas_ta as ta
from datetime import datetime, timedelta
import numpy as np  # The Numpy numerical computing library
import pandas as pd  # The Pandas data science library
import requests  # The requests library for HTTP requests in Python
import xlsxwriter  # The XlsxWriter library for
import math  # The Python math module
from scipy import stats  # The SciPy stats module

# Initialize and connect to MT5
if not mt.initialize():
    print("initialize() failed, error code =", mt.last_error())
    quit()
else:
    print('Connected to MetaTrader5')

login = 51439669
password = 'et8eMdvJ'
server = 'ICMarketsSC-Demo'

if not mt.login(login, password, server):
    print("Login failed, error code =", mt.last_error())
    mt.shutdown()
    quit()

sp500_symbols = pd.read_csv('sp_500_stocks.csv')

for symbol in sp500_symbols['Ticker']:
    try:
        rates = mt.copy_rates_from_pos(symbol, mt.TIMEFRAME_D1, 0, 365)  # Last 365 days of daily data
        df = pd.DataFrame(rates)
        print(f"Data for {symbol} retrieved")
    except Exception as e:
        print(f"Could not retrieve data for {symbol}: {e}")


account_info = mt.account_info()
print(account_info)

# getting specific account data
# login_number = account_info.login
balance = mt.account_info().balance
equity = mt.account_info().equity

num_symbols = mt.symbols_total()
print('num_symbols: ', num_symbols)

symbols = mt.symbols_get()
print(symbols)

symbol_info = mt.symbol_info("BTCUSD")._asdict()
print(symbol_info)

symbol_price = mt.symbol_info_tick("BTCUSD")._asdict()
print(symbol_price)


# Sending Market Order Crossover Strategy *1
def market_order(symbol, volume, order_type, deviation, magic, stoploss, takeprofit):
    tick = mt.symbol_info_tick(symbol)

    order_dict = {'buy': 0, 'sell': 1}
    price_dict = {'buy': tick.ask, 'sell': tick.bid}

    request = {
        "action": mt.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_dict[order_type],
        "price": price_dict[order_type],
        "deviation": deviation,
        "magic": magic,
        "sl": stoploss,
        "tp": takeprofit,
        "comment": "python market order",
        "type_time": mt.ORDER_TIME_GTC,
        "type_filling": mt.ORDER_FILLING_IOC,
    }

    order_result = mt.order_send(request)
    print(order_result)

    return order_result


# Closing an order from the ticket ID
def close_order(ticket):
    positions = mt.positions_get()
    ticket_found = False

    for pos in positions:
        tick = mt.symbol_info_tick(pos.symbol)
        type_dict = {0: 1, 1: 0}  # 0 for buy, 1 for sale. so inverting to close pos
        price_dict = {0: tick.ask, 1: tick.bid}

        if pos.ticket == ticket:
            request = {
                "action": mt.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": type_dict[pos.type],
                "price": price_dict[pos.type],
                "deviation": DEVIATION,
                "magic": 100,
                "sl": 2,
                "tp": 3,
                "comment": "python close order",
                "type_time": mt.ORDER_TIME_GTC,
                "type_filling": mt.ORDER_FILLING_IOC,
            }

        order_result = mt.order_send(request)
        print(order_result)
        return order_result

    if not ticket_found:
        print('Ticket does not exist')
        return 'Ticket does not exist'


# function for symbol exposure
def get_exposure(symbol):
    positions = mt.positions_get(symbol=symbol)
    if positions:
        pos_df = pd.DataFrame(list(map(lambda x: x._asdict(), positions)))
        exposure = pos_df['volume'].sum()
        return exposure
    return 0


# --------------------------Start of signals--------------------------------------

def calculate_indicators_and_generate_signals(symbol, timeframe):
    # Fetch historical data
    rates = mt.copy_rates_from_pos(symbol, timeframe, 0,
                                   70)  # Adjust last parameter to suit the requirement of your indicators
    if rates is None or len(rates) < 100:
        print("Not enough data to perform analysis")
        return None, None, None

    df = pd.DataFrame(rates)

    # Calculate indicators
    bollinger = ta.bbands(df['close'], length=20, std=2)
    rsi = ta.rsi(df['close'], length=14)
    sma_fast = ta.sma(df['close'], length=5)
    sma_slow = ta.sma(df['close'], length=20)

    # Get the latest values
    latest_close = df['close'].iloc[-1]
    lower_band = bollinger['BBL_20_2.0'].iloc[-1]
    upper_band = bollinger['BBU_20_2.0'].iloc[-1]
    latest_rsi = rsi.iloc[-1]
    latest_fast_sma = sma_fast.iloc[-1]
    latest_slow_sma = sma_slow.iloc[-1]

    # Generate signals based on the latest indicator values
    boll_signal = 'buy' if latest_close < lower_band else 'sell' if latest_close > upper_band else 'flat'
    rsi_signal = 'buy' if latest_rsi < 30 else 'sell' if latest_rsi > 70 else 'flat'
    sma_signal = 'buy' if latest_fast_sma > latest_slow_sma else 'sell' if latest_fast_sma < latest_slow_sma else 'flat'

    return boll_signal, rsi_signal, sma_signal


# --------------------------End of signals--------------------------------------


if __name__ == '__main__':
    # strategy params
    SYMBOL = "BTCUSD"
    TIMEFRAME = mt.TIMEFRAME_D1  # TIMEFRAME_D1, TIMEFRAME
    VOLUME = 1.0  # FLOAT
    DEVIATION = 5  # INTEGER
    MAGIC = 10
    TP_SD = 2  # number of deviations for take profit
    SL_SD = 3  # number of deviations for stop loss

    while True:
        # calculating account exposure
        exposure = get_exposure(SYMBOL)
        boll_signal, rsi_signal, sma_signal = calculate_indicators_and_generate_signals(SYMBOL, TIMEFRAME)

        tick = mt.symbol_info_tick(SYMBOL)

        # trading logic
        if boll_signal == 'buy' and rsi_signal == 'buy' and sma_signal == 'buy':
            # if a BUY signal is detected, close all short orders
            for pos in mt.positions_get():
                if pos.type == 1:  # pos.type == 1 means a sell order
                    close_order(pos.ticket)
            # if there are no open positions, open a new long position
            if not mt.positions_total():
                market_order(SYMBOL, VOLUME, 'buy', DEVIATION, MAGIC, tick.bid - SL_SD * df['close'].std(),
                             tick.bid + TP_SD * df['close'].std())

        elif boll_signal == 'sell' and rsi_signal == 'sell' and sma_signal == 'sell':
            # if a SELL signal is detected, close all short orders
            for pos in mt.positions_get():
                if pos.type == 0:  # pos.type == 0 means a buy order
                    close_order(pos.ticket)
            if not mt.positions_total():
                market_order(SYMBOL, VOLUME, 'sell', DEVIATION, MAGIC, tick.bid + SL_SD * df['close'].std(),
                             tick.bid - TP_SD * df['close'].std())

        print('time: ', datetime.now())
        print('Exposure: ', exposure)
        print('Bollinger Signal:', boll_signal)
        print('RSI Signal:', rsi_signal)
        print('SMA Signal:', sma_signal)
        print('--------------------------------\n')

        # update ever 1s
        time.sleep(3)

num_orders = mt.orders_total()
num_orders

orders = mt.orders_get()
orders

num_order_history = mt.history_orders_total(datetime(2023, 10, 1), datetime(2021, 10, 13))
num_order_history

order_history = mt.history_orders_get(datetime(2023, 10, 1), datetime(2023, 10, 13))
order_history

num_deal_history = mt.history_deals_total(datetime(2023, 10, 1), datetime(2023, 10, 13))
num_deal_history

deal_history = mt.history_deals_get(datetime(2023, 10, 1), datetime(2023, 10, 13))
deal_history
