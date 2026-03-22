import pandas as pd
import numpy as np

def get_squeeze_status(df, length=20, mult_bb=2.0, mult_kc=1.5):
    """
    Returns the squeeze status: 
    'ON' (Black Cross), 'RELEASED' (Gray Cross), or 'OFF' (Already out)
    """
    if len(df) < length + 2:
        return "INSUFFICIENT_DATA"

    # 1. Basis (SMA 20)
    sma = df['Close'].rolling(window=length).mean()
    std = df['Close'].rolling(window=length).std()
    
    # 2. Bollinger Bands
    df['bb_up'] = sma + mult_bb * std
    df['bb_low'] = sma - mult_bb * std
    
    # 3. Keltner Channels (Using ATR)
    df['tr'] = np.maximum((df['High'] - df['Low']),
                          np.maximum(abs(df['High'] - df['Close'].shift()),
                                     abs(df['Low'] - df['Close'].shift())))
    df['atr'] = df['tr'].rolling(window=length).mean()
    df['kc_up'] = sma + mult_kc * df['atr']
    df['kc_low'] = sma - mult_kc * df['atr']
    
    # 4. Squeeze Logic
    # True = Squeeze ON (Black), False = Squeeze OFF (Gray)
    df['sqz_on'] = (df['bb_up'] < df['kc_up']) & (df['bb_low'] > df['kc_low'])
    
    # 5. Momentum Histogram (Linear Regression)
    highest = df['High'].rolling(window=length).max()
    lowest = df['Low'].rolling(window=length).min()
    val = df['Close'] - ((highest + lowest)/2 + sma) / 2
    
    # Simple LinReg Slope
    def linreg(s):
        x = np.arange(len(s))
        return np.polyfit(x, s, 1)[0]
    
    df['mom'] = val.rolling(window=length).apply(linreg, raw=True)
    
    # Check for the Transition (Black -> Gray)
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    if prev['sqz_on'] == True and curr['sqz_on'] == False:
        return "RELEASED", curr['mom']
    elif curr['sqz_on'] == True:
        return "ON", curr['mom']
    
    return "OFF", curr['mom']
