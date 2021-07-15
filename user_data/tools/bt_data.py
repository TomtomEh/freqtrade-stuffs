import numpy as np
import h5py
import os
from datetime import datetime,timedelta,timezone
import threading
from os import listdir
from os.path import isfile, join
def get_data(pair,start, end, skip=0):
    if isinstance(start,int) == False:
      date_time_obj = datetime.strptime(start, '%d/%m/%y %H:%M%z')
      start=int(date_time_obj.timestamp())
    if isinstance(end,int) == False:
      date_time_obj = datetime.strptime(end, '%d/%m/%y %H:%M%z')
      end=int(date_time_obj.timestamp())
    res=[]
    skip+=1
    mypath=f"../../depth/h5/{pair}/"
    files = [int(os.path.splitext(f)[0]) for f in listdir(mypath) if isfile(join(mypath, f))]
    files=np.array(files)
    start_h=(start//(60*60))*60*60
    end_h=(end//(60*60))*60*60
    ds=files[files>=start_h]
    ds=ds[ds<=end_h]
    count=-1
    for h5 in ds:
        hfile=h5py.File(f"{mypath}{h5}.h5", 'r') 

        keys = [int(f) for f in hfile.keys()]
        keys=np.array(keys)
        keys=np.sort(keys)
        for k in keys:
            if k <start:
                continue
            if k > end:
                break
            count+=1
            if count % skip != 0:
               continue
            
            ob={"bids":np.array(hfile.get(str(k)).get("bids")),
                "asks":np.array(hfile.get(str(k)).get("asks")),
                "ohlcv":np.array(hfile.get(str(k)).get("ohlcv")),
                "t":k}
            res.append(ob)
        hfile.close()
    return res        
hf_arr={}
hf_last_arr={}
hf_last_file={}
def get_file(pair,t):
    hfile=hf_arr.get(pair,None)
    if hfile is not None:
        elapsed=datetime.now()-hf_last_file[pair] 
        if t%60==0:
            print('number of current threads is ', threading.active_count()) 
        if elapsed > timedelta(hours=4):
            hfile.close()
            hfile=None
            hf_arr[pair]=None
        else:
            return hfile

    try:
        hfile=hf_arr.get(pair,h5py.File(f"depth/{pair}/{t}.h5", 'a'))
    except FileNotFoundError as e:
        
        print("e")
        os.makedirs(f"depth/{pair}/")
        hfile=hf_arr.get(pair,h5py.File(f"depth/{pair}/{t}.h5", 'a'))
    except Exception as e:
        print(e)
    hf_arr[pair]=hfile
    hf_last_file[pair]=datetime.now()
    return hfile

def save(pair, t,arr):
    h=t//(60*60)
    h*=60*60
    hfile=get_file(pair,t)
    hf_last=hf_last_arr.get(pair,0)
    if t == hf_last:
        return
    hf_last_arr[pair]=t
    try:  
        g=hfile.create_group(str(t))
        g.create_dataset("asks",data=arr["asks"])
        g.create_dataset("bids",data=arr["bids"])
        g.create_dataset("ohlcv",data=arr["ohlcv"].astype("float32"))   
        hfile.flush()

    except Exception as e:
        print(e) 
