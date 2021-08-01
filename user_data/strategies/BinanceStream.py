import time
from talipp.indicators.Indicator import Indicator
from binance import Client
from binance import ThreadedWebsocketManager, ThreadedDepthCacheManager
from talipp.indicators import EMA, SMA ,BB

time_map={
    "1m":60,
    "5m":5*60,
    "15m":15*60,
    "30m":30*60,
    "1h":60*60,
}
keys_map={
    "o":1,
    "h": 2,
    "l":3,
    "c":4,
    "v":5
}
_register = {}



class BasePairInfo: 
    _data={}
    ft= None
    def __init__(self,pair):
        self.buy_signal=0
        self.pair=pair
        self.sell_signal=0
        self.should_buy=False
        self.should_sell=False
    def buy(self,price=None):
        self.should_buy=True   
    def check_buy(self):
        res=self.should_buy
        self.should_buy=False
        return res    
    def sell(self,price=None):
        self.should_sell=True   
    def check_sell(self):
        res=self.should_sell
        self.should_sell=False
        return res    
    
    @classmethod
    def set_ft(cls,ft):
        cls.ft=ft    
    @classmethod
    def get(cls,pair):
        key=pair.replace("/","")
        res = cls._data.get(key,None)
        if res is None:
            cls._data[key]=cls(pair) 
        return cls._data[key]
ohlcv=["o","h","l","c","v"]
class SimpleIndicator(Indicator):
     
     def _calculate_new_value(self):
        if len(self.input_values) > 0:
            return self.input_values
        return None 
class BaseIndicator:
    _class_init=False
    registered={}
    _backtesting=False
    not_initialized=True           
    @classmethod
    def class_init(cls):
        cls._class_init=True
        if not cls._backtesting:
            cls.twm = ThreadedWebsocketManager()
            cls.twm.start()
    def _calculate_new_value(self):
        if len(self.input_values) > 0:
            return self.input_values
        return None
    def __init__(self,symbol,prefetch=True,timeframe="1m",min_hist=100,currency=None): 
 
        if(BaseIndicator._class_init == False):
            BaseIndicator.class_init() 
        self.symbol=symbol.replace("/","")     
        if currency is not None:
           self.data_symbol=symbol.split("/")[0]+currency
        else:
            self.data_symbol=self.symbol
        
        self.prefetch=prefetch
        self.timeframe =timeframe
        self.min_hist=min_hist
        self.path = BaseIndicator.get_path(symbol, timeframe)
        for f in ohlcv:
            setattr(self, f, SimpleIndicator())
       
        if not self._backtesting:
            self.sock=self.twm.start_kline_socket(callback=self.process_message, symbol=self.data_symbol,interval=timeframe)
            time.sleep(0.5)
        
    def process_message(self, msg):

        if msg['e'] == 'error':
            print("socket error!!!")
        else:
            k=msg["k"]
            if self.not_initialized and self.prefetch:
                client = Client()
                tf=time_map[self.timeframe]*1000 
                end=int(k["t"])+2*tf
                start=end-tf*self.min_hist
                res=client.get_klines(symbol=self.data_symbol, interval=self.timeframe,startTime=start,endTime=end) 
                print(res)
                for a in res:
                    for f in ohlcv:
                        val = a[keys_map[f]]
                        getattr(self, f).add_input_value(float(val))
                BasePairInfo.get(self.symbol).new_candle()
                self.not_initialized = False
            else:    
                if k["x"]:
                    for f in ohlcv:
                        indicator=getattr(self, f)
                        indicator.add_input_value(float(k[f]))
                        if(len(indicator)>2*self.min_hist):
                            indicator.purge_oldest(self.min_hist)
                    BasePairInfo.get(self.symbol).new_candle()

    @staticmethod
    def get_path(symbol, interval):
        return f'{symbol.lower()}@kline_{interval}'

