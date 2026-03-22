import pandas as pd
import numpy as np

def get_squeeze_status(df, length=20, mult=2.0, length_kc=20, mult_kc=1.5, use_tr=True):
    if len(df) < length + 2:
        return "STAY_SILENT", 0

    # 0. Round data to handle Forex precision issues
    source = df['Close'].round(6)
    basis = source.rolling(window=length).mean()
    
    # --- 1. BOLLINGER BANDS (Calibrated to LazyBear Line 18) ---
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
    # sqzOn: Black dots | sqzOff: Gray dots
    sqz_on = (lower_bb > lower_kc) & (upper_bb < upper_kc)
    sqz_off = (lower_bb < lower_kc) & (upper_bb > upper_kc)
    
    # --- 4. MOMENTUM ---
    highest_h = df['High'].rolling(window=length_kc).max()
    lowest_l = df['Low'].rolling(window=length_kc).min()
    avg_val = ((highest_h + lowest_l)/2 + basis) / 2
    val = source - avg_val
    
    def linreg(s):
        x = np.arange(len(s))
        slope, intercept = np.polyfit(x, s.values, 1)
        return slope * (len(s) - 1) + intercept

    df['mom_val'] = val.rolling(window=length_kc).apply(linreg, raw=False)
    
    # --- 5. THE FOREX-READY TRIGGER ---
    curr_on = sqz_on.iloc[-1]
    prev_on = sqz_on.iloc[-2]
    curr_off = sqz_off.iloc[-1]
    
    # TRIGGER: If it was ON (Black) and is NOW OFF (Gray)
    # OR if it was ON 2 bars ago and current is OFF (Handling minor data gaps)
    prev_on_2 = sqz_on.iloc[-3] if len(sqz_on) > 3 else False
    
    if (prev_on == True or prev_on_2 == True) and curr_off == True:
        # One last check: ensure we didn't just alert on the previous candle
        # We only want the very first Gray dot
        if not (sqz_off.iloc[-2] == True and (sqz_on.iloc[-3] == True or sqz_on.iloc[-4] == True)):
             return "RELEASED", df['mom_val'].iloc[-1]
    
    return "STAY_SILENT", 0
