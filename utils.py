import csv
import requests
import json

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

if __name__ == '__main__':
    get_safe_coin_list()