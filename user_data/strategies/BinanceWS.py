from freezegun import freeze_time

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

import user_data.tools.bt_data as bt_data
class BinanceWS(IStrategy):
    last_time_refresh=datetime.now()-timedelta(days=60)
    last_time_refresh_trade_count=datetime.now()-timedelta(days=60)
    no_trade_until=(datetime.now()-timedelta(days=20)) 
    def __init__(self,config):
        super().__init__(config) 
        self.last_time_refresh=datetime.now()-timedelta(days=60)
        self.last_time_refresh_trade_count=datetime.now()-timedelta(days=60)
        self.no_trade_until=(datetime.now()-timedelta(days=20)) 
        

    dcm=None
    twm=None
    _open_trades=None
    btc_ratio=1.0
    ksm_data=[0,0,0,0,0,0,0,0,0,0]
    ada_data=[0,0,0,0,0,0,0,0,0,0]

    skip=0
    no_skip=0
    last_kline={}
    current_kline={}
    last_volume={}
    max_trades=2
    
    def pair_trade(self, pair):
        trades = None
        if self.backtesting:
            return self.ft.open_trades(pair) 

        else:
            trades = Trade.get_trades_proxy(pair=pair,is_open=True) 
            for a in trades:
                return a
        return None 
    def execute_sell(self,trade,price,reason):
        with self.ft._sell_lock:
            trade=self.pair_trade(trade.pair)
            if not trade:
                return
            #print(f" should sell {trade.pair} {trade.open_order_id} ")
            #for a in trade.orders:
            #    print (a.status)
            for a in trade.orders:
                if a.status == 'open':
                    return
            if trade and  trade.is_open: 
                try:
                    sell_reason=SellCheckTuple(sell_type=reason)
                    if reason == SellType.STOP_LOSS:
                        self.max_trades=1
                        self.no_trade_until=(datetime.now()+timedelta(minutes=2))
                    if reason == SellType.ROI:
                        self.max_trades+=1
                    self.max_trades=max(1,min(5,self.max_trades))               
                    
                    self.ft.execute_sell(trade,price,sell_reason)
                except Exception as e:
                    print(e)

    def get_trades(self):
        if self.backtesting:
            return ft.get_trades()
        else:
            return 
    def open_trades(self,force=False,pair = None):
        if self.backtesting:
            return self.ft.open_trades(pair) 
        trade_filter = []
        trade_filter.append(Trade.is_open.is_(True))
        if force or not self._open_trades or (datetime.now()-self.last_time_refresh_trade_count) > timedelta(seconds=20):
            query = Trade.get_trades()
        
            self._open_trades = query.populate_existing().filter(*trade_filter).all()
            self.last_time_refresh_trade_count=datetime.now()
        if pair:
            found_trade = None
            for trade in self._open_trades :
            
                if trade.pair.replace("/","") == pair.replace("/",""):
                    found_trade = trade
            return found_trade
        return self._open_trades

    backtesting=False
    def check(self, depth_cache):
        if not self.backtesting:
            t=datetime.fromtimestamp(depth_cache.update_time/1e3)
            if datetime.now()>(t+timedelta(seconds=1)):
                self.skip+=1
                if self.skip %100 ==0:
                    print(f"skipingi{self.skip/(self.no_skip+self.skip)}")
                return
            self.no_skip+=1

        bids=np.array(depth_cache.get_bids())
        asks=np.array(depth_cache.get_asks())
        pair=depth_cache.symbol.replace("USDT","/BUSD")
        if self.backtesting == False:
            bid_weight=0.5
            mid_price=(bid_weight*bids[0][0]+(1-bid_weight)*asks[0][0])
            bid_cut = mid_price - mid_price*0.015
            ask_cut = mid_price + mid_price*0.015
            bid_side=bids[bids[:,0]>bid_cut]
            ask_side=asks[asks[:,0]<ask_cut]
            dr=pair.replace("/BUSD","")
            ticker_data=self.ticker_data.get(dr,None)
            if ticker_data is not None:
                #ob={"asks":ask_side,"bids":bid_side,"ohlcv":np.array(ticker_data)}
                np.savez(f"depth/{dr}/{str(int(datetime.now().timestamp()))}.npz",asks=ask_side,bids=bid_side,ohlcv=np.array(ticker_data))
           
                #bt_data.save(pair,int(datetime.now().timestamp()),ob)
        self.new_ob(bids,asks,pair)
   
        self.check_sell(bids,asks,depth_cache.symbol.replace("/","").replace("USDT","/BUSD"))
        self.check_buy(bids,asks,depth_cache.symbol.replace("/","").replace("USDT","/BUSD"))

    def set_ft(self,ft):
        self.ft=ft


    def refresh_latest_ohlcv(self, pair_list: ListPairsWithTimeframes, *,
                             since_ms: Optional[int] = None, cache: bool = True
                             ) -> Dict[Tuple[str, str], DataFrame]:
        print(pair_list)
        if (datetime.now()-self.last_time_refresh) < timedelta(minutes=30):
            return
        if  self.twm is not None:
            return
        self.client = Client()
        custom_properties={}
        if self.twm:
            self.twm.stop()
        self.twm = ThreadedWebsocketManager()
        self.twm.daemon=True
        self.twm.start()

        if self.dcm:
            self.dcm.stop()
        self.dcm = ThreadedDepthCacheManager()
        self.dcm.daemon=True
        self.dcm.start()
        time.sleep(1)
        klines = self.client.get_historical_klines("BNBBTC", "30m", "1 day ago UTC")
        #print(klines)
        for pair in pair_list:
            limit = custom_properties.get(pair[0],{}).get("max_depth",500)            
            self.twm.start_kline_socket(callback=self.handle_socket_message, symbol=pair.replace("/BUSD","USDT"),interval="1m")
            #start_aggtrade_socket
            time.sleep(0.5)

            self.dcm.start_depth_cache(callback=self.handle_dcm_message, symbol=pair.replace("/BUSD","USDT"),limit=limit)
            time.sleep(0.5)
        open_trades=Trade.get_open_trades()

    ticker_data={}
    def handle_socket_message(self,msg):
        pair=msg["s"].replace("USDT","")
        k=msg["k"]
        ticker_data=self.ticker_data.get(pair,None)
        if ticker_data is None:
            self.ticker_data[pair]=[0]*12
            ticker_data=self.ticker_data[pair]
        if k["x"]:
           self.last_volume[pair+"/BUSD"]=float(msg['k']['v'])
           self.last_kline[pair+"/BUSD"]=k
        else:
           self.current_kline[pair+"/BUSD"]=k

           self.last_volume[pair+"/BUSD"]=max(self.last_volume.get(pair+"/BUSD",0),float(msg['k']['V']))
        if k["x"]:
            ticker_data[0]=k["o"]
            ticker_data[1]=k["h"]
            ticker_data[2]=k["l"]
            ticker_data[3]=k["c"]
            ticker_data[4]=k["v"]
            ticker_data[10]=k["V"]

        else:
            ticker_data[5]=k["o"]
            ticker_data[6]=k["h"]
            ticker_data[7]=k["l"]
            ticker_data[8]=k["c"]
            ticker_data[9]=k["v"]
            ticker_data[11]=k["V"]

                
    def handle_dcm_message(self,depth_cache):
        self.check(depth_cache)
    
