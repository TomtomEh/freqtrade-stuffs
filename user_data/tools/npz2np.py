import numpy as np
import h5py
import os
from os import listdir

from os.path import isfile, join

pair="ADA"
mypath=f"depth/{pair}2/"
files = [int(os.path.splitext(f)[0]) for f in listdir(mypath) if isfile(join(mypath, f))]
files=np.array(files)
files=np.sort(files)
def find_hour(f):
    h=f//(60*60)
    h*=60*60
    return h
h_prev=None
hfile=None
for f in files:
    h=find_hour(f)
    if h_prev is None or h!=h_prev:
        if hfile is not None:
            output_file.close()
        output_file = open(f"depth/{pair}_last/{h}.np",  'ab')
 
    arr=np.load(f"depth/{pair}2/{f}.npz")
    h_prev=h
    
    asks=arr["asks"].astype(dtype="float32")   
    bids=arr["bids"].astype(dtype="float32")   
    ohlcv=arr["ohlcv"].astype(dtype="float32")  
    header=np.array([int(f),len(bids),len(asks),len(ohlcv)],dtype="int32")
    header.tofile(output_file)
    bids.tofile(output_file)
    asks.tofile(output_file)
    ohlcv.tofile(output_file)

output_file.close()
