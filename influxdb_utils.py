from datetime import datetime
from influxdb_client import Point, InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS


def new_block_height_request_point(chain: str, url: str, api: str, data: dict):
    http_code = int(data.get('http_code') or -1)
    time_total = float(data.get('time_total') or 0)
    exitcode = int(data.get('exitcode') or -1)
    latest_block_height = int(data.get('latest_block_height') or -1)

    # Create a Point object for the combined block data
    block_point = Point("block_height_request") \
        .tag("url", url) \
        .tag("api", api) \
        .tag("chain", chain) \
        .field("block_height", latest_block_height) \
        .field("http_code", http_code) \
        .field("time_total", time_total) \
        .field("exitcode", exitcode) \
        .time(datetime.utcnow())

    return block_point


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
