from datetime import datetime
from influxdb_client import Point, InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

def new_latest_block_height_point(url: str, api: str, latest_block_height: int):
    # create a Point object for the latest block height data
    latest_block_height_point = Point("latest_block_height") \
        .tag("url", url) \
        .tag("api", api) \
        .field("block_height", latest_block_height) \
        .time(datetime.utcnow())

    return latest_block_height_point

def new_latency_point(url: str, api: str, data: dict):
    http_code = int(data.get('http_code', None))
    time_total = float(data.get('time_total', None))
    exitcode = int(data.get('exitcode', None))

    # create a Point object for the latency data
    latency_point = Point("latency") \
        .tag("url", url) \
        .tag("api", api) \
        .field("http_code", http_code) \
        .field("time_total", time_total) \
        .field("exitcode", exitcode) \
        .time(datetime.utcnow())

    return latency_point

def test_influxdb_connection(url, token, org, bucket):
    """
    Test the connection to the database.
    """
    client = InfluxDBClient(url=url, token=token, org=org)
    try:
        if client.ping():
            return True
        else:
            return False
    except Exception as e:
        print(e)
        return False