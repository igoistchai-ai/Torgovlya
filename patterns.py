import numpy as np

def candle_patterns(df):
    x=[]
    a,b,c=df.iloc[-3],df.iloc[-2],df.iloc[-1]
    body=abs(c.close-c.open); rng=max(c.high-c.low,1e-12)
    upper=c.high-max(c.open,c.close); lower=min(c.open,c.close)-c.low
    if body/rng < .1: x.append("Doji")
    if lower >= body*2 and upper <= body*.6: x.append("Hammer-like")
    if upper >= body*2 and lower <= body*.6: x.append("Shooting-Star-like")
    if b.close<b.open and c.close>c.open and c.open<=b.close and c.close>=b.open: x.append("Bullish Engulfing")
    if b.close>b.open and c.close<c.open and c.open>=b.close and c.close<=b.open: x.append("Bearish Engulfing")
    return x

def structure(df, lookback=30):
    highs=df.high.iloc[-lookback:]; lows=df.low.iloc[-lookback:]
    hh=highs.iloc[-1] > highs.iloc[:-1].max() if len(highs)>1 else False
    ll=lows.iloc[-1] < lows.iloc[:-1].min() if len(lows)>1 else False
    if hh: bias="BULLISH_BOS"
    elif ll: bias="BEARISH_BOS"
    else: bias="RANGE_OR_UNCONFIRMED"
    return {"bias":bias,"recent_high":float(highs.max()),"recent_low":float(lows.min())}
