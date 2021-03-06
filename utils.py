import csv
import requests
import json
import pyupbit as pybit
import jwt
import os
from time import sleep
from urllib.parse import urlencode
from account_config import get_account
import uuid
import  hashlib

def get_safe_coin_list():
    safe_coins = []
    url = "https://api.upbit.com/v1/market/all"
    querystring = {"isDetails": "true"}
    headers = {"Accept": "application/json"}
    response = requests.request("GET", url, headers=headers, params=querystring)
    coin_info_dict = json.loads(response.text)

    for coin_info in coin_info_dict:
        if 'NONE' in coin_info.values():
            safe_coins.append(coin_info['market'])

    result = [ticker for ticker in safe_coins if 'KRW' in ticker]

    return result

def get_top_attention_coin(total_coin_list):
    # return top10 raising coins
    attention_score = []
    for ticker in total_coin_list:
        day_candle = pybit.get_ohlcv(ticker, interval="day")['close']
        attention_score.append(day_candle[-1]/day_candle[-2])
        sleep(0.5)

    res = sorted(range(len(attention_score)), key=lambda sub: attention_score[sub])[-10:]
    top_attention_list = [total_coin_list[idx] for idx in res]

    return top_attention_list

def get_7day_volume_percentage(ticker, interval="minute1"):
    day_volume = pybit.get_ohlcv(ticker, interval="day")['volume'][-7:]
    sleep(0.5)
    minute_volume = pybit.get_ohlcv(ticker, interval=interval)['volume'].tolist()
    minute_avg = sum(minute_volume)/len(minute_volume)
    day_average = sum(((day_volume/24.0)/60.0).tolist())/len(day_volume)

    return minute_avg/day_average


def get_1hour_volume_percentage(ticker, interval="minute1"):
    minute_volume = pybit.get_ohlcv(ticker, interval=interval)['volume'][-60:].tolist()
    minute_avg = sum(minute_volume) / len(minute_volume)
    current_volume = minute_volume[-1]

    return current_volume / minute_avg


def get_10min_volume_percentage(ticker, interval="minute1"):
    minute_volume = pybit.get_ohlcv(ticker, interval=interval)['volume'].tolist()
    minute_avg = sum(minute_volume[-11:-1]) / 10
    current_volume = minute_volume[-1]

    return current_volume / minute_avg



if __name__ == '__main__':
    #safe_list = get_safe_coin_list()
    #top_volume = get_top_attention_coin(safe_list)
    #print(top_volume)
    #get_whole_order_list()
    get_10min_volume_percentage("KRW-XRP")
