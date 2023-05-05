import asyncio
import sys
import requests
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import time
from urllib.parse import urlparse
from rpc_utils import get_eth_block_height_ethbased, get_block_height_aptos, query_for_latency_and_blockheight
from influxdb_utils import new_latency_point, new_latest_block_height_point

# Description: 
#    
#   This script queries an API endpoint and inserts the meassurement into the database.
#   Future improvements will get API endpoints from a database.
#   Future improvements will be able to execute in parallell.
#
#
# Install influxdb2:
# sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys D8FF8E1F7DF8B07E
# sudo apt-key update
# echo "deb https://repos.influxdata.com/ubuntu jammy stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
# curl -sL https://repos.influxdata.com/influxdb.key | sudo apt-key add -
# sudo apt-get update
# sudo apt install influxdb2
# sudo systemctl enable influxdb --now
# sudo influx setup

# ## Install python libs 
# sudo apt-get install python3-pip
# sudo pip3 install influxdb influxdb_client


# ## Create a token that can read and write to all buckets. (may be a bit much, but yeah.) Get the token value.
# sudo influx auth create --write-buckets --read-buckets

# ## Create a bucket for the blockheight data
# sudo influx bucket create -n blockheights -r 30d
 
# ## Test
#    influx write -t QtswU1QRCNzrH1R2ocK8m0xMhJ9oFPiE7OzAipIBhGb5_r1WkAXp9_rC6ls-_1-0Lh09RESvbvxNppNaYKBqsw==
# -b 717027696789dc58 -o dwellir --precision s "block_number,juju_model=myjujumodel,network_name=mychain,endpoint_url=wss://api.domain.se/foo block_height=1"

# ## Dropping all data from a bucket (for testing things): 
#   sudo influx delete --bucket blockheights --start 1970-01-01T00:00:00Z --stop "$(date --iso-8601=seconds)"
#

#
# Collect 5 public endpoints block-heights and insert them to a database.
#
# This will return a table with the average block height for each endpoint over the last hour, grouped by the endpoint
# SELECT MEAN("block_height_1"), MEAN("block_height_2"), MEAN("block_height_3"), MEAN("block_height_4"), MEAN("block_height_5") FROM "cronos_block_height" WHERE time > now() - 1h GROUP BY "endpoint"


# CONFIGS
RPC_FLASK_API="http://localhost:5000"
INFLUXDB_URL = "http://10.122.249.249:8086"
INFLUXDB_TOKEN = "hJaW1Me5OkQF3cwgCEVBPOT7RfUKFiL3YMEWVRShy5OL3EFOxmexqJM5aVtBmb30YKSZpD1ZyXBUSNC5hU8Usw=="
INFLUXDB_ORG = "dwellir"
INFLUXDB_BUCKET = "blockheights"

# Create InfluxDB client
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN)

# Unwrap all RPC endpoints from all chains and place them in a list with their corresponding class.
# This is all the endpoints we are to query and update the influxdb with.

response = requests.get(f'{RPC_FLASK_API}/all')
all_url_api_tuples = []
for item in response.json():
    # Tuple of (url,rpc_class)
    endpoint_tuple = (item['urls'], item['rpc_class'])
    for rpc in endpoint_tuple[0]:
        all_url_api_tuples.append((rpc,endpoint_tuple[1]))


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
                write_to_influxdb(INFLUXDB_URL,INFLUXDB_TOKEN,INFLUXDB_ORG,INFLUXDB_BUCKET, records)
            except Exception as e:
                print(f"Something went horribly wrong while trying to insert into influxdb {endpoint}: {info_dict}", e)
        else:
            print(f"Couldn't get information from {endpoint}. Skipping.")
    
    # Wait for 5 seconds
    time.sleep(5)
