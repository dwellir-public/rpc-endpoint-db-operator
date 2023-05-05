from datetime import datetime
from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS

def new_latest_block_height_point(url: str, api: str, latest_block_height: int):
    # create a Point object for the latest block height data
    latest_block_height_point = Point("latest_block_height") \
        .tag("endpoint", url) \
        .tag("api", api) \
        .field("block_height", latest_block_height) \
        .time(datetime.utcnow())

    return latest_block_height_point

def new_latency_point(url: str, api: str, http_code: int, ssl_verify_result: int, 
                   time_redirect: float, time_namelookup: float, time_connect: float, 
                   time_appconnect: float, time_pretransfer: float, time_starttransfer: float, 
                   time_total: float, exitcode: int, errormsg: str):

    # create a Point object for the latency data
    latency_point = Point("latency") \
        .tag("url", url) \
        .tag("api", api) \
        .field("http_code", http_code) \
        .field("ssl_verify_result", ssl_verify_result) \
        .field("time_redirect", time_redirect) \
        .field("time_namelookup", time_namelookup) \
        .field("time_connect", time_connect) \
        .field("time_appconnect", time_appconnect) \
        .field("time_pretransfer", time_pretransfer) \
        .field("time_starttransfer", time_starttransfer) \
        .field("time_total", time_total) \
        .field("exitcode", exitcode) \
        .field("errormsg", errormsg) \
        .time(datetime.utcnow())

    return latency_point