#!/usr/bin/env python3
import json
from influxdb_client import InfluxDBClient

def test_influxdb_connection(url, token, org, bucket):
    try:
        client = InfluxDBClient(url=url, token=token, org=org)
        if client.ping():
            print("Server responds")
        else:
            print("Server is not respongding to ping()")

        query_api = client.query_api()

        query = f'from(bucket: "{bucket}") |> range(start: -1h) |> last()'
        result = query_api.query(query)

        print(f'Successfully connected to InfluxDB instance at {url}')
        print(f'Result: {result}')
    except Exception as e:
        print(f'Error connecting to InfluxDB instance at {url}: {str(e)}')


if __name__ == '__main__':
    # CONFIG
    with open('config.json') as f:
        config = json.load(f)

    rpc_flask_api = config['RPC_FLASK_API']
    influxdb_url = config['INFLUXDB_URL']
    influxdb_token = config['INFLUXDB_TOKEN']
    influxdb_org = config['INFLUXDB_ORG']
    influxdb_bucket = config['INFLUXDB_BUCKET']

    test_influxdb_connection(influxdb_url,influxdb_token, influxdb_org, influxdb_bucket)
