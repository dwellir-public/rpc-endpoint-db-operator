import asyncio
import requests
from influxdb_client import InfluxDBClient
from datetime import datetime, timezone
import time
from urllib.parse import urlparse


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


# RPC endpoints. Cronos.
rpc_endpoints = [
    "https://rpc.cronos.network",
    "https://cronos1.okexchain.com",
    "https://cronos2.okexchain.com",
    "https://cronos3.okexchain.com",
    "https://cronos4.okexchain.com"
]

#influxdb_url = "http://localhost:8086"
#influxdb_token = "<INFLUXDB_ACCESS_TOKEN>"
#influxdb_org = "<INFLUXDB_ORG>"
#influxdb_bucket = "<INFLUXDB_BUCKET>"

influxdb_url = "http://localhost:8086"
influxdb_token = "<INFLUXDB_ACCESS_TOKEN>"
influxdb_org = "<INFLUXDB_ORG>"
influxdb_bucket = "<INFLUXDB_BUCKET>"


# Create InfluxDB client
client = InfluxDBClient(url=influxdb_url, token=influxdb_token)

# Define async function to get block height from an RPC endpoint
async def get_block_height(endpoint):
    try:
        response = await asyncio.wait_for(
            loop.run_in_executor(None, requests.post, endpoint, {"jsonrpc":"2.0","method":"cronos_blockNumber","params":[],"id":1}),
            timeout=5
        )
        block_height = int(response.json()["result"], 16)
    except:
        block_height = None
    return block_height

# Define function to write data to InfluxDB
def write_to_influxdb(block_heights):
    data = [
        {
            "measurement": "cronos_block_height",
            "tags": {"endpoint": urlparse(endpoint).netloc},
            "time": datetime.now(timezone.utc).isoformat(),
            "fields": {"block_height_" + str(i+1): block_height for i, block_height in enumerate(block_heights)}
        }
        for endpoint, block_heights in zip(rpc_endpoints, block_heights)
    ]
    client.write_api().write(influxdb_bucket, influxdb_org, data)

# Main loop
loop = asyncio.get_event_loop()
while True:
    # Get block heights from all endpoints asynchronously
    tasks = [get_block_height(endpoint) for endpoint in rpc_endpoints]
    block_heights = loop.run_until_complete(asyncio.gather(*tasks))

    # Write data to InfluxDB
    write_to_influxdb(block_heights)

    # Wait for 5 seconds
    time.sleep(5 - len(rpc_endpoints) * 0.2) # Subtract the time it took to get the block heights from the sleep time
