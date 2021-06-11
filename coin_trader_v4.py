"""
2021-05-19
written by dev-kim
Method: RSI-based Martingail
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
from utils import get_safe_coin_list

def get_config():
    conf = edict()
    # === parameter: win
    conf.unit = 8000
    conf.margin_per = 0.01
    # === parameter: loss
    conf.loss_cut = 0.01
    conf.base_candle = "minute5"
    conf.rsi_thres = 30

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
        self.rsi_thres = conf.rsi_thres
        self.coin_list = []

        # for log write
        self.log_win_count = 0
        self.log_loss_cut_count = 0
        self.log_loss_count = 0

        current_time = time.strftime('%Y-%m-%d', time.localtime(time.time()))
        self.writer = f'log/{current_time}.txt'

        # get whole coins in upbit
        self.total_coin_list = get_safe_coin_list()

    def start_trading(self, auto_recommend = True):
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
                self.target_coin = self.ready_to_buy(auto_recommend)
                log = f'!=== Start trading / Target coin:{self.target_coin}'
                self.write_log(log)

                current_rsi = self.stand_by(self.target_coin)
                log = f'Coin rsi: {current_rsi:.2f}'
                self.write_log(log)

                # martingail based on RSI score
                self.martingale_trade()

                log = f"[Betting history] win: {self.log_win_count}/ " \
                      f"loss: {self.log_loss_count}/ loss cut: {self.log_loss_cut_count}"
                self.write_log(log)

                log = f'!=== Earning rate: {self.cal_ER():0,.2f}%'
                self.write_log(log)

        except KeyboardInterrupt:
            self.terminate_session()


    def update_coin_list(self):
        self.total_coin_list = get_safe_coin_list()
        sleep(0.5)
        volume_list = []

        for ticker in self.total_coin_list:
            df = pybit.get_ohlcv(ticker, self.base_candle)
            current_volume = int(df.iloc[-1]['volume'])
            volume_list.append(current_volume)
            sleep(0.2)

        res = sorted(range(len(volume_list)), key = lambda sub : volume_list[sub])[-30:]
        candidate_list = [self.total_coin_list[idx] for idx in res]

        self.coin_list = candidate_list


    def stand_by(self, ticker):
        min_rsi = 100
        while True:
            current_rsi = self.cal_rsi(ticker, interval=self.base_candle).iloc[-1]
            if current_rsi >= 30: break
            elif min_rsi < current_rsi:
                break
            else: min_rsi = current_rsi
            sleep(0.3)
        return current_rsi


    def ready_to_buy(self, auto=True):
        search_count = 0
        target_tickers = []
        target_rsis = []
        try:
            while True:
                if search_count == 0:
                    self.update_coin_list()

                if search_count % 20 == 0:
                    print("[{}] Finding coins suitable for trade".format(datetime.now()) + '.'*int(search_count/20))

                if auto: coin_list = random.sample(self.coin_list, 5)
                else: coin_list = self.coin_list

                search_count = (search_count + 1) % 100

                for ticker in coin_list:
                    current_rsi = self.cal_rsi(ticker, interval=self.base_candle).iloc[-1]
                    if current_rsi < self.rsi_thres:
                        target_tickers.append(ticker)
                        target_rsis.append(current_rsi)

                    sleep(0.3)

                if len(target_tickers) > 0:
                    break
                sleep(random.randrange(1))
        except KeyboardInterrupt:
            self.terminate_session()

        min_index = target_rsis.index(min(target_rsis))
        return target_tickers[min_index]


    def cal_rsi(self, ticker, interval="minute5", period=14):
        closedata = pybit.get_ohlcv(ticker, interval)["close"]
        delta = closedata.diff()
        ups, downs = delta.copy(), delta.copy()

        ups[ups < 0] = 0
        downs[downs > 0] = 0

        AU = ups.ewm(com = period-1, min_periods = period).mean()
        AD = downs.abs().ewm(com = period-1, min_periods = period).mean()
        RS = AU/AD

        return pandas.Series(100 - (100/(1+RS)), name = "RSI")


    def martingale_trade(self):
        self.session.buy_market_order(ticker=self.target_coin, price=self.unit)
        while True:
            sleep(0.5)
            if len(self.session.get_order(self.target_coin)) < 1:  # buy complete
                break
        loss_count = 0
        try:
            while True:
                volume = self.session.get_balance(self.target_coin)
                current_price = self.session.get_avg_buy_price(self.target_coin)
                sell_order, buy_order = self.reserve_order(current_price=current_price, volume=volume)

                try:
                    print("Sell order ID: {}".format(sell_order['uuid']))
                    print("Buy order ID: {}".format(buy_order['uuid']))
                except: # loss cut
                    print(sell_order)
                    print(buy_order)
                    # loss cut or error to order
                    self.session.sell_market_order(ticker=self.target_coin, volume=volume)
                    self.cancel_whole_order()
                    self.log_loss_cut_count += 1
                    break

                sell_id = sell_order['uuid']
                buy_id = buy_order['uuid']

                while True:
                    if len(self.session.get_order(self.target_coin)) < 2:  # buy complete
                        break
                    sleep(0.2)

                remain_order = self.session.get_order(self.target_coin)[0]['uuid']
                if remain_order == buy_id:  # win
                    self.session.cancel_order(buy_id)
                    self.log_win_count += 1
                    sleep(1)
                    log = f'[Win] KRW : {self.cal_ER():0,.2f}%'
                    self.write_log(log)
                    print(self.session.get_balances())
                    print("{}".format("="*30))
                    break
                else:  # lost
                    self.session.cancel_order(sell_id)
                    loss_count += 1
                    self.log_loss_count += 1
                    log = f'[lost] Loss count:{loss_count} / {self.target_coin}'
                    self.write_log(log)
                    print(self.session.get_balances())
                    print("{}".format("="*30))

        except KeyboardInterrupt:
            self.terminate_session()


    def cal_ER(self):
        # calculate earning rate
        current_price = self.session.get_balance('KRW')
        try: result = current_price / self.initial_krw * 100
        except: result = -1

        return result


    def reserve_order(self, current_price, volume):
        win_price = pybit.get_tick_size(current_price + current_price * self.margin_per)
        loss_price = pybit.get_tick_size(current_price - current_price * self.margin_per)
        sell_order = self.session.sell_limit_order(ticker=self.target_coin,
                                                   price=win_price,
                                                   volume=volume)
        buy_order = self.session.buy_limit_order(ticker=self.target_coin,
                                                 price=loss_price,
                                                 volume=volume * 2)
        return sell_order, buy_order


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
        if len(self.coin_list) == 0: coin_list = self.total_coin_list
        else: coin_list = self.coin_list

        for ticker in coin_list:
            for orders in self.session.get_order(ticker):
                order_id = orders['uuid']
                self.session.cancel_order(order_id)
                sleep(0.5)

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
        self.log_f.close()
        sys.exit()