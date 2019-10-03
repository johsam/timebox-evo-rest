#!/usr/bin/env python3
import argparse
import time
import requests
from dateutil import parser as date_parser
from yr.libyr import Yr


def update_forecast(location):

    evo_forecast = {'min': {'timestamp': 0, 'temp': 100, 'symbol': '1'}, 'max': {'timestamp': 0, 'temp': -100, 'symbol': '1'}}
    now = int(time.time())

    weather = Yr(location_name=location, forecast_link='forecast_hour_by_hour')

    for forecast in weather.forecast(as_json=False):
        from_time = forecast['@from']
        timestamp = int(date_parser.parse(from_time).timestamp())

        if timestamp < now or timestamp > now + 12 * 3600:
            continue

        symbol = forecast['symbol']['@var']
        temp = int(forecast['temperature']['@value'])

        #print(timestamp, from_time, symbol, temp)

        if temp <= evo_forecast['min']['temp']:
            evo_forecast['min']['temp'] = temp
            evo_forecast['min']['timestamp'] = timestamp
            evo_forecast['min']['symbol'] = symbol

        if temp > evo_forecast['max']['temp']:
            evo_forecast['max']['temp'] = temp
            evo_forecast['max']['timestamp'] = timestamp
            evo_forecast['max']['symbol'] = symbol

    requests.post('http://localhost:3333/evo/forecast', json=evo_forecast)

    # print(evo_forecast)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('-l', '--location', required=False, default="Norge/Telemark/Skien/Skien", dest='location',
                        help='Location for forecast')

    args = parser.parse_args()

    update_forecast(args.location)


if __name__ == '__main__':
    main()
