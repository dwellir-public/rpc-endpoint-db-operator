### endpointdb



### Descripton:

This repo holds tools to maintain a database of public API:s for blockchains.

It also holds a tool to update an influx database with latency and blockheight information.

### Start and initialize the database

The API endpoint database is a sqlite database which is also interfaced/used via a Flask API.

Start the database like this.

    python3 ./app.y

Populate the database with initial information. This is read from a set of .json files in the directory "json".

    python3 add-from-directory-json.py -d json

### Start the influx updater

    python3 ./update_influxdb.py

### Query the database via the API 

The Flask API supportes all CRUD: "Create, Read, Update, Delete".

    curl -X POST -H "Content-Type: application/json" -d \
    '{
    "native_id": 999,
    "chain_name": "TESTCHAIN",
    "urls": ["https://foo.bar", "https://foo.bar"],
    "rpc_class": "polkadot"} ' http://localhost:5000/create

    {
    "id": 1,
    "message": "Record created successfully"
    }

Get the record

    curl http://127.0.0.1:5000/get/1

Update the record

    curl -X PUT -H "Content-Type: application/json" -d '{"native_id": 888, "chain_name": "My test chain", "urls": ["https://polkadot-rpc.dwellir.com"], "rpc_class": "substrate"}' http://localhost:5000/update/1

Delete the record

    curl -X DELETE http://localhost:5000/delete/1

Get all records

    curl http://localhost:5000/all
