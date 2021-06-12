import csv
import requests
import json
import pyupbit as pybit
from time import sleep

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
        sleep(0.3)

    res = sorted(range(len(attention_score)), key=lambda sub: attention_score[sub])[-10:]
    top_attention_list = [total_coin_list[idx] for idx in res]

    return top_attention_list


if __name__ == '__main__':
    safe_list = get_safe_coin_list()
    top_volume = get_top_attention_coin(safe_list)
    print(top_volume)
