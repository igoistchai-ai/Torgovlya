import numpy as np
import pandas as pd

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def sma(s, n): return s.rolling(n).mean()
def rsi(s, n=14):
    d=s.diff(); up=d.clip(lower=0); dn=-d.clip(upper=0)
    rs=up.ewm(alpha=1/n, adjust=False).mean()/dn.ewm(alpha=1/n, adjust=False).mean()
    return 100-(100/(1+rs))
def atr(df, n=14):
    pc=df.close.shift(1)
    tr=pd.concat([(df.high-df.low),(df.high-pc).abs(),(df.low-pc).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()
def macd(s):
    m=ema(s,12)-ema(s,26); sig=m.ewm(span=9,adjust=False).mean()
    return m,sig,m-sig
def bollinger(s,n=20,k=2):
    mid=s.rolling(n).mean(); sd=s.rolling(n).std()
    return mid,mid+k*sd,mid-k*sd

def compute(df):
    out={}
    for n in [9,20,21,50,100,200]: out[f"EMA{n}"]=ema(df.close,n).iloc[-1]
    out["RSI14"]=rsi(df.close).iloc[-1]
    m,s,h=macd(df.close); out.update({"MACD":m.iloc[-1],"MACD_SIGNAL":s.iloc[-1],"MACD_HIST":h.iloc[-1]})
    mid,up,lo=bollinger(df.close); out.update({"BB_MID":mid.iloc[-1],"BB_UPPER":up.iloc[-1],"BB_LOWER":lo.iloc[-1]})
    out["ATR14"]=atr(df).iloc[-1]
    out["VolumeSMA20"]=df.volume.rolling(20).mean().iloc[-1]
    return {k: (None if pd.isna(v) else float(v)) for k,v in out.items()}
