import datetime
import json
import os
import time

import pandas
import pyupbit
import requests

UPBIT_ACCESS = None
UPBIT_SECRET = None
BOT_TOKEN = None
USER_CHAT_ID = None


def get_exception(function, text):
    return Exception(f"[{function}] {text}")


def get_env(key):
    function = "get_env"

    if key is None:
        raise get_exception(function, "`key` is None")

    value = os.getenv(key)

    if value is None:
        raise get_exception(function, f"`os.getenv('{key}')` is None")

    return value


def send(text):
    global BOT_TOKEN, USER_CHAT_ID

    function = "send"

    response = requests.get(
        url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        params={"chat_id": USER_CHAT_ID, "text": text},
        headers={"Accept": "application/json"}
    )

    if not response.ok:
        raise get_exception(function, response.json().get("description"))

    response = response.json().get("result").get("text")

    if response != text:
        raise get_exception(function, response)

    print(text)


def get_prices(count):
    function = "get_prices"

    response = requests.get(
        url="https://api.upbit.com/v1/candles/days",
        params={"market": "KRW-BTC", "count": count},
        headers={"Accept": "application/json"}
    )

    candles = json.loads(response.text)

    if type(candles) is dict:
        raise get_exception(function, candles["error"])

    prices = list(int(candle["trade_price"]) for candle in reversed(candles))
    return prices


def get_ema(values, span):
    series = pandas.Series(values)
    ewm = series.ewm(span=span, adjust=False)
    ema = ewm.mean()
    return ema


def get_oscillator():
    prices = get_prices(200)
    ema_12 = get_ema(prices, 12)
    ema_26 = get_ema(prices, 26)
    macd = ema_12 - ema_26
    signal = get_ema(macd, 9)
    oscillator = macd.iloc[-1] - signal.iloc[-1]
    return oscillator


def main():
    global UPBIT_ACCESS, UPBIT_SECRET, BOT_TOKEN, USER_CHAT_ID

    # noinspection PyBroadException
    try:
        UPBIT_ACCESS = get_env("upbit_access")
        UPBIT_SECRET = get_env("upbit_secret")
        BOT_TOKEN = get_env("bot_token")
        USER_CHAT_ID = get_env("user_chat_id")

        upbit = pyupbit.Upbit(UPBIT_ACCESS, UPBIT_SECRET)

        send(f"Program started ({"{:,}".format(int(upbit.get_balance("KRW")))})")

        check_btc = True
        check_running = True
    except Exception as exception:
        try:
            send(str(exception))
        finally:
            print(exception)

        return

    while True:
        # noinspection PyBroadException
        try:
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))

            if now.hour == 8 and now.minute >= 50:
                if check_btc:
                    oscillator = get_oscillator()

                    if oscillator <= 0:
                        btc = upbit.get_balance("BTC")

                        if btc > 0:
                            upbit.sell_market_order("KRW-BTC", btc)
                    else:
                        krw = upbit.get_balance("KRW")

                        if krw > 10000:
                            upbit.buy_market_order("KRW-BTC", krw * 0.9995)

                    check_btc = False
            else:
                check_btc = True

            if now.hour == 12:
                if check_running:
                    oscillator = get_oscillator()
                    send(f"Program running ({"{:,}".format(int(oscillator)})")

                    check_running = False
            else:
                check_running = True

            time.sleep(30)
        except Exception as exception:
            try:
                send(str(exception))
            finally:
                print(exception)


if __name__ == '__main__':
    main()
