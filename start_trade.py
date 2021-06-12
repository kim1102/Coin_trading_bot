"""
2021-06-07
written by dev-kim
!! The responsibility for the investment lies with you
"""
#from coin_trader import trading_bot
from coin_trader_v5 import trading_bot
from datetime import datetime
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description= 'option for trading bot')
    parser.add_argument("-coin", "--target_coin", default= ["KRW-BTC", "KRW-XRP", "KRW-ETH"])
    parser.add_argument("-auto", "--auto_recommend", default=True)
    args = parser.parse_args()

    # initialize trading bot
    bot = trading_bot(args.target_coin)
    if args.auto_recommend:
        print("!=== Auto coin recommendation function ON!")
    bot.start_trading()
