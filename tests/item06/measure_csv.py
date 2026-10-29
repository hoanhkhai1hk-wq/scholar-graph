"""Actual local NumPy timing experiment, not invented paper/model accuracy data."""
import csv,time,platform,os
for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='1'
from statistics import median
import numpy as np
from contextlib import nullcontext
from common import BASE,write
if __name__=='__main__':
    path=BASE/'matrix-timings.csv';assert not path.exists();rng=np.random.default_rng(20261029);rows=[];raw=[]
    with nullcontext():
        for n in [64,128,256,512,1024]:
            a=rng.normal(size=(n,n));b=rng.normal(size=(n,n));row={'dimension':n}
            for name,operation in [('matmul_ms',np.matmul),('add_ms',np.add),('multiply_ms',np.multiply)]:
                operation(a,b);samples=[]
                for _ in range(7):
                    start=time.perf_counter_ns();value=operation(a,b);samples.append((time.perf_counter_ns()-start)/1e6)
                    assert np.isfinite(value).all()
                row[name]=round(median(samples),6);raw.append({'dimension':n,'operation':name,'milliseconds':samples})
            rows.append(row)
    with path.open('w',newline='',encoding='utf8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write(BASE/'matrix-experiment.json',{'origin':'actual local NumPy operations; not published paper experiments','numpy':np.__version__,'platform':platform.platform(),'seed':20261029,'blas_threads_requested':1,'actual_thread_count':'not independently measured','repetitions':7,'statistic':'median milliseconds rounded to six decimals','raw_measurements':raw,'rows':rows})
    print(rows)
