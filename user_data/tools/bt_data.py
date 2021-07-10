import numpy as np
import h5py
import os

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
hf_date={}

def save(pair, t,arr):
    h=t//(60*60)
    h*=60*60
    hfile=None
    try:
        hfile=hf_arr.get(pair,h5py.File(f"depth/{pair}/{h}.h5", 'a'))
    except FileNotFoundError:
        
        os.makedirs(f"depth/{pair}/")
        hfile=hf_arr.get(pair,h5py.File(f"depth/{pair}/{h}.h5", 'a'))

    hf_arr[pair]=hfile    
    g=hfile.create_group(str(t))
    g.create_dataset("asks",data=arr["asks"])
    g.create_dataset("bids",data=arr["bids"])
    g.create_dataset("ohlcv",data=arr["ohlcv"].astype("float32"))   
    hfile.flush()