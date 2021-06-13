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
from utils import get_safe_coin_list, get_top_attention_coin, get_10min_volume_percentage

def get_config():
    conf = edict()
    # === parameter: win
    conf.unit_per = 0.5
    conf.margin_per = 0.02
    # === parameter: loss
    conf.loss_cut = 0.015
    conf.base_candle = "minute3"
    # === parameter: timed out
    conf.timed_out = 30  # 30minute for waiting

    # === parameter: entrance gap
    # previous price < moving average(MA) - MA * param &&
    # current price > MA + MA * param -> then buy
    conf.entrance_gap = 0.002

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
        self.unit = 0
        self.unit_per = conf.unit_per
        self.interval = conf.trade_interval
        self.margin_per = conf.margin_per
        self.entrance_gap = conf.entrance_gap
        self.loss_cut = conf.loss_cut
        self.base_candle = conf.base_candle
        self.timed_out = conf.timed_out

        # for log write
        self.log_win_count = 0
        self.log_time_out_count = 0
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
                # unit update
                self.unit = pybit.get_tick_size(self.session.get_balance('KRW')*self.unit_per)
                sleep(0.5)

                # wait until entrance
                self.target_coin, current_price = self.ready_to_buy()

                # trade start
                self.trade_target_coin(current_price)

                log = f"[Betting history] win: {self.log_win_count}/ " \
                      f"loss: {self.log_loss_count}/ timed out: {self.log_time_out_count}"
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
                    moving_avg, previous_price, current_close = self.cal_ma(ticker, interval=self.base_candle)
                    condition1 = previous_price < moving_avg - moving_avg*self.entrance_gap
                    condition2 = moving_avg + moving_avg*self.entrance_gap*0.5 < current_close
                    #percentage = get_10min_volume_percentage(ticker)
                    #condition3 = percentage > 1.5

                    if condition1 and condition2:
                        log = f'!=== Start trading / Target coin:{ticker}'
                        self.write_log(log)
                        log = f'current_price: {current_close:.2f}/ previous_price: {previous_price:.2f}/ ' \
                              f'moving average: {moving_avg:.2f}'
                        self.write_log(log)

                        #print(percentage)

                        return ticker, current_close

                sleep(1)
        except KeyboardInterrupt:
            self.terminate_session()


    def cal_ma(self, ticker, interval="minute3", period=50):
        candle_data = pybit.get_ohlcv(ticker, interval)
        closedata = candle_data['close']
        moving_avg = sum(closedata.tolist()[-period:])/period
        current_close = closedata[-1]

        # get previous price
        previous_high = candle_data['high'][-2]
        current_open = candle_data['open'][-1]
        previous_price = (previous_high + current_open)/2

        return moving_avg, previous_price, current_close


    def trade_target_coin(self, start_price):
        print(self.session.buy_market_order(ticker=self.target_coin, price=self.unit))
        while True:
            sleep(0.5)
            if len(self.session.get_order(self.target_coin)) < 1:  # buy complete
                break

        volume = self.session.get_balance(self.target_coin)
        sleep(0.3)
        buy_price = self.session.get_avg_buy_price(self.target_coin)
        loss_price = buy_price - buy_price*self.loss_cut
        sleep(0.3)
        sell_order = self.reserve_order(current_price=buy_price, volume=volume)
        sell_id = sell_order['uuid']
        sleep(0.3)

        t1 = time.time()
        try:
            while True:
                current_price = pybit.get_current_price(self.target_coin)
                sleep(0.5)
                # lost
                if current_price < loss_price:
                    print(self.session.cancel_order(sell_id))
                    print(self.session.sell_market_order(ticker=self.target_coin, volume=volume))
                    sleep(0.5)
                    self.log_loss_count += 1
                    return
                # win
                elif len(self.session.get_order(self.target_coin)) < 1:
                    self.log_win_count += 1
                    return
                # timed out
                elif time.time() - t1 > self.timed_out*60:
                    print(self.session.cancel_order(sell_id))
                    print(self.session.sell_market_order(ticker=self.target_coin, volume=volume))
                    sleep(0.5)
                    self.log_time_out_count += 1
                    return


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
        sell_order = self.session.sell_limit_order(ticker=self.target_coin, price=win_price, volume=volume)
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
