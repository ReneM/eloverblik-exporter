import requests
import jwt
import time
import json
import pytz
import os
from datetime import date, datetime, timedelta
from prometheus_client import CollectorRegistry, push_to_gateway
from prometheus_client.core import GaugeMetricFamily

DATA_ACCESS_TOKEN_FILENAME = 'data_access_token.txt' # Used for local storage

API_URL = os.environ.get('API_URL', 'https://api.eloverblik.dk/customerapi/api')
REFRESH_TOKEN = os.environ.get('REFRESH_TOKEN')
METERING_POINTS = os.environ.get('METERING_POINTS')
PUSH_GATEWAY_URL = os.environ.get('PUSH_GATEWAY_URL', 'http://victoria-metrics:8428/api/v1/import/prometheus')

def read_file(filename):
    try:
        with open(filename, 'r') as file:
            print(f'Token read from file {filename}')
            return file.read()
    except FileNotFoundError:
        print(f'The file "{filename}" does not exist.')
        return None

def save_to_file(token, filename):
    with open(filename, 'w') as file:
        print(f'Writing token to file {filename}')
        file.write(token)
        print(f'Token written to file {filename}')

def is_expired(token):
    token_decoded = jwt.decode(token, options={'verify_signature': False})
    if token_decoded and 'exp' in token_decoded:
        expiry_time = token_decoded['exp']
        current_time = time.time()
        return current_time > expiry_time
    return True

def get_data_access_token():
    data_access_token = read_file(DATA_ACCESS_TOKEN_FILENAME)

    if not data_access_token or is_expired(data_access_token):
        print('Data access token is expired or non-existing, refreshing')
        data_access_token = refresh_data_access_token()
        save_to_file(data_access_token, DATA_ACCESS_TOKEN_FILENAME)
    
    return data_access_token

def refresh_data_access_token():
    print('Fetching data access token')
    url = API_URL + '/token'
    headers = {
        "Authorization": f"Bearer {REFRESH_TOKEN}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        response_json = json.loads(response.text)
        print('Data access token refreshed successfully')
        return response_json.get('result')
    else:
        raise Exception('Failed to fetch data access token - response:' + response)

def get_time_series_data(data_access_token):
    date_to = date.today()
    date_from = date_to - timedelta(weeks=1) # Fetching the previous weeks data, any existing metrics will retain the same data.
    metering_points_formatted = ','.join(f'"{number}"' for number in METERING_POINTS.split(','))
    
    url = API_URL + '/meterdata/gettimeseries/' + str(date_from) + '/' + str(date_to) + '/Quarter'
    headers = {
        "Authorization": f"Bearer {data_access_token}",
        "Content-Type": "application/json"
    }
    data = '{"meteringPoints": {"meteringPoint": [' + metering_points_formatted + ']}}'
    response = requests.post(url, data, headers=headers)

    if response.status_code == 200:
        print('HTTP 200 received from API')
        response_json = response.json()
        return response_json['result'][0]['MyEnergyData_MarketDocument']['TimeSeries']

def get_timestamp_from_quarter(start_timestamp_str, quarter):
    start_timestamp = datetime.strptime(start_timestamp_str, '%Y-%m-%dT%H:%M:%SZ')
    start_timestamp = start_timestamp.replace(tzinfo=pytz.utc).astimezone() # Calculated into local timezone

    delta_minutes = (int(quarter) - 1) * 15
    time = start_timestamp + timedelta(minutes=delta_minutes)

    return time.timestamp()

class CustomCollector(object):
    def __init__(self):
        pass

    def collect(self):
        data_access_token = get_data_access_token()
        time_series_data = get_time_series_data(data_access_token)

        metric_gauge = GaugeMetricFamily('meter_data', 'Meter data from Eloverblik.dk', labels=['quality', 'business_type', 'meter_id'])
        print(f'Number of time series found: {0 if time_series_data is None else len(time_series_data)}')
        for time_series in time_series_data: # One per metering-id

            meter_id = time_series['mRID']
            for period in time_series['Period']:
                date = period['timeInterval']['start']
                points = period['Point']
                business_type = 'produced' if time_series['businessType'] == 'A01' else 'consumed'

                print(f'Parsing meter id {meter_id} for date {date}')
                for point in points:
                    position = point['position']
                    quantity = point['out_Quantity.quantity']
                    quality = point['out_Quantity.quality']
                    timestamp = get_timestamp_from_quarter(date, position)

                    #print(f'Adding metric: quality: {quality}, business_type: {business_type}, position: {position}, quantity: {quantity}, timestamp: {timestamp}')
                    metric_gauge.add_metric([quality, business_type, meter_id], quantity, timestamp=timestamp)

        yield metric_gauge

if __name__ == '__main__':
    print('Starting')
    
    registry = CollectorRegistry()
    registry.register(CustomCollector())

    print('Pushing metrics to gateway')
    push_to_gateway(PUSH_GATEWAY_URL ,job='eloverblik-exporter', registry=registry)
    print('Metrics pushed to gateway, stopping application')