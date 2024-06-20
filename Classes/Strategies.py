import pandas as pd
from Classes.data_operations import *
from time import sleep
import customtkinter
from datetime import date
from random import choice,randint

# Parameteters for strategy (not modify)
OFFSET = 2
CHOP_LIMIT = 50.24
CHOP_LENGHT = 4
ATR_LENGTH = 15
FACTOR = 2.4
EMA_OPEN_EURUSD = 2
EMA_LH_EURUSD = 2
EMA_OPEN_XAUUSD = 4
EMA_LH_XAUUSD = 2

# DEFAULT CUSTOM PARAMETERS
TARGET_POINTS_EURUSD = 65
TARGET_POINTS_XAUUSD = 800
RISK = .0025
PROFIT = .0035
ENTRIES_PER_SIGNAL = 4



# Stragies created by my own
def positions_open(conn,s=None):
    """
        Check if exists positions opened in the symbol
    """    
    return not conn.get_positions(0).empty if s is None else not conn.get_positions(0,s=s).empty

def export_signals(df,result,order,reverse,points,symbol,date_for_df,i):    
    df["result"] = result
    df["reverse"] = reverse
    df["points"] = points
    df["symbol"] = symbol
    df["order"] = order
    id_rand = randint(1,100)
    df["ID"] = symbol+"-"+date_for_df+"-"+str(points)+"live"+"-"+str(i)+str(id_rand)
    return df,id_rand

def main_loop(object,conn,symbol_to_trade,partial_close,risk,target_profit,entries_per_trade,max_trades,timeFrame,flag_session,flag_position,points,lots,both_directions=False,dynamic_sl=True,reverse_entries=False,fibonacci=False):
    point = mt5.symbol_info(symbol_to_trade).point   
    points_value = 0
    TRADES_SIGNALS = []    
    id = 0
    date_for_df = str(date.today())
    fibonacci_levels = dict()
    FINAL_EMA_OPEN = EMA_OPEN_XAUUSD if symbol_to_trade == "XAUUSD" else EMA_OPEN_EURUSD
    FINAL_EMA_LH = EMA_LH_XAUUSD if symbol_to_trade == "XAUUSD" else EMA_LH_EURUSD
    max_profit_trades = int(.6 * max_trades) if max_trades != 1 else 1
    max_loss_trades = int(.4 * max_trades) if max_trades > 2 else 1
    total_profit = 0
    positive = 0
    negative = 0        
    balance = conn.account_details().balance   
    last_balance = balance
    check_balance = False  
    risk = (balance * risk) * -1
    target_profit = balance * target_profit
    while not flag_session.is_set():        
        # Position Opened
        if positions_open(conn,symbol_to_trade) and not flag_position.is_set():
            if fibonacci:
                # TRAILLING STOP based onf fibonacci levels
                TRAILLING_STOP_FIBONACCI(s=symbol_to_trade,
                                         order=entry,
                                         tickets=tickets_copy,
                                         conn=conn,
                                         levels=fibonacci_levels,
                                         profit=target_profit,
                                         risk=risk,
                                         pnl=total_profit,
                                         flag_to_stop=flag_position,
                                         partial_close=partial_close,
                                         dynamic_sl=dynamic_sl)
            else:
                # Active Trailling STOP with 33 %  - Apply in both directions based on entry    
                TRAILLING_STOP(conn=conn,
                            s=symbol_to_trade,
                            order=entry,
                            tickets=tickets_copy,
                            points=points / 3,
                            profit=target_profit,
                            risk=risk,
                            partial_close=partial_close,
                            apply_both_directions=both_directions,
                            flag_to_stop=flag_position,dynamic_sl=dynamic_sl,
                            pnl = total_profit
                            )
            check_balance = True                                   
        # If operations are alive and flag is set up to True close all positions
        if positions_open(conn,symbol_to_trade) and flag_position.is_set():  
            tickets_to_close = conn.get_positions().ticket.values          
            print(f"Next Trades wil be closed due flag change: {tickets_to_close}")
            for ticket in tickets_to_close:                
                conn.close_position(symbol_to_trade, ticket, entry, lots, comment="Closed by limit reached")                
            check_balance = True
            # Clear the flag to avoid close the next entries
            flag_position.clear()               
                                             
        # Update current balance        
        if check_balance and last_balance != conn.account_details().equity:            
            profit = conn.account_details().equity - last_balance            
            result = "WIN"
            id += 1
            # Keep tracks of profit/loss operations
            if profit > 0:
                positive += 1                        
            else:
                result = "LOSS"
                negative += 1                
            total_profit += profit
            last_balance = conn.account_details().equity
            check_balance = False            
            if fibonacci:    
                df,id = export_signals(M1,result,entry,random_reverse,int(points_value),symbol_to_trade,date_for_df,id)                                            
                TRADES_SIGNALS.append(df) 
            else:
                df,id = export_signals(M1,result,entry,random_reverse,points,symbol_to_trade,date_for_df,id)
                TRADES_SIGNALS.append(df) 
        # Check if sessions needs to be closed
        if not positions_open(conn,s=symbol_to_trade):
            # Close the session if profit/loss or max entries was reached
            if (total_profit >= target_profit) or (total_profit <= risk):
                print(f"The session was closed automatically by {'loss' if total_profit < 0 else 'profit'} limit reached!")
                break
            if (positive == max_profit_trades) or (negative == max_loss_trades) or (negative + positive >= max_trades):
                print("Maximun trades reached")
                break
        try:            
            M1 = conn.data_range(symbol_to_trade, timeFrame, 100)
        except Exception as e:
            print("Data range failed:", e)
            break
        # Avoid open positions when the profit/risk was acheived
        if not positions_open(conn,symbol_to_trade) and (total_profit <= target_profit) or (total_profit >= risk):
            # Open positions if the stratgy detects entries
            random_reverse = choice([True,True,False,False]) if symbol_to_trade == "XAUUSD" else choice([True,True,False,False,False])
            position, entry = EMA_CROSSING(df=M1,offset= OFFSET, ema_open=FINAL_EMA_OPEN,ema_period= FINAL_EMA_LH,reverse=random_reverse)        
            if position:                 
                lowest,highest = Technical(M1).LOWEST_AND_HIGHEST(10) 
                difference = abs(highest - lowest)
                fibonacci_levels = {
                    23.6: .236 * difference,
                    38.2: .382 * difference,        
                    50: .5 * difference,
                    61.8: .618 * difference
                }
                # if reverse_entries:
                #     entry = 0 if entry == 1 else 1
                #entry = 0 if entry == 1 else 1 if reverse_entries else entry
                tickets = [] 
                tickets_copy = [] 
                if entry == 1:
                    print("****************** BUY ******************")
                    decimal_places = len(str(mt5.symbol_info_tick(symbol_to_trade).ask).split(".")[1])
                    entry_price = mt5.symbol_info_tick(symbol_to_trade).ask
                    sl = round(entry_price - fibonacci_levels[38.2], decimal_places)
                    tp = round(entry_price + fibonacci_levels[61.8], decimal_places)
                else:
                    print("****************** SELL ******************")   
                    decimal_places = len(str(mt5.symbol_info_tick(symbol_to_trade).bid).split(".")[1])
                    entry_price = mt5.symbol_info_tick(symbol_to_trade).bid
                    sl = round(entry_price + fibonacci_levels[38.2], decimal_places)
                    tp = round(entry_price - fibonacci_levels[61.8], decimal_places)                                               
                
                while len(tickets) < entries_per_trade:                    
                    # Set SL and TP based in Fibonacci levels
                    if fibonacci:
                        points_value = round((max([tp,entry_price]) - min([tp,entry_price])) * (100 if symbol_to_trade == "XAUUSD" else 100_000))
                        object.points = str(points_value)
                        ticket = conn.open_position(symbol_to_trade, entry, lots,[sl,tp])
                    # Set  SL and TP with user inputs
                    else:
                        ticket = conn.open_position(symbol_to_trade, entry, lots,points)
                    if ticket != 0:
                        tickets.append(ticket) 
                valid_entries = False
                for ticket in tickets:
                    if ticket != 10019:
                        valid_entries = True
                        tickets_copy.append(ticket)                        
                if not valid_entries:
                    flag_session.set()
                    print("Please reduce the lots")                                    
        sleep(1)
    
    if not flag_session.is_set():                  
        flag_session.set()
    # Display the buttons when session is closed automactically by one condtion reached
    object.main_frame.stop_thread.grid_forget()    
    object.main_frame.close_trades.grid_forget()                
    object.sidebar_button_2.configure(state="enabled")
    object.main_frame.stop_thread = customtkinter.CTkButton(object.main_frame, text="Return Strategy Screen",command= object.start_connection)
    object.main_frame.stop_thread.grid(row=7, column=0,columnspan=2, padx=40, pady=0,sticky="ew")                             
    # Export the current operations
    print(f"Profit: {total_profit}")  
    if len(TRADES_SIGNALS) > 0:
        if fibonacci:                
            pd.concat(TRADES_SIGNALS).to_csv(fr"C:\Users\Moy\Documents\Python\Algorithmic Trading\HFT\backtest_data\{symbol_to_trade}-{date_for_df}-{points_value}-fibonacci-{id}.csv")     
        else:
            pd.concat(TRADES_SIGNALS).to_csv(fr"C:\Users\Moy\Documents\Python\Algorithmic Trading\HFT\backtest_data\{symbol_to_trade}-{date_for_df}-{points}-{id}.csv")     

def EMA_CROSSING(df,offset=3, ema_open=15, ema_period=3,reverse=False,volume_filter=False,show=False):
    """
        Check for crossing signals based on the parameters passed
    """
    
    operation = False
    trend_for_operation = 2
    M1_technical = Technical(df)
    series_bar = M1_technical.RETURN_DIRECTION(30) 
    counters = bar_trend_ocurrencies(series_bar)
    if len(counters) > 2:
        total = 30 - counters[2]
    else:
        total = 30    
    if M1_technical.CHOP(CHOP_LENGHT) < CHOP_LIMIT:                
        # Set PARAMETERS         
        EMA_LOW = M1_technical.EMA(entry="low", period=ema_period, deviation=offset)
        EMA_HIGH = M1_technical.EMA(entry="high", period=ema_period, deviation=offset)
        EMA_OPEN = M1_technical.EMA(entry="open", period=ema_open, deviation=-1)
        supertrend = M1_technical.SUPER_TREND(ATR_LENGTH, FACTOR)          
        if (CROSSING(EMA_OPEN, EMA_HIGH, 0)) and supertrend == 1:            
            # SELL Under
            if counters[-1] / total >= .35:
                if show:
                    print("Sell under")
                operation = True
                trend_for_operation = 0                
            else:
                if show:
                    print("Buy by Strong Trend")
                operation = True
                trend_for_operation = 1                 
        
        elif (CROSSING(EMA_OPEN, EMA_LOW, 1)) and supertrend == 0:
            # BUY Over
            if counters[1] / total >= .35:
                if show:
                    print("Buy over")
                operation = True
                trend_for_operation = 1
            else:
                if show:
                    print("Sell by Strong Trend")
                operation = True
                trend_for_operation = 0                
        if operation and volume_filter:
            if df.tick_volume.iloc[-1] < df.tick_volume.iloc[-2]:                
                operation = False
        if reverse:
            trend_for_operation = 0 if trend_for_operation == 1 else 1
    return operation, trend_for_operation
