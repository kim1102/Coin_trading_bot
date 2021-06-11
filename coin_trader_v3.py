"""
2021-05-07
written by dev-kim
advanced_martingail
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
    conf.unit = 5500
    conf.margin_per = 0.007
    # === parameter: loss
    conf.loss_cut = 0.3

    # === parameter: else
    conf.trade_interval = 10# default 1min

    return conf

class trading_bot():
    def __init__(self, target_coin):
        acc_key, sec_key = get_account()
        self.session = pybit.Upbit(acc_key, sec_key)
        self.target_coin = target_coin

        # initial balance
        self.initial_krw = 0

        conf = get_config()
        self.unit = conf.unit
        self.interval = conf.trade_interval
        self.margin_per = conf.margin_per
        self.loss_cut = conf.loss_cut

    def start_trading(self):
        # start with one unit target balance
        for bal in self.session.get_balances():
            ticker = bal['currency']
            if ticker != 'KRW':
                ticker = 'KRW-' + ticker
                self.sell(ticker, self.session.get_balance(ticker), self.get_current_price(ticker))
            sleep(2)
        self.initial_krw = self.session.get_balance('KRW')

        print("!=== Start trading")
        self.write_log(pybit.get_current_price(self.target_coin))
        # cumulative win strategy
        try:
            while True:
                # wait until entrance
                self.ready_to_buy()
                self.martingale_trade()

        except KeyboardInterrupt:
            self.terminate_session()

    def ready_to_buy(self):
        while True:
            sleep(random.randrange(self.interval))
            break


    def martingale_trade(self):
        self.session.buy_market_order(ticker=self.target_coin, price=self.unit)
        while True:
            if len(self.session.get_order(self.target_coin)) < 1:  # buy complete
                break
        loss_count = 0
        try:
            while True:
                volume = self.session.get_balance(self.target_coin)
                current_price = self.session.get_avg_buy_price(self.target_coin)
                sell_id, buy_id = self.reserve_order(current_price=current_price, volume=volume)

                if 'error' in buy_id:
                    # loss cut
                    self.sell(self.target_coin, self.session.get_balance(self.target_coin))
                    #self.update_unit()
                    continue

                while True:
                    if len(self.session.get_order(self.target_coin)) < 2:  # buy complete
                        break

                remain_order = self.session.get_order(self.target_coin)[0]['uuid']
                if remain_order == buy_id:  # win
                    self.session.cancel_order(buy_id)
                    print("[Win] KRW : {:0,}%".format(self.cal_ER(self.cal_ER())))
                    print(self.session.get_balances())
                    break
                else:  # lost
                    self.session.cancel_order(sell_id)
                    loss_count += 1
                    print("[lost] Loss count:{} / {} : {:0,}%"
                          .format(loss_count, self.target_coin, self.cal_ER(self.target_coin)))
                    print(self.session.get_balances())

        except KeyboardInterrupt:
            self.terminate_session()


    def cal_ER(self, ticker='KRW'):
        # calculate earning rate
        if ticker == 'KRW':
            my_price = self.initial_krw
        else: my_price = self.session.get_avg_buy_price(ticker)

        current_price = pybit.get_current_price(self.target_coin)
        return current_price / my_price * 100


    def reserve_order(self, current_price, volume):
        win_price = pybit.get_tick_size(current_price + current_price * self.margin_per)
        loss_price = pybit.get_tick_size(current_price - current_price * self.margin_per)
        sell_order = self.session.sell_limit_order(ticker=self.target_coin,
                                                   price=win_price,
                                                   volume=volume)
        buy_order = self.session.buy_limit_order(ticker=self.target_coin,
                                                 price=loss_price,
                                                 volume=volume * 2)
        sell_id = sell_order['uuid']
        print(sell_order)
        buy_id = buy_order['uuid']
        print(buy_order)

        return sell_id, buy_id


    def sell(self, ticker, volume):
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

        return ret


    def buy(self, ticker, price):
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

        return ret


    def write_log(self, current_price):
        print("[{}] current_price: {:0,}".format(datetime.now(), current_price))


    def terminate_session(self):
        # sell whole coins and finish program
        volume = self.session.get_balance(self.target_coin)
        self.sell(self.target_coin, volume)

        # cancel whole orders
        for orders in self.session.get_order(self.target_coin):
            order_id = orders['uuid']
            self.session.cancel_order(order_id)

        print(datetime.now())
        print("!=== Terminate trading bot")
        sys.exit()