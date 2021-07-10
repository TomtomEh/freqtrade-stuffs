from freezegun import freeze_time
import os
import sys
sys.path.append("E:/users/e5n/nosave/perso/sw/investing/tmp/freqtrade")
sys.path.append("E:/users/e5n/nosave/perso/sw/investing/tmp/freqtrade/user_data/strategies")

#from OBOnlyWS import OBOnlyWS
from OBOnlyWSv2 import OBOnlyWSv2
#from OBOnlyWSv2reverse import OBOnlyWSv2reverse

#from OBOnlyWSnext import OBOnlyWSnext
from datetime import datetime,timedelta,timezone
import os
from threading import Lock
import time
import h5py
from freqtrade.persistence import LocalTrade,Order

from os import listdir
from os.path import isfile, join
import numpy as np
import pandas as pd
class Wallets:
    def get_trade_stake_amount(self,pair):
        return 100    
class bt_DepthCache:
    bids=None
    asks=None
    symbol="ADAUSDT"
    def get_bids(self):
        return self.bids
    def get_asks(self):
        return self.asks    
           
class MyFT:
    trades=[]
    _open_trades=[]
    wallets=Wallets()
    _sell_lock=Lock()
    #wallets=MyWallet()
    def open_trades(self,pair):
        if pair:
            for trade in self._open_trades :
                return trade
            return None    
        return self._open_trades 
    closed_kline=False           
    def execute_buy(self,pair,stake_amount,price):
        if len(self._open_trades) >0:
            return
        print(datetime.now())
        print("buy")
        trade=LocalTrade()
        o=Order()
        o.status="open"
        o.side="buy"
        o.order_date=datetime.now()

        trade.orders.append(o)
        trade.pair=pair
        trade.open_rate=price
        trade.open_date=datetime.now()
        self._open_trades.append(trade)
        self.closed_kline=False
    

    def execute_sell(self,trade,price,reason):
        #print("sell")

        trade.close_rate=price
        o=Order()
        o.status="open"
        o.side="sell"
        o.order_date=datetime.now()
        trade.sell_reason=reason
        self.closed_kline=False

        trade.orders.append(o)
    gain=[]
    last_data= None
    last_price=0
    def check_price(self,dc,msg):
        if self.last_data is not None:
            elapsed_lp=datetime.now()-self.last_data
            
            if self.last_data is not None and elapsed_lp > timedelta(minutes=30):
                if self.last_price != 0:
                        interval=elapsed_lp.total_seconds()//60
                        change=(float(msg["k"]["c"])-self.last_price)/self.last_price  
                        print(f">>>>>skiped!!!! {interval} min {change}")
                        self._open_trades.clear()
                       
        for t in self._open_trades:
            for o in t.orders:
                #print(o.status)
                if o.status == "open":
                    if o.order_date < datetime.now() -timedelta(minutes=2):
                        if o.side =="buy":
                            t=self._open_trades.pop()
                            t.orders.clear() 
                            print("buy canceled")
                        else:
                            print("sell canceled")

                        o.status="canceled"
                        break    
                    if o.side =="buy":
                        best_price=float(msg["k"]["c"]) 
                        #if self.closed_kline:
                        #    best_price=float(msg["k"]["l"])
                        if t.open_rate>= dc.asks[0][0] or t.open_rate>= best_price:
                            
                            o.status="closed"
                    if o.side =="sell":
                        best_price=float(msg["k"]["c"]) 

                        if self.last_data is not None and (datetime.now()-self.last_data) > timedelta(minutes=30):
                            self.last_data=datetime.now()
                            t=self._open_trades.pop()
                            t.orders.clear() 
                            print("remove trade")
                        
                        
                            break
                        #if self.closed_kline:
                        #    best_price=float(msg["k"]["h"])
                        if t.close_rate <= dc.bids[0][0] or t.close_rate <=  float(msg["k"]["h"]):
                           
                            #f=open("trades2.csv", "a+")
                            gain=(t.close_rate-t.open_rate)/t.open_rate
                            print(f"{t.open_date} {datetime.now()}, {t.pair}, {t.open_rate}, {t.close_rate}, {gain} {t.sell_reason.sell_type}\n")
                            #f.close()
                            self.gain.append(gain-0.00075)
                            #self.gain.append(gain-0.00075)
                            gain=np.array(self.gain)

                            print(np.sum(gain))     
                            t=self._open_trades.pop()
                            
                            t.orders.clear()
                            self.trades.append(t)
                            o.status="closed"
                    if msg["k"]["x"]:
                        self.closed_kline=True
     
        self.last_data=datetime.now()    
    
        self.last_price=float(msg["k"]["c"]) 
        
    def get_trades(self):
        res = []
        for key in self.trades:
            res.append(self.trades[key])
        return res




class OBBacktest:
    strat_data={}
    
    def __init__(self,start,end,stratClass=OBOnlyWSv2,stride=1):
        #date_time_str = '02/08/21 19:00+02:00'

        #date_time_str = '29/06/21 00:00+02:00'

        #date_time_str = '26/06/21 20:50+02:00'
        end_time = datetime.strptime(end, '%d/%m/%y %H:%M')
        end=int(end_time.timestamp())
        #date_time_str = '02/07/21 12:00+02:00'
        # date_time_str = '28/06/21 02:00+02:00'

        start_time = datetime.strptime(start, '%d/%m/%y %H:%M')

        start=int(start_time.timestamp())
        print(start)






        mypath="../../depth/h5/ADA/"
        files = [int(os.path.splitext(f)[0]) for f in listdir(mypath) if isfile(join(mypath, f))]
        files=np.array(files)
        files=np.sort(files)
        start_file=files[files<start]
        if len(start_file) >0:
            start_file=start_file[-1]
        else:
            start_file=files[0]

        end_file=files[files<end]
        if len(end_file) >0:
            end_file=end_file[-1]
        else:
            end_file=files[-1]


        ds=files[files>=start_file]
        
        ds=ds[ds<=end_file]
        ds=np.sort(ds)
        conf={
                "dry_run":True,
                "stake_currency":"BUSD",
                "exchange": {
                    "name": "binance",
                    "key": "qsdfqsd",
                    "secret": "qsdfqsdf",
                    "ccxt_config": {"enableRateLimit": True},
                    "ccxt_async_config": {
                        "enableRateLimit": True,
                        "rateLimit": 1000
                    },
                    "pair_whitelist":[],
                    "pair_blacklist":[],
                }
            }        
        with freeze_time(start_time) as frozen_datetime:
            print(datetime.now())
            frozen_datetime.move_to(start_time)
            print(datetime.now())
            ft=MyFT()
            strat=stratClass(conf)
            self.strat=strat
            strat.ft=ft
            strat.backtesting=True
            self.last_time=datetime.now()

            prev=None
            i=0
            dc=bt_DepthCache()
            max_size=0
            min_size=10000000

            for h5 in ds:
                try:
                    hfile=h5py.File(f"{mypath}{h5}.h5", 'r') 

                    keys = [int(f) for f in hfile.keys()]
                    keys=np.array(keys)
                    keys=np.sort(keys)
                    
                    for k in keys:
                        if k <start:
                            continue
                        if k > end:
                            continue
                        
                        
                        dc.bids=np.array(hfile.get(str(k)).get("bids"))
                        dc.asks=np.array(hfile.get(str(k)).get("asks"))
                        max_size=max(len(dc.bids),max_size)
                        min_size=min(len(dc.asks),max_size)
                        
                        #print(f"ib {ob}")
                        frozen_datetime.move_to(datetime.fromtimestamp(k))
                        ohlcv=np.array(hfile.get(str(k)).get("ohlcv"))
                        if ohlcv[4] == '0':
                            continue
                        if prev is  None :
                            prev=ohlcv
                        x=True
                        if np.array_equal(ohlcv[:5],prev[:5]):
                            x=False
                        
                        msg={"s":"ADAUSDT",
                            "k":{
                                "o":ohlcv[5],
                                "h":ohlcv[6],
                                "l":ohlcv[7],
                                "c":ohlcv[8],
                                "v":ohlcv[9],
                                "V":ohlcv[9],

                                "x":x  
                            }   
                        
                        
                        }
                        elapsed=datetime.now()-self.last_time
                        if elapsed>timedelta(minutes=30)  :
                            print(datetime.now())
                            self.last_time=datetime.now()    
                        strat.handle_socket_message(msg)
                        strat.handle_dcm_message(dc)
                        ft.check_price(dc,msg)
                        ft.last_data=datetime.now()
                        #strat.strat_data.t=k
                        i+=1

                        if i%stride== 0:
                            if hasattr(strat,"strat_data"):
                                if self.strat_data.get("date") is None:
                                    self.strat_data["date"]=[]
                                    self.strat_data["gain"]=[]

                                self.strat_data["date"].append(k)
                                self.strat_data["gain"].append(np.sum(np.array(ft.gain)))
            
                                for key in    strat.strat_data:
                                    if self.strat_data.get(key) is None:
                                        self.strat_data[key]=[]                        
                                    self.strat_data[key].append(strat.strat_data[key])
                            #print(msg)
                        prev=ohlcv

                except Exception as e:
                    print(e)
                    #i+=1
                    #if i >200:
                    #    break
        gain=np.array(ft.gain)
        print(repr(gain))
        print(np.sum(gain))  
        print(f"gain {len(gain[gain>0])}")
        print(len(gain[gain<0]))

    def get_df(self):
        df = pd.DataFrame(self.strat_data)
        df['date']= pd.to_datetime(df['date'],unit='s')   

        df=df.set_index(df['date'])   
        return df  

def run():    
    ob=OBBacktest('29/05/21 10:50','29/07/21 15:30',stride=5*60)
    df=ob.get_df()
    df.to_csv("full_result.csv")
import cProfile
        
if __name__ == "__main__":
        #date_time_str = '26/06/21 20:50+02:00'
        run()
        #cProfile.run('run()')
