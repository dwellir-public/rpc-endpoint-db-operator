### endpointdb



### Descripton:

This repo holds tools to maintain a database of public API:s for blockchains.

It also holds a tool to update an influx database with latency and blockheight information.


## Prepare the environment

Install and setup influxdb2
  
    sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys D8FF8E1F7DF8B07E
    sudo apt-key update
    echo "deb https://repos.influxdata.com/ubuntu jammy stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
    curl -sL https://repos.influxdata.com/influxdb.key | sudo apt-key add -
    sudo apt-get updat
    sudo apt install influxdb2
    sudo systemctl enable influxdb --now
    sudo influx setup

Install python libs etc.
    sudo apt install python3.10-venv
    python3 -m venv venv
    source venv/bin/activate
    sudo apt-get install python3-pip
    sudo pip3 install -r requirements.txt


Create a token that can read and write to all buckets. (may be a bit much, but yeah.) Get the token value.

    sudo influx auth create --write-buckets --read-buckets

Create a bucket for the blockheight data

    sudo influx bucket create -n blockheights -r 30d


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
    "api_class": "polkadot"} ' http://localhost:5000/create

    {
    "id": 1,
    "message": "Record created successfully"
    }

Get the record

    curl http://127.0.0.1:5000/get/1

Update the record

    curl -X PUT -H "Content-Type: application/json" -d '{"native_id": 888, "chain_name": "My test chain", "urls": ["https://polkadot-rpc.dwellir.com"], "api_class": "substrate"}' http://localhost:5000/update/1

Delete the record

    curl -X DELETE http://localhost:5000/delete/1

Get all records

    curl http://localhost:5000/all
