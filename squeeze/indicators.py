import pandas as pd
import numpy as np

def get_squeeze_status(df, length=20, mult=2.0, mult_kc=1.5):
    """Calibrated to LazyBear's logic for Forex/Stock consistency."""
    if len(df) < length + 2:
        return "STAY_SILENT", 0

    source = df['Close']
    basis = source.rolling(window=length).mean()
    
    # dev = multKC * stdev (This is the 'Black Dot' math from Pine Script)
    dev = mult_kc * source.rolling(window=length).std()
    upper_bb = basis + dev
    lower_bb = basis - dev
    
    # Keltner Channels
    tr = np.maximum((df['High'] - df['Low']),
                    np.maximum(abs(df['High'] - df['Close'].shift()),
                               abs(df['Low'] - df['Close'].shift())))
    range_ma = tr.rolling(window=length).mean()
    upper_kc = basis + range_ma * mult_kc
    lower_kc = basis - range_ma * mult_kc
    
    # Squeeze Logic
    sqz_on = (lower_bb > lower_kc) & (upper_bb < upper_kc)
    sqz_off = (lower_bb < lower_kc) & (upper_bb > upper_kc)
    
    # Momentum
    highest_h = df['High'].rolling(window=length).max()
    lowest_l = df['Low'].rolling(window=length).min()
    avg_val = ((highest_h + lowest_l)/2 + basis) / 2
    val = source - avg_val
    
    def linreg(s):
        x = np.arange(len(s))
        slope, intercept = np.polyfit(x, s.values, 1)
        return slope * (len(s) - 1) + intercept

    df['val'] = val.rolling(window=length).apply(linreg, raw=False)
    
    # TRIGGER: Only the VERY FIRST Gray dot
    if sqz_on.iloc[-2] == True and sqz_off.iloc[-1] == True:
        return "RELEASED", df['val'].iloc[-1]
    
    return "STAY_SILENT", 0
