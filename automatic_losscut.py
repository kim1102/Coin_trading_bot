"""
2021-06-22
written by dev-kim
Automatic loss cut
Bug report: devkim1102@gmail.com
"""

import pyupbit as pybit
from account_config import get_account
from time import sleep
import sys
import random
from datetime import datetime
from easydict import EasyDict as edict
import pandas
import time
from utils import get_safe_coin_list, get_top_attention_coin, get_10min_volume_percentage

def get_config():
    conf = edict()
    conf.loss_cut = 0.001

    return conf

class trading_bot():
    def __init__(self, conf):
        acc_key, sec_key = get_account()
        self.session = pybit.Upbit(acc_key, sec_key)
        current_time = time.strftime('%Y-%m-%d', time.localtime(time.time()))
        self.writer = f'log/{current_time}.txt'
        self.loss_cut = conf.loss_cut

    def start_trading(self):
        print(datetime.now())
        log = "!=== Initialize trading bot"
        self.write_log(log)

        # start with one unit target balance
        self.cancel_whole_order()
        self.initial_krw = self.session.get_balance('KRW')
        log = f'Initial KRW: {self.initial_krw:0,.0f}'
        self.write_log(log)


        # cumulative win strategy
        try:
            while True:
                my_balances = self.session.get_balances()
                time.sleep(0.5)

                for balance in my_balances:
                    ticker = balance['currency']
                    if 'KRW' in ticker: continue
                    ticker = 'KRW-' + ticker
                    buy_price = self.session.get_avg_buy_price(ticker)
                    time.sleep(0.3)
                    if buy_price - buy_price*self.loss_cut > pybit.get_current_price(ticker):
                        volume = self.session.get_balance(ticker)
                        self.sell(ticker, volume)
                        log = f'[Trade complete]=== Earning rate: {self.cal_ER():0,.2f}%'
                        self.write_log(log)
                        break
                    time.sleep(0.5)

                print(f'[Trade complete]=== Earning rate: {self.cal_ER():0,.2f}%')
                print(datetime.now())


        except KeyboardInterrupt:
            self.terminate_session()

        print(self.session.get_balances())
        print("{}".format("=" * 30))

    def cal_ER(self):
        # calculate earning rate
        current_price = self.session.get_balance('KRW')
        try: result = current_price / self.initial_krw * 100
        except: result = -1

        return result


    def sell(self, ticker, volume):
        ret = self.session.sell_market_order(ticker=ticker, volume=volume)
        while True: # wait until sell process done
            try:
                if len(self.session.get_order(ticker)) < 1: break
            except:
                print(self.session.get_order(ticker))
                continue
            sleep(0.5)

        return ret


    def write_log(self, log):
        print(log)
        writer = open(self.writer, 'a')
        writer.write(log + '\n')
        writer.close()


    def cancel_whole_order(self):
        print("Whole sale in my balance...")
        my_balances = self.session.get_balances()
        time.sleep(0.5)

        for balance in my_balances:
            ticker = balance['currency']
            if 'KRW' in ticker: continue
            ticker = 'KRW-' + ticker

            # cancle orders
            for orders in self.session.get_order(ticker):
                order_id = orders['uuid']
                self.session.cancel_order(order_id)
                sleep(1)

            # whole sale
            volume = self.session.get_balance(ticker)
            self.session.sell_market_order(ticker, volume)

            sleep(1)


    def terminate_session(self):
        # sell whole coins and finish program
        self.cancel_whole_order()

        print(datetime.now())
        log = "!=== Terminate trading bot"
        self.write_log(log)
        log = f'!=== Earning rate: {self.cal_ER():0,.2f}%'
        self.write_log(log)
        sys.exit()

if __name__ == '__main__':
    config = get_config()
    auto_cancle_bot = trading_bot(config)
    auto_cancle_bot.start_trading()
