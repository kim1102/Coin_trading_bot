"""
2021-05-19
written by dev-kim
Method: RSI-based Martingail
가격이 이평선 돌파시 매수
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
from utils import get_safe_coin_list, get_top_attention_coin, get_volume_percentage

def get_config():
    conf = edict()
    # === parameter: win
    conf.unit = 30000
    conf.margin_per = 0.02
    # === parameter: loss
    conf.loss_cut = 0.007
    conf.base_candle = "minute1"

    # === parameter: else
    conf.trade_interval = 5# default 1min

    return conf

class trading_bot():
    def __init__(self, coin_list):
        acc_key, sec_key = get_account()
        self.session = pybit.Upbit(acc_key, sec_key)
        self.target_coin = None

        # initial balance
        self.initial_krw = 0

        conf = get_config()
        self.unit = conf.unit
        self.interval = conf.trade_interval
        self.margin_per = conf.margin_per
        self.loss_cut = conf.loss_cut
        self.base_candle = conf.base_candle

        # for log write
        self.log_win_count = 0
        self.log_loss_cut_count = 0
        self.log_loss_count = 0

        current_time = time.strftime('%Y-%m-%d', time.localtime(time.time()))
        self.writer = f'log/{current_time}.txt'

        # get whole coins in upbit
        self.total_coin_list = get_safe_coin_list()
        self.coin_list = []

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
                # wait until entrance
                self.target_coin = self.ready_to_buy()

                # trade start
                self.trade_target_coin()

                log = f"[Betting history] win: {self.log_win_count}/ " \
                      f"loss: {self.log_loss_count}/ loss cut: {self.log_loss_cut_count}"
                self.write_log(log)

                log = f'[Trade complete]=== Earning rate: {self.cal_ER():0,.2f}%'
                self.write_log(log)

        except KeyboardInterrupt:
            self.terminate_session()

    def update_coin_list(self):
        self.total_coin_list = get_safe_coin_list()
        sleep(0.5)
        self.coin_list = get_top_attention_coin(self.total_coin_list)


    def ready_to_buy(self):
        search_count = 0
        try:
            while True:
                if search_count == 0:
                    self.update_coin_list()
                if search_count % 20 == 0:
                    print("[{}] Finding coins suitable for trade".format(datetime.now()) + '.'*int(search_count/20))
                search_count = (search_count + 1) % 100

                coin_list = random.sample(self.coin_list, 5)

                for ticker in coin_list:
                    moving_avg, current_open, current_close = self.cal_ma(ticker, interval=self.base_candle)
                    condition1 = current_open < moving_avg
                    condition2 = moving_avg < current_close
                    condition3 = get_volume_percentage(ticker) > 1.5

                    if condition1 and condition2 and condition3:
                        log = f'!=== Start trading / Target coin:{ticker}'
                        self.write_log(log)
                        log = f'current_price: {current_close:.2f}/ previous_price: {current_open:.2f}/ ' \
                              f'moving average: {moving_avg:.2f}'
                        self.write_log(log)

                        return ticker

                sleep(1)
        except KeyboardInterrupt:
            self.terminate_session()


    def cal_ma(self, ticker, interval="minute3", period=15):
        candle_data = pybit.get_ohlcv(ticker, interval)
        closedata = candle_data['close']
        moving_avg = sum(closedata.tolist()[-period:])/period
        current_close = closedata[-1]
        current_open = candle_data['open'][-1]

        return moving_avg, current_open, current_close


    def trade_target_coin(self):
        self.session.buy_market_order(ticker=self.target_coin, price=self.unit)
        while True:
            sleep(0.5)
            if len(self.session.get_order(self.target_coin)) < 1:  # buy complete
                break

        volume = self.session.get_balance(self.target_coin)
        current_price = self.session.get_avg_buy_price(self.target_coin)
        loss_price = current_price - current_price*self.loss_cut
        sell_order = self.reserve_order(current_price=current_price, volume=volume)
        sell_id = sell_order['uuid']

        try:
            while True:
                current_price = pybit.get_current_price(self.target_coin)
                # lost
                if current_price < loss_price:
                    self.session.sell_market_order(ticker=self.target_coin, volume=volume)
                    self.session.cancel_order(sell_id)
                    self.log_loss_count += 1
                    break
                # win
                elif len(self.session.get_order(self.target_coin)) < 1:
                    self.log_win_count += 1
                    break
                sleep(0.5)

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


    def reserve_order(self, current_price, volume):
        win_price = pybit.get_tick_size(current_price + current_price * self.margin_per)
        sell_order = self.session.sell_limit_order(ticker=self.target_coin,
                                                   price=win_price,
                                                   volume=volume)
        return sell_order


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


    def buy(self, ticker, price):
        ret = self.session.buy_market_order(ticker=ticker, price=price)
        while True: # wait until buy process done
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
        # cancel order
        for ticker in self.total_coin_list:
            for orders in self.session.get_order(ticker):
                order_id = orders['uuid']
                self.session.cancel_order(order_id)
                sleep(1)

        for balance in self.session.get_balances():
            ticker = balance['currency']
            if 'KRW' not in ticker:
                ticker = 'KRW-' + ticker
                volume = self.session.get_balance(ticker)
                self.session.sell_market_order(ticker, volume)
            sleep(0.5)


    def terminate_session(self):
        # sell whole coins and finish program
        self.cancel_whole_order()

        print(datetime.now())
        log = "!=== Terminate trading bot"
        self.write_log(log)
        log = f'!=== Earning rate: {self.cal_ER():0,.2f}%'
        self.write_log(log)
        sys.exit()
