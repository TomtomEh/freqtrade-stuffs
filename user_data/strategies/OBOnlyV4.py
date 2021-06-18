import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import talib.abstract as ta
from freqtrade.strategy.interface import IStrategy 
from freqtrade.strategy import timeframe_to_prev_date
import os
from pandas import DataFrame
from datetime import datetime, timedelta
from freqtrade.data.converter import order_book_to_dataframe
from freqtrade.persistence import Trade
import random
import time
#import debugpy
#debugpy.listen(5678)
#debugpy.wait_for_client()


class OBOnlyV3(IStrategy):
    INTERFACE_VERSION = 2

    cust_minimal_roi = {
        "0": 0.007,
        "5": 0.005,
        "10": 0.004,
        "15": 0.003,
        "20": 0.002
        

    }
    cust_stoploss = -0.006
    stoploss = -0.006   
    counter=0
    timeframe = '5m'
    use_sell_signal = True
    sell_profit_only = False
    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 100
    cust_conditions={}
    ob_history={}
    use_protections = True
    ob_penalize={}
    _perf_weight={}
    ob_trade={"delta_bid":0.003,
            "delta_ask":0.015,
            "ratio_min":1.3,
            "ratio_max":2.0,
            "ratio":1.3 ,
            "loss_penality":0.1,
            "profit_reward":0.035,
            "blend":1,
            "log": False
    }
    last_time_reduced_ratio=datetime.now()-timedelta(minutes=25)
    last_time_computed_indicators=datetime.now()-timedelta(hours=100)
    def update_perf_weight(self):
        perf = Trade.get_overall_performance()
        val=0
        self._perf_weight={}
        for a in perf:
            self._perf_weight[a["pair"]]=val
            val+=1
    def perf_weight(self,pair):
        randres= int(14*self._perf_weight.get(pair,len(self._perf_weight)/2)/max(len(self._perf_weight),1))
        print(f"{pair} {randres}")
        return randres

    def bot_loop_start(self, **kwargs) -> None:
        if (datetime.now()-self.last_time_reduced_ratio) > timedelta(minutes=20):
            self.update_perf_weight()

            open_trades = Trade.get_trades([Trade.is_open.is_(True)]).all()

            if len(open_trades) == 0:
        
                self.last_time_reduced_ratio = datetime.now()
                self.ob_trade["ratio"]=max(self.ob_trade["ratio_min"],self.ob_trade["ratio"]-self.ob_trade["profit_reward"])
                print(self.ob_trade["ratio"])
        self.compute=False


           
    def min_roi_entry(self, roi_table: dict,trade_dur: int) -> float:

        roi_list = []
        for x in roi_table.keys():
            if int(x) <= trade_dur:
                roi_list.append(int(x))
        if not roi_list:
            return None, None

        roi_entry = max(roi_list)
        return roi_table[str(roi_entry)]

    def custom_sell(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float, current_profit: float, **kwargs):
      
        trade_dur = int((current_time.timestamp() - trade.open_date_utc.timestamp()) // 60)
        
        roi_value=self.min_roi_entry(self.cust_minimal_roi, trade_dur)
        f=open("log.log", "a+")
        f.write(f"{current_time} - {trade_dur} {pair} {roi_value} {current_profit} {self.ob_trade['ratio']}\n")
        f.close()
        result = None
        self.ob_penalize[pair]=self.ob_penalize.get (pair,0)
        ratio_delta=self.ob_trade["ratio"]-self.ob_trade["ratio_min"]
        if current_profit > roi_value:
            result = 'roi'
        # shoudl try -roi_value here tu funnel trade          
        if  (current_profit>0.05 and current_profit< 0.05+((trade.max_rate-trade.open_rate)/trade.open_rate)):
            result =  'stoploss'
        r = self.get_ratio(pair,current_rate,0.006,0.002)
        if 1/r > 1.01:          
            result =  "ratio"
        if result == None:
            if current_profit < -0.005 and  self.ob_penalize[pair] == 0:
                old_ratio=self.ob_trade["ratio"]
                self.ob_trade["ratio"]=min(self.ob_trade["ratio_max"],self.ob_trade["ratio"]+self.ob_trade["loss_penality"])
                self.ob_penalize[pair] =  self.ob_trade["ratio"] - old_ratio
            if current_profit >  0.005 and self.ob_penalize[pair]  != 0:
                self.ob_trade["ratio"]-= self.ob_penalize[pair]
                self.ob_penalize[pair]=0
        else:
            if current_profit>0:
                self.ob_trade["ratio"]=max(self.ob_trade["ratio_min"],self.ob_trade["ratio"]-self.ob_penalize[pair]-self.ob_trade["profit_reward"])
            else:
                self.ob_trade["ratio"]=min(self.ob_trade["ratio_max"],self.ob_trade["ratio"]+self.ob_trade["loss_penality"] -self.ob_penalize[pair])
            self.ob_penalize[pair]=0

        return result 
    def get_ratio_buy(self, pair: str,
                           rate: float, delta_bid: float, delta_ask: float, num=1000) -> float:
        try:
            ob = self.dp.orderbook(pair,num)

            ob_dp=order_book_to_dataframe(ob['bids'],ob['asks'])
            if self.ob_trade["log"]:
                dp_dir = "depth/"+pair[:pair.find("/")]
                try:
                    os.makedirs(dp_dir)
                except OSError:
                    pass
                ob_dp.to_parquet(dp_dir+"/"+str(int(datetime.now().timestamp()))+".parket")
            mid_price=(0*ob_dp['bids'][0]+2*ob_dp['asks'][0])/2
            bid_cut = mid_price - mid_price*delta_bid
            ask_cut = mid_price + mid_price*delta_ask
            bid_side=ob_dp[ob_dp['bids']>bid_cut]
            ask_side=ob_dp[ob_dp['asks']<ask_cut]
            # some pairs don't have enough data. TODO:try to fetch more 
            if ask_side.count() == 1000 or bid_side.count() == 1000:
                if num == 1000:
                    return self.get_ratio_buy(pair,rate,delta_bid,delta_ask,10*num)
                else:
                    #return a low rate
                    return 1.0
            print(f"{pair} {min(ask_side.count(),bid_side.count()) }")       

            if min(ask_side['a_sum'].count(),bid_side['b_sum'].count()) < 10 :
                return 1.0 
            ask_side_i=ask_side['a_sum'].tail(1).item()
            bid_side_i=bid_side['b_sum'].tail(1).item()

            if bid_side[bid_side["b_size"] >bid_side_i/10].count()==0:
                return 1.0 
           
            r=bid_side_i/ask_side_i
            print(f"ratio {pair}  {r}")
            return r
        except:
            return 1.0

    def get_ratio(self, pair: str,
                           rate: float, delta_bid: float, delta_ask: float, num=1000) -> float:
        try:
            ob = self.dp.orderbook(pair,num)

            ob_dp=order_book_to_dataframe(ob['bids'],ob['asks'])
            if self.ob_trade["log"]:
                dp_dir = "depth/"+pair[:pair.find("/")]
                try:
                    os.makedirs(dp_dir)
                except OSError:
                    pass
                ob_dp.to_parquet(dp_dir+"/"+str(int(datetime.now().timestamp()))+".parket")
            mid_price=(0*ob_dp['bids'][0]+2*ob_dp['asks'][0])/2
            bid_cut = mid_price - mid_price*delta_bid
            ask_cut = mid_price + mid_price*delta_ask
            bid_side=ob_dp[ob_dp['bids']>bid_cut]['b_sum']
            ask_side=ob_dp[ob_dp['asks']<ask_cut]['a_sum']
            # some pairs don't have enough data. try to fetch more 
            if ask_side.count() == 1000 or bid_side.count() == 1000:
                if num == 1000:
                    return self.get_ratio(pair,rate,delta_bid,delta_ask,10*num)
                else:
                    #return a low rate
                    return 1.0

            if min(ask_side.count(),bid_side.count()) < 10 :
                return 1.0 
            ask_side=ask_side.tail(1).item()
            bid_side=bid_side.tail(1).item()

            r=bid_side/ask_side
            print(f"ratio {pair}  {r}")
            return r
        except:
            return 1.0

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                           rate: float, time_in_force: str, current_time, **kwargs) -> bool:

        if self.ob_trade["ratio"] >1.85:
            return False
        r=self.get_ratio_buy(pair,rate,self.ob_trade["delta_bid"],self.ob_trade["delta_ask"])
        self.ob_history[pair]=(1.0-self.ob_trade["blend"])*self.ob_history.get(pair,0)+self.ob_trade["blend"]*r
      

        if( self.ob_history[pair]> self.ob_trade["ratio"]):
            
            self.ob_history[pair]=0
            return True
     
        return False
        

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        imax = dataframe.index.max()
        if self.last_time_computed_indicators != dataframe.loc[imax,"date"]:
            self.compute = True
            self.last_time_computed_indicators=dataframe.loc[imax,"date"]
        if self.compute and self.use_protections:
            
            dataframe.loc[imax,'ratio'] = self.ob_trade["ratio"] 
            self.cust_conditions[metadata["pair"]]=False
            mhigh=max(dataframe.loc[imax,'high'],dataframe.loc[imax-1,'high'])
            mlow=min(dataframe.loc[imax,'low'],dataframe.loc[imax-1,'low'])
            delta = 0.5*(mhigh - mlow)/(mhigh + mlow)
            #avoid too volatile situations 
            if delta < 0.06:
                self.cust_conditions[metadata["pair"]]=True

            
        return dataframe
    def set_df(self,dataframe,key,val):
        dataframe.loc[dataframe.index.max(),key]=val 
            
    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        conditions=self.cust_conditions.get(metadata["pair"],False) 
        #use performance weight on random to open more trades on better performing pairs
        if conditions and  random.randint(0, self.perf_weight(metadata["pair"])) == 0   :

            self.set_df(dataframe,"buy",1)
        else:
            self.set_df(dataframe,"buy",0)
    
        return dataframe


    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self.set_df(dataframe,"sell",0)
        return dataframe
