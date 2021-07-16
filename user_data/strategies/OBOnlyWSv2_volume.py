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
#TODO: Start from trailing from -0.002 
#TODO: reduce buy  
#todO: test walls
#import debugpy
#debugpy.listen(5678)
#debugpy.wait_for_client()
""" Binance exchange subclass """
import logging
from typing import Any, Dict, List, Optional, Tuple

from pandas import DataFrame
from datetime import datetime,timedelta

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
        self.ob_bb=BB(300,1.8)
        self.bbp=BB(20*60,2)

        self.ob_ema=EMA(9)
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
        bid_side,ask_side=self.ob_cut( bids, asks,delta_bid,delta_ask,bid_weight)
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

    def new_ob(self,bids, asks, pair):
        pi=PairInfo.get(pair)

        bb=pi.ob_bb
        ema=pi.ob_ema
        pi.buy,r2=self.check_ob(pair,bids, asks,delta_bid=0.002,delta_ask=0.002,wall=0.4,ratio=1.7)
        bid_side,ask_side=self.ob_cut( bids, asks,delta_bid=00.2)
        mid_price=(1*bids[0][0]+1*asks[0][0])/2

        no_wall=bid_side[bid_side[:,1]<0.4*np.sum(bid_side[:,1])]
        r2=np.sum(no_wall[:1])/np.sum(ask_side[:,1])
        bbp=pi.bbp
        if len(bbp)>0:      
           
                bbp.add_input_value(mid_price)
                bbp.purge_oldest(1)
        else:
                bbp.add_input_value(mid_price)  

        bid_side,ask_side=self.ob_cut( bids, asks,delta_bid=00.2)

        if len(ema)>0:      
           
            ema.add_input_value(r2)
            ema.purge_oldest(1)
            if len(bb)>0:      
           
                bb.add_input_value(ema[-1])
                bb.purge_oldest(1)
            else:
                bb.add_input_value(ema[-1])   
        else:
             ema.add_input_value(r2)

    def check_buy(self,bids, asks, pair):
        pi=PairInfo.get(pair)
        buy_cond=[]

        prev_buy_signal=pi.buy_signal
        pi.buy_signal=0
        open_trades= self.open_trades()
        if len (open_trades) >= self.max_trades or self.no_trade_until > datetime.now():
            return
        mid_price=(1*bids[0][0]+1*asks[0][0])/2
        lk=self.last_kline.get(pair)
        ck=self.current_kline.get(pair)
        
        if ck and (0.0*float(ck["l"])+1.*float(ck["o"])) > bids[0][0]:
            return
        bid_side,ask_side=self.ob_cut( bids, asks,delta_bid=00.2)
        no_wall=bid_side[bid_side[:,1]<0.4*np.sum(bid_side[:,1])]
        bbp=pi.bbp
           


        r2=np.sum(no_wall[:,1])
        buy3=False
        buy4=False
        if pi.buy:
            buy_cond.append("pi.buy")
 
        if lk and r2>2*float(lk["v"]) :
            buy3=True
            buy_cond.append("buy3")
        if len(bbp)>0 and mid_price<bbp[-1].lb:
            buy4=True
            buy_cond.append("buy4")

        
        #buy1,r1=self.check_ob(pair,bids, asks,delta_bid=delta_bid,delta_ask=delta_ask,ratio=1.3)
        #buy2,r2=self.check_ob(pair,bids, asks,delta_bid=0.003,delta_ask=0.004,wall=0.3,ratio=1.3) 
        buy2=False
        bb=pi.ob_bb
        ema=pi.ob_ema
        if len(bb)>0 and len(ema)>0:      
            if ema[-1] > 1.2*bb[-1].ub:
                buy2=True
                buy_cond.append("buy2")
        if len(buy_cond)==3:
           print(buy_cond)
        if buy4  and  buy3  and buy2: 
            pi.buy_signal=prev_buy_signal+1
            if pi.buy_signal <3:
                
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
        
        
        sell_1=False
        bb=pi.ob_bb
        ema=pi.ob_ema
        sell2,r2=self.check_ob(pair,bids=bids, asks=asks,delta_bid=0.002,delta_ask=0.002,ratio=1.,bid_weight=0.2,wall=-0,reciprocal=True)
        sell2=False 
        if r2 <1.0:
            sell2=True
        if len(bb)>0 and len(ema)>0:      
            if ema[-1] < 1.8*bb[-1].lb:
                sell_1=True
        
        
        if sell_1 and sell2:
            pi.sell_signal=prev_sell_signal+1
            #if pi.sell_signal <3:
                
            #    return
            self.execute_sell(found_trade,mid_price,SellType.CUSTOM_SELL)

        elapsed=datetime.now()-found_trade.open_date  
        #print(elapsed.total_seconds()/60)
        dyn_roi = max (0.002,0.004-0.0015*elapsed.total_seconds()/60)
       
        sell=False
        #if self.max_pct[pair]>0:
        max_pct=pi.max_pct
        #print(f"{pair} : max pct {max_pct} {gain}")
        if  gain >0 and max_pct >(dyn_roi) and gain < max_pct-0.0005:
        #    print(f"sell max pct {max_pct} {gain} {dyn_roi}")
            sell=True     
        else:
           if gain > dyn_roi:
                sell = True

       
        if pi.min_pct<0:
            min_pct=pi.min_pct
            #print(f"{pair} : min pct {min_pct} {gain}")
            #if min_pct <-0.004 and gain > min_pct+dyn_roi:
                #print(f"sell min pct {min_pct} {gain}")
                #sell=True     
        if sell: 
            self.execute_sell(found_trade,sell_price,SellType.ROI)
       
             
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:         
        return dataframe
    
            
    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe.index.max(),"buy"]=0 

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe.index.max(),"sell"]=0 
        return dataframe
