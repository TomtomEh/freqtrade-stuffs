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

logger = logging.getLogger(__name__)

import numpy as np
from binance import Client
from binance import ThreadedWebsocketManager, ThreadedDepthCacheManager

from binance.exceptions import BinanceAPIException
import time
from typing import Any, Callable, Dict, List, Optional

from user_data.strategies.BinanceWS import BinanceWS
class OBOnlyWS(BinanceWS):
    INTERFACE_VERSION = 2


    stoploss = -0.11  


    timeframe = '1m'
    use_sell_signal = True
    sell_profit_only = False
    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True 
    max_pct={}
    min_pct={}
    buy_signal={}
    ratio={}
    def check_sell(self,bids, asks, pair):
        sell_price=(0.1*bids[0][0]+0.9*asks[0][0])
        ob_price=(0.2*bids[0][0]+0.8*asks[0][0])
        mid_price=(0.5*bids[0][0]+0.5*asks[0][0])
        found_trade= self.open_trades(pair=pair)
        
        if(found_trade == None):
            return
        found_trade= self.open_trades(force=True,pair=pair)
        if(found_trade == None):
            return
        gain = (mid_price-found_trade.open_rate)/found_trade.open_rate
        sell_price1=found_trade.open_rate*1.002
        elapsed=datetime.now()-found_trade.open_date  
        elapsed_min=elapsed.total_seconds()//60
        count_down=max(0,elapsed_min-6)        
        ask_ratio=1.003-count_down*0.0005
        sell_price=    asks[0][0]*(ask_ratio)
        
        """sell_price3=    asks[0][0]
        if sell_price3 >sell_price:
            sell_price=sell_price3
        else:
            sell_price=sell_price2
        """
        self.max_pct[pair]=max(gain,self.max_pct.get(pair,0))
        self.min_pct[pair]=min(gain,self.min_pct.get(pair,0))
        gain2=False
        #if gain > 0.004:
        lk=self.current_kline.get(pair)
        if lk and float(lk["o"]) < asks[0][0]:
                return
<<<<<<< Updated upstream
        elapsed=datetime.now()-found_trade.open_date  
        if elapsed < timedelta(minutes=2):
            return
        if gain < -0.001:
            sell_price= asks[0][0]    
        self.execute_sell(found_trade,sell_price,SellType.ROI)
        return
        dyn_roi=0.007
=======
       
        dyn_roi=0.006
>>>>>>> Stashed changes
        elapsed=datetime.now()-found_trade.open_date  

        #print(elapsed.total_seconds()/60)
        #print((elapsed-timedelta(minutes=1000)).total_seconds())
        dyn_roi = max (0.002,0.0055-0.0002*(max(0,(elapsed-timedelta(minutes=10)).total_seconds()/60)))
        #print(dyn_roi)
       
        sell=False
        #if self.max_pct[pair]>0:
        sell_price=asks[0][0]*1.001
        #print(f"{pair} : max pct {max_pct} {gain}")
        if gain < -0.005:
            sell_price=bids[0][0]*0.99

        if gain >dyn_roi  :
            print(f"max: {self.max_pct[pair]} {self.min_pct[pair]}")
            self.execute_sell(found_trade,sell_price,SellType.ROI)
        #if gain < -0.005  :
        #    print(f"max: {self.max_pct[pair]} {self.min_pct[pair]}")
        #    self.execute_sell(found_trade,sell_price,SellType.ROI)

        #if  elapsed > timedelta(minutes=20)and gain >0.002:
            #print(f"max: {self.max_pct[pair]}")
        #    self.execute_sell(found_trade,sell_price,SellType.ROI)

        sell1,r1=self.check_ob(pair,bids=bids, asks=asks,delta_bid=0.0045,delta_ask=0.002,ratio=1.3,bid_weight=0.2,reciprocal=True)
        sell2,r2=self.check_ob(pair,bids=bids, asks=asks,delta_bid=0.002,delta_ask=0.002,ratio=1.,bid_weight=0.2,wall=-0.5,reciprocal=True)

        if sell1 or sell2:
            print(f"max: {self.max_pct[pair]} {self.min_pct[pair]}")
            self.execute_sell(found_trade,sell_price,SellType.CUSTOM_SELL)
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
    def check_buy(self,bids, asks, pair):
        delta_bid=0.003
        delta_ask=0.012
        prev_buy_signal=self.buy_signal.get(pair,0)
        self.buy_signal[pair]=0
        open_trades= self.open_trades()
        if len (open_trades) >= self.max_trades or self.no_trade_until > datetime.now():
            return
        mid_price=(1*bids[0][0]+1*asks[0][0])/2
        lk=self.current_kline.get(pair)
        if lk and (0.0*float(lk["l"])+1.0*float(lk["o"])) > bids[0][0]:
            return
        buy1,r1=self.check_ob(pair,bids, asks,delta_bid=delta_bid,delta_ask=delta_ask,ratio=1.3)
        buy2,r2=self.check_ob(pair,bids, asks,delta_bid=0.003,delta_ask=0.004,wall=0.3,ratio=1.3) 
        buy3,r3=self.check_ob(pair,bids, asks,delta_bid=0.002,delta_ask=0.002,wall=0.4,ratio=1.7)

        #if pair == "ADA/BUSD":
<<<<<<< Updated upstream
        #    print(f"{datetime.now()} {pair} {r1} {r2} {r3}")
        if  True or buy2 and buy3:
=======
        #print(f"{datetime.now()} {pair} {r1} {r2} {r3}")
        if  buy2 and buy3:
>>>>>>> Stashed changes
            self.buy_signal[pair]=prev_buy_signal+1
            if self.buy_signal[pair] <6:
                
                return
            found_trade = None

            for trade in self.open_trades(True) :
                if trade.pair.replace("/","") == pair.replace("/",""):
                    found_trade = trade
            if found_trade:
                return

            stake_amount = self.ft.wallets.get_trade_stake_amount(pair)
            with self.ft._sell_lock:
                self.max_pct[pair]=0
                self.min_pct[pair]=0
                self.ft.execute_buy(pair,stake_amount,(0.3*bids[0][0]+0.7*asks[0][0]))
        else:
            self.buy_signal[pair]=0
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:         
        return dataframe
    
            
    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe.index.max(),"buy"]=0 
        dataframe.loc[dataframe.index.max(),"ratio"]=self.ratio.get(metadata["pair"],1) 

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe.index.max(),"sell"]=0 
        return dataframe
