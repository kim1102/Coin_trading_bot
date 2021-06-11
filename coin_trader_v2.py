"""
2021-05-06
written by dev-kim
Bug report: devkim1102@gmail.com
"""

import pyupbit as pybit
from account_config import get_account
from time import sleep
import sys
import random
from datetime import datetime
from easydict import EasyDict as edict

def get_config():
    conf = edict()
    # === parameter: win
    conf.unit_per = 0.15
    conf.margin_per = 0.005
    conf.max_target = 5
    # === parameter: loss
    conf.loss_cut = 0.003
    conf.default_loss_stop = 3

    # === parameter: else
    conf.trade_interval = 1# default 2 seconds

    return conf


class trading_bot():
    def __init__(self, target_coin):
        acc_key, sec_key = get_account()
        self.session = pybit.Upbit(acc_key, sec_key)
        self.target_coin = target_coin

        # initial balance
        self.initial_krw = 0

        conf = get_config()
        self.interval = conf.trade_interval
        self.unit_per = conf.unit_per
        self.margin_per = conf.margin_per
        self.unit = 0 # 2% of seed money
        self.max_target = conf.max_target
        self.loss_cut = conf.loss_cut

    def start_trading(self):
        # start with one unit target balance
        previous_price = pybit.get_current_price(self.target_coin)
        for bal in self.session.get_balances():
            ticker = bal['currency']
            if ticker != 'KRW':
                ticker = 'KRW-' + ticker
                self.sell(ticker, self.session.get_balance(ticker), self.get_current_price(ticker))
            sleep(2)
        self.initial_krw = self.session.get_balance('KRW')
        self.update_unit()

        print("!=== Start trading")
        self.buy(self.target_coin, self.unit, previous_price)
        self.write_log(pybit.get_current_price(self.target_coin))
        # cumulative win strategy
        unit_count= 0
        try:
            while True:
                sleep(self.interval)
                # get current price & coin balance
                current_price = pybit.get_current_price(self.target_coin)
                my_price = self.session.get_avg_buy_price(self.target_coin)
                tot_volume = self.session.get_balance(ticker=self.target_coin)

                # win
                if current_price-my_price > my_price * self.margin_per:
                    print("!+++ Win count ({}/5) +++!".format(unit_count))
                    if unit_count >= self.max_target:
                        target_price = pybit.get_tick_size(current_price)
                        #loss_price = pybit.get_tick_size(current_price - current_price*self.loss_cut)
                        loss_price = pybit.get_tick_size(my_price + my_price * self.loss_cut)

                        prof_order = self.session.sell_limit_order(ticker=self.target_coin,
                                                     price=target_price,
                                                     volume=tot_volume)
                        print(print("[Win] Profit order: {} ".format(prof_order['uuid'])))
                        try:
                            while True:
                                # wait until sell is over
                                current_price = pybit.get_current_price(self.target_coin)
                                if len(self.session.get_order(self.target_coin)) < 1: # sell complete
                                    print("[Win] Limit sell order complete---")
                                    self.write_log(current_price)
                                    break
                                elif current_price < loss_price:
                                    self.sell(self.target_coin, tot_volume, current_price)
                                    self.session.cancel_order(prof_order['uuid'])
                                    print("[Order cancel] profit order cancel---")
                                    break
                                sleep(0.3)
                        except KeyboardInterrupt:
                            self.terminate_session(current_price)

                        self.buy(self.target_coin, self.unit, current_price)
                        unit_count = 0
                    else:
                        self.buy(self.target_coin, self.unit, current_price)
                        unit_count += 1

                # lost
                elif current_price < my_price:
                    print("!+++ Lose +++!")
                    if unit_count > 0: # continuous +, one -
                        self.sell(self.target_coin, tot_volume, current_price)
                        self.buy(self.target_coin, self.unit, current_price)
                        unit_count = 0
                        continue

                    target_price = pybit.get_tick_size(my_price - my_price * self.loss_cut)
                    loss_order = self.session.buy_limit_order(ticker=self.target_coin,
                                                               price=target_price,
                                                               volume=tot_volume)
                    print("[Loss] loss order: {} ".format(loss_order['uuid']))
                    try:
                        while True:
                            # wait until buy is over
                            current_price = pybit.get_current_price(self.target_coin)
                            if len(self.session.get_order(self.target_coin)) < 1:  # buy complete
                                self.sell(self.target_coin, tot_volume, current_price)
                                print("[Loss] Limit buy order complete---")
                                break
                            elif current_price >= my_price: # turning to earn
                                self.session.cancel_order(loss_order['uuid'])
                                print("[Order cancel] loss order cancel---")
                                break
                            sleep(0.3)
                    except KeyboardInterrupt:
                        self.terminate_session(current_price)

                    unit_count = 0

                else:
                    continue

                # update previous price
                previous_price = self.get_current_price(self.target_coin)

        except KeyboardInterrupt:
            self.terminate_session(current_price)

    def cal_ER(self, ticker='KRW'):
        # calculate earning rate
        if ticker == 'KRW': my_price = self.initial_krw
        else: my_price = self.session.get_avg_buy_price(ticker)

        current_price = self.get_current_price(self.target_coin)
        return current_price / my_price * 100


    def update_unit(self):
        self.unit = self.session.get_balance('KRW')*self.unit_per


    def get_current_price(self, ticker):
        price = pybit.get_current_price(ticker)
        assert isinstance(price, float)
        return price


    def sell(self, ticker, volume, current_price):
        ret = self.session.sell_market_order(ticker=ticker, volume=volume)
        while True: # wait until sell process done
            try:
                if len(self.session.get_order(self.target_coin)) < 1: break
            except:
                print(self.session.get_order())
                continue

        krw_balance = self.session.get_balance('KRW')
        target_balance = self.session.get_balance(ticker)
        self.update_unit()

        try:
            print("[Sell] KRW:{:0,.0f}, init KRW:{:0,.0f}, {}:{:0,}"
                  .format(krw_balance, self.initial_krw, ticker, target_balance))
        except:
            print("[Sell] {}:{:0,}"
                  .format(ticker, volume))

        self.write_log(current_price)
        return ret


    def buy(self, ticker, price, current_price):
        ret = self.session.buy_market_order(ticker=ticker, price=price)
        while True: # wait until buy process done
            try:
                if len(self.session.get_order(self.target_coin)) < 1: break
            except:
                print(self.session.get_order())
                continue

        krw_balance = self.session.get_balance('KRW')
        target_balance = self.session.get_balance(ticker)

        try:
            print("[Buy] KRW:{:0,.0f}, {}:{:0,}, {} ER:{:.2f}%"
                  .format(krw_balance, ticker, target_balance, ticker, self.cal_ER(ticker)))
        except:
            print("[Buy] {}:{:0,}"
                  .format(ticker, price))

        self.write_log(current_price)
        return ret


    def write_log(self, current_price):
        print("[{}] current_price: {:0,}".format(datetime.now(), current_price))


    def terminate_session(self, current_price):
        # sell whole coins and finish program
        volume = self.session.get_balance(self.target_coin)
        self.sell(self.target_coin, volume, current_price)

        print(datetime.now())
        print("!=== Terminate trading bot")
        sys.exit()