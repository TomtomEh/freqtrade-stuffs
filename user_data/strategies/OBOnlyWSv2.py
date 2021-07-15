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
#TODO: test stoploss /bad idea. ROI ok
#TODO: test without green/red protection, bad idea
#todO; test BBAND?
#todO: test walls
#import debugpy
#debugpy.listen(5678)
#debugpy.wait_for_client()
""" Binance exchange subclass """
import logging
from typing import Any, Dict, List, Optional, Tuple
import profile
from pandas import DataFrame
from datetime import datetime,timedelta
import math
from freqtrade.exchange import Exchange
from freqtrade.exchange.common import retrier
from freqtrade.exchange.binance import Binance
from freqtrade.constants import DEFAULT_AMOUNT_RESERVE_PERCENT, ListPairsWithTimeframes
from freqtrade.persistence import PairLocks, Trade
from freqtrade.strategy.interface import IStrategy, SellCheckTuple, SellType
from talipp.indicators import EMA, SMA ,BB

logger = logging.getLogger(__name__)

import numpy as np
from binance import Client
from binance import ThreadedWebsocketManager, ThreadedDepthCacheManager

from binance.exceptions import BinanceAPIException
import time
from typing import Any, Callable, Dict, List, Optional

from user_data.strategies.BinanceWS import BinanceWS

class PairInfo: 
    _data={}
    def __init__(self):
        self.max_pct=0
        self.min_pct=0
        self.buy_signal=0
        self.ob_bb=BB(200,2.0)
        self.bb5=BB(20,2.0)

        self.ob_ema=EMA(7)
        self.sell_signal=0
        self.buy=False
    @classmethod
    def get(cls,pair):
        res = cls._data.get(pair,None)
        if res is None:
            cls._data[pair]=PairInfo() 
        return cls._data[pair]

class OBOnlyWSv2(BinanceWS):
    INTERFACE_VERSION = 2


    stoploss = -0.11  


    timeframe = '1m'
    use_sell_signal = True
    sell_profit_only = False
    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True
    strat_data={
        "ratio_buy1":0,
        "ratio_buy2":0,
        "ratio_buy3":0,
        "ratio_wall":0,
        "price":0,
        "ratio_ema":0,
        "ratio_ub":0,
        "ratio_lb":0,
        "ratio_gain":0,
    }
    def ob_cut(self, bids, asks,delta_bid,delta_ask=None,bid_weight=0.5):
        if delta_ask is None:
            delta_ask=delta_bid
        mid_price=(bid_weight*bids[0][0]+(1-bid_weight)*asks[0][0])
        bid_cut = mid_price - mid_price*delta_bid
        ask_cut = mid_price + mid_price*delta_ask
        bid_side=bids[bids[:,0]>bid_cut]
        ask_side=asks[asks[:,0]<ask_cut] 
        return bid_side,ask_side  
    def check_ob(self,pair, bids, asks,delta_bid,delta_ask=None,wall=0.0,ratio=1.0,bid_weight=0.5,reciprocal=False):
        if delta_ask is None:
            delta_ask=delta_bid
        mid_price=(bid_weight*bids[0][0]+(1-bid_weight)*asks[0][0])
        bid_cut = mid_price - mid_price*delta_bid
        ask_cut = mid_price + mid_price*delta_ask
        bid_side=bids[bids[:,0]>bid_cut]
        ask_side=asks[asks[:,0]<ask_cut]
        wall_side=bid_side
        asum=ask_side[:,1].sum() 
        bsum=bid_side[:,1].sum() 
        if wall<0:
            wall_side=ask_side
            wall=-wall
        wsum=wall_side[:,1].sum()
        volume =1*float(self.last_volume.get(pair,0))
        r=bsum/asum 
        r_test=(r >ratio)
        if reciprocal:
            r_test= ((1/r) >ratio)
        if r_test and min(np.size(ask_side[:,1]),np.size(bid_side[:,1])) > 10:
            wlist=wall_side[wall_side[:,1]>(wall*wsum)]
            #print(f"passed ratio {len (wlist) >0}")
            if   len (wlist) >0 :
                #print(f"symbol {pair} {r} {np.size(bid_side[:,1])} {np.size(ask_side[:,1])} ")

                return True,r
        return False,r
    def rescale(self,r):
        if math.isnan(r) or math.isinf(r) or r==0:
            return 1
        if r>1:
            return r-1
        return -(1/r-1)   
    def new_ob(self,bids, asks, pair):
  
        pi=PairInfo.get(pair)

        bb=pi.ob_bb
        ema=pi.ob_ema
        self.strat_data["price"]=mid_price=(1*bids[0][0]+1*asks[0][0])/2

        pi.buy,r2=self.check_ob(pair,bids, asks,delta_bid=0.002,delta_ask=0.002,wall=0.4,ratio=1.7)
        if pi.buy:
            self.strat_data["ratio_wall"]=1
        else:
            self.strat_data["ratio_wall"]=0
        bid_side,ask_side=self.ob_cut( bids, asks,delta_bid=0.002)
        mid_price=(1*bids[0][0]+1*asks[0][0])/2
        if hasattr(pi.bb5, 'last')==False or (datetime.now()-pi.bb5.last)>timedelta(minutes=1):
                
                pi.bb5.add_input_value(mid_price)
                pi.bb5.last=datetime.now()
                
                if len(pi.bb5)>1:
                    self.strat_data["ratio_ub"]=pi.bb5[-1].ub
                    self.strat_data["ratio_lb"]=pi.bb5[-1].lb
                    pi.bb5.purge_oldest(1)
                else:
                    self.strat_data["ratio_ub"]=mid_price
                    self.strat_data["ratio_lb"]=mid_price
       
            

        no_wallb=bid_side[bid_side[:,1]<0.4*np.sum(bid_side[:,1])]
        no_walla=ask_side[ask_side[:,1]<0.4*np.sum(ask_side[:,1])]

        r2=np.sum(bid_side)/np.sum(ask_side)
        r2=self.rescale(r2)  
        r2nw=np.sum(no_wallb)/np.sum(no_walla)
        r2nw=self.rescale(r2nw)  

        
        if len(bb)>0:      
            iv=r2nw
           
            #print(f"will added {iv} {bb[-1].lb}")
            bb.add_input_value(iv)
            #print(f" added {iv} {bb[-1].lb}")

            bb.purge_oldest(1)
            #print(f" pop {iv} {bb[-1].lb}")

           

           
        else:
            bb.add_input_value(r2nw)   
        if len(ema)>0:      
            self.strat_data["ratio_ema"]=ema[-1]
            
            ema.add_input_value(r2nw)
            ema.purge_oldest(1)
            
        else:
             ema.add_input_value(r2nw)

    def check_buy(self,bids, asks, pair):
        pi=PairInfo.get(pair)

        prev_buy_signal=pi.buy_signal
        pi.buy_signal=0
        open_trades= self.open_trades()
        
        #### NO RETURN BEFORE HERE
        
        
        if len (open_trades) >= self.max_trades or self.no_trade_until > datetime.now():
            return
        mid_price=(1*bids[0][0]+1*asks[0][0])/2
        lk=self.current_kline.get(pair)
        if lk and (0.0*float(lk["l"])+1.*float(lk["o"])) > bids[0][0]:
            return
        bb5=pi.bb5
        if len(bb5)>0: 
            bbb=bb5[-1]
            cond1=mid_price>(bbb.cb) and mid_price<(bbb.ub) 
            if not cond1:
                
                return 
        else:
            return           
        #buy1,r1=self.check_ob(pair,bids, asks,delta_bid=delta_bid,delta_ask=delta_ask,ratio=1.3)
        #buy2,r2=self.check_ob(pair,bids, asks,delta_bid=0.003,delta_ask=0.004,wall=0.3,ratio=1.3) 
        buy3=False
        bb=pi.ob_bb
        ema=pi.ob_ema
        if len(bb)>0 and len(ema)>0:      
            if ema[-1] > 1.3*bb[-1].ub:
                buy3=True
            
        self.strat_data["ratio_buy3"]= 1 if buy3 else 0

        if   buy3 : 
            pi.buy_signal=prev_buy_signal+1
            if pi.buy_signal <1: 
                
                return
            found_trade = None

            for trade in self.open_trades(True) :
                if trade.pair.replace("/","") == pair.replace("/",""):
                    found_trade = trade
            if found_trade:
                return

            stake_amount = self.ft.wallets.get_trade_stake_amount(pair)
            with self.ft._sell_lock:
                pi.max_pct=0
                pi.min_pct=0
                self.ft.execute_buy(pair,stake_amount,(0.8*bids[0][0]+0.2*asks[0][0]))
        else:
            pi.buy_signal=0  
    def check_sell(self,bids, asks, pair):
        pi=PairInfo.get(pair)
        sell_price=(0.1*bids[0][0]+0.9*asks[0][0])
        ob_price=(0.2*bids[0][0]+0.8*asks[0][0])
        mid_price=(0.5*bids[0][0]+0.5*asks[0][0])
        found_trade= self.open_trades(pair=pair)
        prev_sell_signal=pi.sell_signal
        pi.sell_signal=0
        if(found_trade == None):
            return
        found_trade= self.open_trades(force=True,pair=pair)
        if(found_trade == None):
            return

        lk=self.current_kline.get(pair)
        if lk and float(lk["o"]) < asks[0][0]:
                return
                
        gain = (mid_price-found_trade.open_rate)/found_trade.open_rate
        self.strat_data["ratio_gain"]= gain*100

        pi.min_pct=min(pi.min_pct,gain)
        
        
        sell_1=False
        bb=pi.ob_bb
        ema=pi.ob_ema
        sell2,r2=self.check_ob(pair,bids=bids, asks=asks,delta_bid=0.002,delta_ask=0.002,ratio=1.,bid_weight=0.2,wall=-0,reciprocal=True)
        sell2=False 
        if r2 <1.0:
            sell2=True
        elapsed=datetime.now()-found_trade.open_date  
        elapsed_min=elapsed.total_seconds()//60
        elapsed_min2=max(0,elapsed_min-20)
        factor=max(0.8,1-elapsed_min2*0.005)    
        if len(bb)>0 and len(ema)>0:  
           # print(f"{ema[-1]} {bb[-1].lb}")    
    
            if ema[-1] < 1*factor*bb[-1].lb:
                sell_1=True
        
        sell=False
        if sell_1 and sell2:
            pi.sell_signal=prev_sell_signal+1
           
            #print("should sell")    
            #print(datetime.now())
            
            #self.execute_sell(found_trade,asks[0][0],SellType.CUSTOM_SELL)

            #print(f"{pair} : min pct {min_pct} {gain}")
        #if pi.min_pct <-0.003 and gain > max(pi.min_pct+0.006,0.0005):
                #print(f"sell min pct {min_pct} {gain}")
        #        sell=True     

        if gain >0.003 or  sell:
            self.execute_sell(found_trade,sell_price,SellType.ROI)
       
             
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:         
        return dataframe
    
            
    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe.index.max(),"buy"]=0 

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe.index.max(),"sell"]=0 
        return dataframe
