import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import talib.abstract as ta
from freqtrade.strategy.interface import IStrategy 
from freqtrade.strategy import timeframe_to_prev_date
import os
from pandas import DataFrame
from datetime import datetime, timedelta
from freqtrade.data.converter import order_book_to_dataframe
from talipp.indicators import EMA, SMA ,BB,RSI

from user_data.strategies.BinanceStream import BaseIndicator, BasePairInfo

###########################################################################################################
##                CombinedBinHAndClucV4 by iterativ                                                      ##
##                                                                                                       ##
##    The authors of the original CombinedBinHAndCluc https://github.com/freqtrade/freqtrade-strategies  ##
##    V4 by iterativ.                                                                                    ##
##                                                                                                       ##
###########################################################################################################
##               GENERAL RECOMMENDATIONS                                                                 ##
##                                                                                                       ##
##   For optimal performance, suggested to use between 4 and 6 open trades, with unlimited stake.        ##
##   A pairlist with 20 to 40 pairs. Volume pairlist works well.                                         ##
##   Prefer stable coin (USDT, BUSDT etc) pairs, instead of BTC or ETH pairs.                            ##
##                                                                                                       ##
###########################################################################################################
##               DONATIONS                                                                               ##
##                                                                                                       ##
##   Absolutely not required. However, will be accepted as a token of appreciation.                      ##
##                                                                                                       ##
##   BTC: bc1qvflsvddkmxh7eqhc4jyu5z5k6xcw3ay8jl49sk                                                     ##
##   ETH: 0x83D3cFb8001BDC5d2211cBeBB8cB3461E5f7Ec91                                                     ##
##                                                                                                       ##
###########################################################################################################


class PairInfo(BasePairInfo):
    def __init__(self,pair):
        super().__init__(pair)
        self.bi=BaseIndicator(pair,timeframe="1m",currency="USDT")
        self.bb_40=BB(40,2.0,input_indicator=self.bi.c) #Attach BB to the base close indicator
        self.bb20=BB(20,2.0,input_indicator=self.bi.c) 
        self.ema_slow=EMA(50,input_indicator=self.bi.c)
        self.volume_mean_slow=SMA(30,input_indicator=self.bi.v)
        self.rsi=RSI(9,input_indicator=self.bi.c)


    def new_candle(self):
        bbdelta = self.bb_40[-1].cb - self.bb_40[-1].lb
        close = self.bi.c[-1][-1]
        close_prev=self.bi.c[-2][-1]
        closedelta = abs(close - close_prev)
        tail = abs(self.bi.c[-1][-1] - self.bi.l[-1][-1]) 
        volume = self.bi.v[-1][-1]
        #print(f"bbdeltatpp {bbdelta}")
        #print(f"closetpp {close}")
        
        buy_condition = ((  # strategy BinHV45
            self.bi.l[-2][0] > 0 and
            bbdelta > (close* 0.008/4) and
            closedelta>(close * 0.0175/4) and
            tail < (bbdelta * 0.25) and
            close<self.bb_40[-2].lb and
            close<self.bi.c[-2][0] and
               volume > 0 # Make sure Volume is not 0
        )
        |
        (  # strategy ClucMay72018
            close < self.ema_slow[-1] and
            close < 0.985 * self.bb20[-1].lb and
            volume < self.volume_mean_slow[-2] * 20 and
            volume > 0 # Make sure Volume is not 0
        ))
        #buy_condition=True
        if buy_condition:
            self.buy()

        sell_condition=(
            close > self.bb20[-1].ub and
            close_prev > self.bb20[-2].ub and
            volume > 0 
        )

        if sell_condition:
            self.sell()
        
class CombinedBinHAndClucV4WS(IStrategy):
    INTERFACE_VERSION = 2

    minimal_roi = {
        "0": 0.018
    }

    stoploss = -0.9 # effectively disabled.

    timeframe = '1h'
    compute_original=False
    # Sell signal
    use_sell_signal = True
    sell_profit_only = True
    sell_profit_offset = 0.001 # it doesn't meant anything, just to guarantee there is a minimal profit.
    ignore_roi_if_buy_signal = True

    # Trailing stoploss
    trailing_stop = True
    trailing_only_offset_is_reached = True
    trailing_stop_positive = 0.007
    trailing_stop_positive_offset = 0.018

    # Custom stoploss
    use_custom_stoploss = False

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 50

    # Optional order type mapping.
    order_types = {
        'buy': 'limit',
        'sell': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }
    
    ob_history={}
    ob_delta_bid=0.002
    ob_delta_ask=0.002
    ob_ratio=1.2
    ob_blend=0.6
    """def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                           rate: float, time_in_force: str, current_time, **kwargs) -> bool:
        ob = self.dp.orderbook(pair,1000)
        ob_dp=order_book_to_dataframe(ob['bids'],ob['asks'])
        mid_price=(ob_dp['bids'][0]+ob_dp['asks'][0])/2
        bid_side=ob_dp[ob_dp['bids']>(mid_price - mid_price*self.ob_delta_bid)].tail(1)['b_sum'].item()
        ask_side=ob_dp[ob_dp['asks']<(mid_price + mid_price*self.ob_delta_ask)].tail(1)['a_sum'].item()

        r=bid_side/ask_side
        self.ob_history[pair]=(1.0-self.ob_blend)*self.ob_history.get(pair.replace("BUSD","USDT"),0)+self.ob_blend*r

        if( self.ob_history[pair]> self.ob_ratio):
            self.ob_history[pair]=0
            return True
     
        return False
    """
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        # Manage losing trades and open room for better ones.
        if (current_profit < 0) & (current_time - timedelta(minutes=3000000) > trade.open_date_utc):
            return 0.01
        return 0.99
    """def confirm_trade_exit(self, pair: str, trade: 'Trade', order_type: str, amount: float,
                           rate: float, time_in_force: str, sell_reason: str,
                           current_time: 'datetime', **kwargs) -> bool:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        # Prevent ROI trigger, if there is more potential, in order to maximize profit
        if (sell_reason == 'roi') & (last_candle['rsi'] > 63):
            return False
        return True
    """
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # strategy BinHV45
        if self.compute_original: 

            bb_40 = qtpylib.bollinger_bands(dataframe['close'], window=40, stds=2)
            dataframe['lower'] = bb_40['lower']
            dataframe['mid'] = bb_40['mid']
            dataframe['bbdelta'] = (bb_40['mid'] - dataframe['lower']).abs()
            dataframe['closedelta'] = (dataframe['close'] - dataframe['close'].shift()).abs()
            dataframe['tail'] = (dataframe['close'] - dataframe['low']).abs()


            # strategy ClucMay72018
            bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
            dataframe['bb_lowerband'] = bollinger['lower']
            dataframe['bb_middleband'] = bollinger['mid']
            dataframe['bb_upperband'] = bollinger['upper']
            dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=50)
            dataframe['volume_mean_slow'] = dataframe['volume'].rolling(window=30).mean()
            dataframe['rsi'] = ta.RSI(dataframe, timeperiod=9)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if self.compute_original: 
            dataframe.loc[
                (  # strategy BinHV45
                    dataframe['lower'].shift().gt(0) &
                    dataframe['bbdelta'].gt(dataframe['close'] * 0.008) &
                    dataframe['closedelta'].gt(dataframe['close'] * 0.0175) &
                    dataframe['tail'].lt(dataframe['bbdelta'] * 0.25) &
                    dataframe['close'].lt(dataframe['lower'].shift()) &
                    dataframe['close'].le(dataframe['close'].shift()) &
                    (dataframe['volume'] > 0) # Make sure Volume is not 0
                )
                |
                (  # strategy ClucMay72018
                    (dataframe['close'] < dataframe['ema_slow']) &
                    (dataframe['close'] < 0.985 * dataframe['bb_lowerband']) &
                    (dataframe['volume'] < (dataframe['volume_mean_slow'].shift(1) * 20)) &
                    (dataframe['volume'] > 0) # Make sure Volume is not 0
                ),
                'buy'
            ] = 1
        pair=metadata["pair"]
        
        shoud_buy=PairInfo.get(pair).check_buy()

        #last_candle = dataframe.iloc[-1].squeeze()
        if shoud_buy:
            self.unlock_pair(pair)
            dataframe.loc[dataframe.index.max(),"buy"]=1 
        else:
            dataframe.loc[dataframe.index.max(),"buy"]=0
        
        #print(f"{pair} {shoud_buy}")
        
        return dataframe
    def set_ft(self,ft):
        PairInfo.set_ft(ft)
        self.ft=ft
    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if self.compute_original: 
        
            dataframe.loc[
                ( # Improves the profit slightly.
                    (dataframe['close'] > dataframe['bb_upperband']) &
                    (dataframe['close'].shift(1) > dataframe['bb_upperband'].shift(1)) &
                    (dataframe['volume'] > 0) # Make sure Volume is not 0
                )
                ,
                'sell'
            ] = 1
        pair=metadata["pair"]

        shoud_sell=PairInfo.get(pair).check_sell()
        if shoud_sell:
            dataframe.loc[dataframe.index.max(),"sell"]=1 
        else:
            dataframe.loc[dataframe.index.max(),"sell"]=0
        
        return dataframe
