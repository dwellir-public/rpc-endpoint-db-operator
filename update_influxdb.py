import asyncio
import json
import sys
import requests
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import time
from urllib.parse import urlparse
from rpc_utils import get_eth_block_height_ethbased, get_block_height_aptos, query_for_latency_and_blockheight
from influxdb_utils import new_latency_point, new_latest_block_height_point


# CONFIG
with open('config.json') as f:
    config = json.load(f)

rpc_flask_api = config['RPC_FLASK_API']
influxdb_url = config['INFLUXDB_URL']
influxdb_token = config['INFLUXDB_TOKEN']
influxdb_org = config['INFLUXDB_ORG']
influxdb_bucket = config['INFLUXDB_BUCKET']

# Create InfluxDB client
client = InfluxDBClient(url=influxdb_url, token=influxdb_token)

# Unwrap all RPC endpoints from all chains and place them in a list with their corresponding class.
# This is all the endpoints we are to query and update the influxdb with.

response = requests.get(f'{rpc_flask_api}/all')
all_url_api_tuples = []
for item in response.json():
    # Tuple of (url,rpc_class)
    endpoint_tuple = (item['urls'], item['rpc_class'])
    for rpc in endpoint_tuple[0]:
        all_url_api_tuples.append((rpc,endpoint_tuple[1]))


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

async def collect_info_from_endpoint(url, api_type):
    """
    Collect info.  (latency + latest_block)
    """
    try:
        info = await asyncio.wait_for(
            loop.run_in_executor(None, query_for_latency_and_blockheight, url, api_type),
            timeout=5
        )
    except Exception as e:
        print(f"Error fetching blockheight and latency from {url}:", e)
        info = None
    return info

# Define function to write data to InfluxDB
def write_to_influxdb(url, token, org, bucket, records):
    client = InfluxDBClient(url=url, token=token, org=org)
    write_api = client.write_api(write_options=SYNCHRONOUS)
    write_api.write(bucket=bucket, record=records)

# Main loop

if not test_influxdb_connection(influxdb_url,influxdb_token, influxdb_org, influxdb_bucket):
    print("Couldn't connect to influxdb.")
    sys.exit(1)

loop = asyncio.get_event_loop()
while True:
    # Get block heights from all endpoints asynchronously
    tasks = [collect_info_from_endpoint(url, api_type) for url, api_type in all_url_api_tuples]
    
    #TODO: Make it time out!
    info = loop.run_until_complete(asyncio.gather(*tasks))

    # Write data to InfluxDB
    all_records = []
    for endpoint, info_dict in zip(all_url_api_tuples, info):
        if info_dict:
            blockheight_point = new_latest_block_height_point(endpoint[0], endpoint[1], info_dict['latest_block_height'])
            latency_point = new_latency_point(endpoint[0], endpoint[1], info_dict)
            # Append the records to all_records
            records = []
            records.append(blockheight_point)
            records.append(latency_point)
            try:
                print(f"Writing to database {endpoint}: Block: {info_dict['latest_block_height']} Total Latency: {info_dict['time_total']}")
                write_to_influxdb(influxdb_url,influxdb_token,influxdb_org,influxdb_bucket, records)
            except Exception as e:
                print(f"Something went horribly wrong while trying to insert into influxdb {endpoint}: {info_dict}", e)
        else:
            print(f"Couldn't get information from {endpoint}. Skipping.")
    
    # Wait for 5 seconds
    time.sleep(5)
