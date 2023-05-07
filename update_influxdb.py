#!/usr/bin/env python3
import asyncio
import json
import logging
import sys
import requests
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import time
from urllib.parse import urlparse
from rpc_utils import get_eth_block_height_ethbased, get_block_height_aptos, query_for_latency_and_blockheight
from influxdb_utils import new_latency_point, new_latest_block_height_point, test_influxdb_connection
from color_logger import ColoredFormatter

async def collect_info_from_endpoint(loop, url, api_type):
    """
    Collect info.  (latency + latest_block)
    """
    try:
        info = await asyncio.wait_for(
            loop.run_in_executor(None, query_for_latency_and_blockheight, url, api_type),
            timeout=5
        )
    except asyncio.exceptions.TimeoutError as timeouterror:
        logger.error(f"A timeout occured while trying to get into from {url} {timeouterror}")
        info = None
    except Exception as e:
        logger.error(f"Error fetching blockheight and latency from {url}:", str(e))
        info = None
    return info

# Define function to write data to InfluxDB
def write_to_influxdb(url, token, org, bucket, records):
    try:
        client = InfluxDBClient(url=url, token=token, org=org)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=bucket, record=records)
    except Exception as e:
        logger.critical(f"Failed writing to influx. This shouldn't happen.", e)
        sys.exit(1)


# Main loop

def main(logger, influxdb_url, influxdb_token, influxdb_org, influxdb_bucket, all_url_api_tuples, collect_info_from_endpoint, write_to_influxdb):
    loop = asyncio.get_event_loop()
    while True:
    # Get block heights from all endpoints asynchronously
        tasks = [collect_info_from_endpoint(loop, url, api_type) for url, api_type in all_url_api_tuples]
    
    #TODO: Make it time out!
        info = loop.run_until_complete(asyncio.gather(*tasks))

        for endpoint, info_dict in zip(all_url_api_tuples, info):
            if info_dict:
                blockheight_point = new_latest_block_height_point(endpoint[0], endpoint[1], info_dict['latest_block_height'])
                latency_point = new_latency_point(endpoint[0], endpoint[1], info_dict)
                records = []
                records.append(blockheight_point)
                records.append(latency_point)
                try:
                    logger.debug(f"Writing to database {endpoint}: Block: {info_dict['latest_block_height']} Total Latency: {info_dict['time_total']}")
                    write_to_influxdb(influxdb_url,influxdb_token,influxdb_org,influxdb_bucket, records)
                except Exception as e:
                    logger.error(f"Something went horribly wrong while trying to insert into influxdb {endpoint}: {info_dict}", e)
            else:
                logger.warning(f"Couldn't get information from {endpoint}. Skipping.")
    
    # Wait for 5 seconds
        time.sleep(5)

if __name__ == '__main__':
    
    # create logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    # create console handler and set level to debug
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    # create formatter
    formatter = ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s')
    # add formatter to console handler
    console_handler.setFormatter(formatter)
    # add console handler to logger
    logger.addHandler(console_handler)

    # CONFIG
    with open('config.json') as f:
        config = json.load(f)

    rpc_flask_api = config['RPC_FLASK_API']
    influxdb_url = config['INFLUXDB_URL']
    influxdb_token = config['INFLUXDB_TOKEN']
    influxdb_org = config['INFLUXDB_ORG']
    influxdb_bucket = config['INFLUXDB_BUCKET']

    # Test connection to influx
    if not test_influxdb_connection(influxdb_url,influxdb_token, influxdb_org, influxdb_bucket):
        logger.error("Couldn't connect to influxdb.")
        sys.exit(1)

    # Create InfluxDB client
    client = InfluxDBClient(url=influxdb_url, token=influxdb_token)

    # Get all RPC endpoints from all chains and place them in a list with their corresponding class.
    # This is all the endpoints we are to query and update the influxdb with.

    response = requests.get(f'{rpc_flask_api}/all')
    all_url_api_tuples = []
    for item in response.json():
        # Tuple of (url,api_class)
        endpoint_tuple = (item['urls'], item['api_class'])
        for rpc in endpoint_tuple[0]:
            all_url_api_tuples.append((rpc,endpoint_tuple[1]))
    
    main(logger, influxdb_url, influxdb_token, influxdb_org, influxdb_bucket, all_url_api_tuples, collect_info_from_endpoint, write_to_influxdb)