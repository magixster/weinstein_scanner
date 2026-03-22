import pandas as pd
import numpy as np

def get_squeeze_status(df, length=20, mult=2.0, length_kc=20, mult_kc=1.5, use_tr=True):
    if len(df) < length + 2:
        return "STAY_SILENT", 0

    source = df['Close']
    basis = source.rolling(window=length).mean()
    
    # --- 1. BOLLINGER BANDS (CALIBRATED) ---
    # LazyBear line 18: dev = multKC * stdev(source, length)
    # This is why standard 2.0 bands didn't match the black dots!
    dev = mult_kc * source.rolling(window=length).std()
    upper_bb = basis + dev
    lower_bb = basis - dev
    
    # --- 2. KELTNER CHANNELS ---
    if use_tr:
        tr = np.maximum((df['High'] - df['Low']),
                        np.maximum(abs(df['High'] - df['Close'].shift()),
                                   abs(df['Low'] - df['Close'].shift())))
        range_ma = tr.rolling(window=length_kc).mean()
    else:
        range_ma = (df['High'] - df['Low']).rolling(window=length_kc).mean()
        
    upper_kc = basis + range_ma * mult_kc
    lower_kc = basis - range_ma * mult_kc
    
    # --- 3. SQUEEZE LOGIC ---
    # sqzOn  = (lowerBB > lowerKC) and (upperBB < upperKC)
    # sqzOff = (lowerBB < lowerKC) and (upperBB > upperKC)
    sqz_on = (lower_bb > lower_kc) & (upper_bb < upper_kc)
    sqz_off = (lower_bb < lower_kc) & (upper_bb > upper_kc)
    
    # --- 4. MOMENTUM (LINEAR REGRESSION) ---
    highest_h = df['High'].rolling(window=length_kc).max()
    lowest_l = df['Low'].rolling(window=length_kc).min()
    avg_val = ( (highest_h + lowest_l)/2 + basis ) / 2
    val = source - avg_val
    
    def linreg(s):
        x = np.arange(len(s))
        slope, intercept = np.polyfit(x, s.values, 1)
        return slope * (len(s) - 1) + intercept

    # LazyBear linreg length is lengthKC
    df['mom_val'] = val.rolling(window=length_kc).apply(linreg, raw=False)
    
    # --- 5. THE ONE-SHOT TRIGGER ---
    curr_on = sqz_on.iloc[-1]
    prev_on = sqz_on.iloc[-2]
    curr_off = sqz_off.iloc[-1]
    
    # TRIGGER: If it WAS on (Black) and is NOW off (Gray)
    if prev_on == True and curr_off == True:
        return "RELEASED", df['mom_val'].iloc[-1]
    
    return "STAY_SILENT", 0
