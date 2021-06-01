import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import talib.abstract as ta
from freqtrade.strategy.interface import IStrategy 
from freqtrade.strategy import timeframe_to_prev_date
import os
from pandas import DataFrame
from datetime import datetime, timedelta
from freqtrade.data.converter import order_book_to_dataframe
import random
#import debugpy
#debugpy.listen(5678)
#debugpy.wait_for_client()


class OBOnlyV3(IStrategy):
    INTERFACE_VERSION = 2

    cust_minimal_roi = {
        "0": 0.01,
        "10": 0.007
        

    }

    stoploss = -0.01  # effectively disabled.
    counter=0
    timeframe = '1h'
    use_sell_signal = True
    sell_profit_only = False
    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 0

    ob_history={}
    ob_trade={"delta_bid":0.005,
            "delta_ask":0.02,
            "ratio_min":1,
            "ratio_max":1.6,
            "ratio":1.57,
            "loss_penality":0.1,
            "profit_reward":0.025,
            "blend":1,
            "log": False
    }
    last_time=datetime.now()-timedelta(minutes=25)
    def bot_loop_start(self, **kwargs) -> None:
        if (datetime.now()-self.last_time) > timedelta(minutes=15):
            self.last_time = datetime.now()
            self.ob_trade["ratio"]=max(self.ob_trade["ratio_min"],self.ob_trade["ratio"]-self.ob_trade["profit_reward"])

           
    def min_roi_entry(self, roi_table: dict,trade_dur: int) -> float:

        roi_list = list(filter(lambda x: int(x) <= trade_dur, roi_table.keys()))
        if not roi_list:
            return None, None
        roi_entry = max(roi_list)
        return roi_table[roi_entry]

    def custom_sell(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float, current_profit: float, **kwargs):
        print("called custom sell_n")
        
        trade_dur = int((current_time.timestamp() - trade.open_date_utc.timestamp()) // 60)

        roi_value=self.min_roi_entry(self.cust_minimal_roi, trade_dur)
        f=open("log.log", "a+")
        f.write(f"{current_time} - {pair} {roi_value} {current_profit} {self.ob_trade['ratio']}\n")
        f.close()
        
        if current_profit > roi_value:
            self.ob_trade["ratio"]=max(self.ob_trade["ratio_min"],self.ob_trade["ratio"]-self.ob_trade["profit_reward"])
            return 'roi'
        # shoudl try -roi_value here tu funnel trade
        if current_profit < self.stoploss:
            self.ob_trade["ratio"]=min(self.ob_trade["ratio_max"],self.ob_trade["ratio"]+self.ob_trade["loss_penality"])
            return 'stoploss'
        r = self.get_ratio(pair,current_rate,self.ob_trade["delta_ask"],0.01)
        if 1/r > (self.ob_trade["ratio_min"]):
            return "ratio"
        return None 

    def get_ratio(self, pair: str,
                           rate: float, delta_bid: float, delta_ask: float) -> float:
        ob = self.dp.orderbook(pair,1000)

        ob_dp=order_book_to_dataframe(ob['bids'],ob['asks'])
        if self.ob_trade["log"]:
            dp_dir = "depth/"+pair+"/"
            try:
                os.makedirs(dp_dir)
            except OSError:
                pass
            ob_dp.to_csv(dp_dir+"/"+str(int(datetime.now().timestamp()))+".csv")
        mid_price=(ob_dp['bids'][0]+ob_dp['asks'][0])/2
        bid_cut = mid_price - mid_price*delta_bid
        ask_cut = mid_price + mid_price*delta_ask
        bid_side=ob_dp[ob_dp['bids']>bid_cut]['b_sum']
        ask_side=ob_dp[ob_dp['asks']<ask_cut]['a_sum']
        # some 
        if ask_side.count() == 1000 or bid_side.count() == 1000:
            return False
        ask_side=ask_side.tail(1).item()
        bid_side=bid_side.tail(1).item()

        r=bid_side/ask_side
        return r
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                           rate: float, time_in_force: str, current_time, **kwargs) -> bool:

        r=self.get_ratio(pair,rate,self.ob_trade["delta_bid"],self.ob_trade["delta_ask"])
        self.ob_history[pair]=(1.0-self.ob_trade["blend"])*self.ob_history.get(pair.replace("BUSD","USDT"),0)+self.ob_trade["blend"]*r
      

        if( self.ob_history[pair]> self.ob_trade["ratio"]):
            
            #    f=open("log.dry.log", "a+")
            #    f.write(f"{str(current_time)} - buying {pair}  {self.ob_history[pair]} {r} {rate} \n")
            #    f.close()
            self.ob_history[pair]=0
            return True
     
        return False
         
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        

        return dataframe
    def set_df(self,dataframe,key,val):
        dataframe.loc[dataframe.index.max(),key]=val 
        """
        if key in dataframe:
            print("using df")
        dataframe[dataframe["date"]==dataframe["date"].tail(1)ke].iat[-1]=val 
        else:
            dataframe[key]=val
        """
            
    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
 
        #debugpy.breakpoint()
        
        if random.randint(0, 10) == 0: 
           self.set_df(dataframe,"buy",1)
        else:
            self.set_df(dataframe,"buy",0)
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self.set_df(dataframe,"sell",0)
        return dataframe
