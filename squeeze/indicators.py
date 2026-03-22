import pandas as pd
import numpy as np

def get_squeeze_status(df, length=20, mult_bb=2.0, mult_kc=1.5, use_true_range=True):
    if len(df) < length + 2:
        return "INSUFFICIENT_DATA", 0

    # Source is Close
    source = df['Close']
    
    # --- 1. BOLLINGER BANDS ---
    # basis = sma(source, length)
    basis = source.rolling(window=length).mean()
    # dev = multKC * stdev(source, length) <--- LazyBear uses multKC here for the squeeze check
    dev = mult_kc * source.rolling(window=length).std()
    upper_bb = basis + dev
    lower_bb = basis - dev
    
    # --- 2. KELTNER CHANNELS ---
    # ma = sma(source, lengthKC)
    ma = source.rolling(window=length).mean()
    
    if use_true_range:
        # tr = max(high-low, abs(high-prev_close), abs(low-prev_close))
        tr = np.maximum((df['High'] - df['Low']),
                        np.maximum(abs(df['High'] - df['Close'].shift()),
                                   abs(df['Low'] - df['Close'].shift())))
        range_val = tr
    else:
        range_val = df['High'] - df['Low']
        
    # rangema = sma(range, lengthKC)
    range_ma = range_val.rolling(window=length).mean()
    upper_kc = ma + range_ma * mult_kc
    lower_kc = ma - range_ma * mult_kc
    
    # --- 3. SQUEEZE LOGIC ---
    # sqzOn  = (lowerBB > lowerKC) and (upperBB < upperKC)
    # sqzOff = (lowerBB < lowerKC) and (upperBB > upperKC)
    sqz_on = (lower_bb > lower_kc) & (upper_bb < upper_kc)
    sqz_off = (lower_bb < lower_kc) & (upper_bb > upper_kc)
    
    # --- 4. MOMENTUM (Linear Regression) ---
    # val = linreg(source - avg(avg(highest(high, length), lowest(low, length)), sma(close,length)), length, 0)
    highest_h = df['High'].rolling(window=length).max()
    lowest_l = df['Low'].rolling(window=length).min()
    avg_hl = (highest_h + lowest_l) / 2
    avg_all = (avg_hl + basis) / 2
    
    val_to_reg = source - avg_all
    
    def calculate_linreg(series):
        x = np.arange(len(series))
        y = series.values
        slope, intercept = np.polyfit(x, y, 1)
        # Offset 0 means we calculate the value at the current bar
        return slope * (len(series) - 1) + intercept

    df['val'] = val_to_reg.rolling(window=length).apply(calculate_linreg, raw=False)
    
    # --- 5. TRIGGER CHECK ---
    curr_sqz_on = sqz_on.iloc[-1]
    prev_sqz_on = sqz_on.iloc[-2]
    
    # Signal: Only alert when it transitions from Black (On) to Gray (Off)
    # We use boolean check: prev was True, current is False
    if prev_sqz_on == True and curr_sqz_on == False:
        return "RELEASED", df['val'].iloc[-1]
    
    return "STAY_SILENT", 0
