from datetime import datetime
import asyncio
from influxdb_client import Point, InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

from rpc_utils import get_aptos, get_ethereum, get_substrate


def new_block_height_request_point(chain: str, url: str, api: str, data: dict) -> Point:
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


def test_influxdb_connection(url: str, token: str, org: str) -> bool:
    """
    Test the connection to the database.
    """
    client = InfluxDBClient(url=url, token=token, org=org)
    try:
        return client.ping()
    except Exception as e:
        print(e)
        return False


async def fetch_info(api_url: str, api_class: str):
    if api_class == 'aptos':
        info = await get_aptos(api_url)
    elif api_class == 'substrate':
        info = await get_substrate(api_url)
    elif api_class == 'ethereum':
        info = await get_ethereum(api_url)
    else:
        raise ValueError('Invalid api_class:', api_class)
    return info


async def fetch_all_info(all_url_api_tuples: list):
    loop = asyncio.get_event_loop()  # Reuse the current event loop
    tasks = []
    for _, url, api_class in all_url_api_tuples:
        tasks.append(loop.create_task(fetch_info(url, api_class)))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
