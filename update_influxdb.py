#!/usr/bin/env python3
import asyncio
import json
import logging
import sys
import requests
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import time
from rpc_utils import fetch_all_info, get_aptos, get_ethereum, get_substrate, is_valid_url
from influxdb_utils import new_latency_point, new_latest_block_height_point, test_influxdb_connection
from color_logger import ColoredFormatter


# Define function to write data to InfluxDB
def write_to_influxdb(url, token, org, bucket, records):
    try:
        client = InfluxDBClient(url=url, token=token, org=org)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=bucket, record=records)
    except Exception as e:
        logger.critical(f"Failed writing to influx. This shouldn't happen. {str(e)}")
        sys.exit(1)

def load_endpoints(rpc_flask_api, cache_refresh_interval=30):
    """Load endpoints from cache or refresh if cache is stale."""

    # Load cached value from file
    try:
        with open('cache.json', 'r') as f:
            all_url_api_tuples, last_cache_refresh = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_url_api_tuples, last_cache_refresh = None, 0

    # Check if cache is stale
    if time.time() - last_cache_refresh > cache_refresh_interval:
        force_refresh_cache = True
    else:
        diff = time.time() - last_cache_refresh
        remains = cache_refresh_interval - diff
        logger.info(f"Cache will be updated in: {remains}")
        force_refresh_cache = False

    # Refresh cache if needed
    if force_refresh_cache:
        try:
            logger.info("Updating cache from endpoints API")
            all_url_api_tuples = get_all_endpoints_from_api(rpc_flask_api)
            last_cache_refresh = time.time()

            # Save updated cache to file
            with open('cache.json', 'w') as f:
                json.dump((all_url_api_tuples, last_cache_refresh), f)

        except Exception as e:
            # Log the error
            logger.error(f"An error occurred while getting endpoints: {str(e)}")

            # Load the previous cache value
            with open('cache.json', 'r') as f:
                all_url_api_tuples, last_cache_refresh = json.load(f)

    else:
        logger.info("Using cached endpoints")

    return all_url_api_tuples

def get_all_endpoints_from_api(rpc_flask_api):
    response = requests.get(f'{rpc_flask_api}/all')
    all_url_api_tuples = []
    for item in response.json():
        # Tuple of (url,api_class)
        endpoint_tuple = (item['urls'], item['api_class'])
        for rpc in endpoint_tuple[0]:
            all_url_api_tuples.append((rpc,endpoint_tuple[1]))
    return all_url_api_tuples


if __name__ == '__main__':
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    with open('config.json') as f:
        config = json.load(f)

    rpc_flask_api = config['RPC_FLASK_API']
    influxdb_url = config['INFLUXDB_URL']
    influxdb_token = config['INFLUXDB_TOKEN']
    influxdb_org = config['INFLUXDB_ORG']
    influxdb_bucket = config['INFLUXDB_BUCKET']
    rpc_request_timeout = config['RPC_REQUEST_TIMEOUT']
    cache_max_age=config['CACHE_MAX_AGE']

    # Test connection to influx before attemting start.
    if not test_influxdb_connection(influxdb_url,influxdb_token, influxdb_org, influxdb_bucket):
        logger.error("Couldn't connect to influxdb. Exit.")
        sys.exit(1)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError as ex:
        if "no current event loop" in str(ex):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        else:
            raise

    
    while True:
        # Get all RPC endpoints from all chains.
        # Place them in a list with their corresponding class.
        # This is all the endpoints we are to query and update the influxdb with.
        # all_url_api_tuples = get_all_endpoints_from_api(rpc_flask_api)
        all_url_api_tuples = load_endpoints(rpc_flask_api,cache_refresh_interval=cache_max_age)

        print("==============", all_url_api_tuples)

        # info = loop.run_until_complete(fetch_all_info(all_url_api_tuples))
        
        info = loop.run_until_complete(await fetch_all_info(all_url_api_tuples))

        print("============================================")

        print(info)

        for endpoint, info_dict in zip(all_url_api_tuples, info):
            if info_dict:
                blockheight_point = new_latest_block_height_point(endpoint[0], endpoint[1], info_dict['latest_block_height'])
                latency_point = new_latency_point(endpoint[0], endpoint[1], info_dict)
                records = []
                records.append(blockheight_point)
                records.append(latency_point)
                try:
                    logger.debug(f"Writing to database {endpoint}: Block: {info_dict['latest_block_height']} Total Latency: {info_dict['time_total']}")
    
                    if int(info_dict['exitcode']) > 0:
                        logger.warning(f"Non zero exit_code found for {endpoint}. I will store the information in influx, but this is an indication that the endpoint isnt healthy.")
    
                    write_to_influxdb(influxdb_url,influxdb_token,influxdb_org,influxdb_bucket, records)
                
                except Exception as e:
                    logger.error(f"Something went horribly wrong while trying to insert into influxdb {endpoint}: {info_dict}", e)
            else:
                logger.warning(f"Couldn't get information from {endpoint}. Skipping.")
    
        # Wait for 5 seconds before running again. Allows us to see what goes on.
        # Possibly we can remove this later.
        time.sleep(5)