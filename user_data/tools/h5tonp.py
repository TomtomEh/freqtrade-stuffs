import h5py
import numpy as np
from os import listdir
import os
from os.path import isfile, join
mypath="../../depth/h5/ADA/"
files = [int(os.path.splitext(f)[0]) for f in listdir(mypath) if isfile(join(mypath, f))]
files=np.array(files)
for h5 in files:
    try:
        hfile=h5py.File(f"{mypath}{h5}.h5", 'r') 

        keys = [int(f) for f in hfile.keys()]
        keys=np.array(keys)
        keys=np.sort(keys)
        output_file = open(f"{mypath}{h5}.np",  'wb')

        for k in keys:
                      
            bids=np.array(hfile.get(str(k)).get("bids")).astype(dtype="float32")
            asks=np.array(hfile.get(str(k)).get("asks")).astype(dtype="float32")
            ohlcv=np.array(hfile.get(str(k)).get("ohlcv")).astype(dtype="float32")
            header=np.array([int(k),len(bids),len(asks),len(ohlcv)],dtype="int32")
            header.tofile(output_file)
            bids.tofile(output_file)
            asks.tofile(output_file)
            ohlcv.tofile(output_file)

        output_file.close()    
    except:
         pass       