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

def singleton(cls):
   def wrapper(*args, **kw):
       if cls not in _register:
           instance = cls(*args, **kw)
           _register[cls] = instance
       return _register[cls] 

   wrapper.__name__ = cls.__name__
   return wrapper


@singleton
class BaseIndicatorsManager:
    backtesting=False
    base_indicators={}

BaseIndicatorsManager = BaseIndicatorsManager()


class BaseIndicator(Indicator):
    _class_init=False
    registered={}
    _backtesting=False
               
    @classmethod
    def class_init(cls):
        cls._class_init=True
        if not BaseIndicatorsManager.backtesting:
        
            cls.twm = ThreadedWebsocketManager()
            cls.twm.start()
    def _calculate_new_value(self):
        if len(self.input_values) > 0:
            return self.input_values
        return None
    def __init__(self,symbol,prefetch=True,interval="1m",min_hist=100,field='c'): 
        super().__init__()
 
        if(BaseIndicator._class_init == False):
            BaseIndicator.class_init() 
        symbol=symbol.replace("/BUSD","USDT")
        self.symbol=symbol
        self.prefetch=prefetch
        self.interval =interval
        self.min_hist=min_hist
        self.field=field
        self.path = BaseIndicator.get_path(symbol, interval)
        BaseIndicatorsManager.base_indicators[self.path]=self
        if not BaseIndicatorsManager.backtesting:
            print("init socket")
            self.sock=self.twm.start_kline_socket(callback=self.process_message, symbol=symbol,interval=interval)
        
        time.sleep(0.5)
        
    # check for it like so
    def process_message(self, msg):
        if msg['e'] == 'error':
            print("socket error!!!")
        else:
            k=msg["k"]
            if k["x"]:
                if len (self)==0 and self.prefetch:
                   client = Client()

                   end=int(k["t"])
                   start=end-time_map[self.interval]*1000*self.min_hist
                   print(f"fetch {start} {end}")
                   res=client.get_klines(symbol=self.symbol, interval=self.interval,startTime=start,endTime=end) 
                   for a in res:
                        val = a[keys_map[self.field]]
                        self.add_input_value(float(val))       
                self.add_input_value(float(k[self.field]))
                self.purge_oldest(1)


    @staticmethod
    def get_path(symbol, interval):
        return f'{symbol.lower()}@kline_{interval}'

if __name__ == "__main__":
        #date_time_str = '26/06/21 20:50+02:00'
        bi=BaseIndicator("ADAUSDT")
        bb=BB(40,20,input_indicator=bi)
        #for a in range(100):
        while True:

            time.sleep(1)
            if len(bb)>0:
                print(bb[-1])
        
        #cProfile.run('run()')
