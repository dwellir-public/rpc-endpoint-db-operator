### endpointdb



### Descripton:

 - db-init.py:  This script creates a sqlite database with RPC endpoint information and performs an initial healthcheck.

It will need the json files from this repo: https://github.com/ethereum-lists/chains/tree/master/_data

This repos/json-files contains a vast number of EIP155 chains (Ethereum etc.) which is a large class of chains.

The data is inserted into a table in the datbase.

Once the sqlite database has been created, you can query it like this:
    
    # Get some data about API endpoints that was responding within 3 seconds:
    $ sqlite3 rpc_database.db
    sqlite> SELECT chains.chainId,rpcs.id,highestBlock,rpcs.latency FROM rpcs,chains WHERE latency < 3;



 - cronos-blockdiff.py: This is an example script that meters an RPC endpoint and inserts the meassurements into an influxdb (Which is intended for grafana)


The intention is to tag the data with (at least) the following information: 

    bucket: blockheights
    Measurement: block_number
    tag_1=juju_model,value=string    # The juju model where the data comes from.
    tag_2=network_name,value=string  # A canonical name for the chain.
    tag_3=endpoint_url,value=string  # The URL used to retrieve the data.
    tag_4=network_id,value=string    # The network ID returned from the chain. Helps identify correctly the source of the datapoint.
