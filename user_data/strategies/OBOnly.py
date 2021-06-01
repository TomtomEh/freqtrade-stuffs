import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import talib.abstract as ta
from freqtrade.strategy.interface import IStrategy 
from freqtrade.strategy import timeframe_to_prev_date
import os
from pandas import DataFrame
from datetime import datetime, timedelta
from freqtrade.data.converter import order_book_to_dataframe



class OBOnly(IStrategy):
    INTERFACE_VERSION = 2

    minimal_roi = {
        "0": 0.01,
        "10": 0.007,
        "15": 0.0035,
         "25": 0.002,


    }

    stoploss = -0.01  # effectively disabled.

    timeframe = '1h'

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 50

    ob_history={}
    ob_delta_bid=0.005
    ob_delta_ask=0.02
    ob_ratio=1.
    ob_blend=1
    ob_log=True
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                           rate: float, time_in_force: str, current_time, **kwargs) -> bool:
        ob = self.dp.orderbook(pair,1000)
        ob_dp=order_book_to_dataframe(ob['bids'],ob['asks'])
        mid_price=(ob_dp['bids'][0]+ob_dp['asks'][0])/2
        bid_cut = mid_price - mid_price*self.ob_delta_bid
        ask_cut = mid_price + mid_price*self.ob_delta_ask
        bid_side=ob_dp[ob_dp['bids']>bid_cut]['b_sum']
        ask_side=ob_dp[ob_dp['asks']<ask_cut]['a_sum']
        
        if ask_side.count() == 1000 or bid_side.count() == 1000:
            return False
        ask_side=ask_side.tail(1).item()
        bid_side=bid_side.tail(1).item()

        r=bid_side/ask_side
        self.ob_history[pair]=(1.0-self.ob_blend)*self.ob_history.get(pair.replace("BUSD","USDT"),0)+self.ob_blend*r

        if( self.ob_history[pair]> self.ob_ratio):
            if self.ob_log:
                dp_dir = "depth/"+pair+"/"
                try:
                    os.makedirs(dp_dir)
                except OSError:
                    pass
                ob_dp.to_csv(dp_dir+"/"+current_time.strftime("buy_%m_%d_%Y_%H_%M")+".csv")

                f=open("log.dry.log", "a+")
                f.write(f"{str(current_time)} - buying {pair}  {self.ob_history[pair]} {r} {rate} \n")
                f.close()
            self.ob_history[pair]=0
            return True
     
        return False
         
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe [
          
            'buy'
        ] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe[
            
            'sell'
        ] = 0
        return dataframe
