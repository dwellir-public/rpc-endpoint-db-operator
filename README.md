# endpointdb

This repo holds tools to maintain a database of public API:s for blockchains.

It also holds a tool to update an influx database with latency and blockheight information.

## Setup

### Prepare the environment

Install `influxdb2` and Python tools by running the `install-dependencies.sh` script in your target environment. 

    ./install-dependencies.sh

Enable `influxdb`.

    sudo systemctl enable influxdb --now

Set up `influx`. You will be prompted to configure the primary user and can answer as shown in the example below. For a production deployment, remember to store the selected login information in the keepass.

    sudo influx setup
    > Welcome to InfluxDB 2.0!
    ? Please type your primary username admin
    ? Please type your password ********
    ? Please type your password again ********
    ? Please type your primary organization name dwellir
    ? Please type your primary bucket name default
    ? Please type your retention period in hours, or 0 for infinite 0

Fetch the `endpointdb` repo to your target environment. If not already configured, you will need to create a new SSH key to add as a deploy key for the repo.

    # If a new key is needed
    ssh-keygen -t ed25519
    # Add ~/.ssh/id_ed25519.pub to 'Deploy keys' in the endpointdb repo on GitHub
    git clone git@github.com:dwellir-public/endpointdb.git

Create a new virtual environment in the repo and install the Python requirements.

    cd endpointdb
    python3 -m venv venv
    source venv/bin/activate
    pip3 install -r requirements.txt

Create an InfluxDB token that can read and write to all buckets (this level of access might be overkill, evaluate what's needed in production deployment). Be sure to store the token value in keepass for production deployments.

    sudo influx auth create --write-buckets --read-buckets

Create a bucket for the blockheight data.

    sudo influx bucket create -n blockheights -r 30d


### Start and initialize the database

The API endpoint database is an SQLite database which is interfaced and used via a Flask API.

Start the database, preferrably using a `screen`. Exit the screen gracefully with Ctrl + A + D.

    screen -S endpointdb-app
    > python3 app.py

Populate the database with initial information. The `json` directory in the repo conatins a number of `.json` files with blockchain RPC urls to use.

    python3 add-from-directory-json.py -d json

### Start the influx updater

To start pushing data to the influx database, we run the `update_influxdb.py` script. It can be run form the same machine as the database was initialized on but could also be run from an entirely different machine. The script uses the `config.json` file to set up Flask and InfluxDB parameters, make sure to edit it to use the correct database host IP and InfluxDB settings.

    screen -S update-influxdb  # optional
    python3 ./update_influxdb.py

## Usage

### Query the database via the API 

The Flask API supportes all of CRUD: "Create, Read, Update, Delete". Here follows some `curl` examples:

    curl -X POST -H "Content-Type: application/json" -d \
    '{
    "native_id": 999,
    "chain_name": "TESTCHAIN",
    "urls": ["https://foo.bar", "https://foo.bar"],
    "api_class": "polkadot"} ' http://localhost:5000/create

    {
    "id": 1,
    "message": "Record created successfully"
    }'

Get the record

    curl http://127.0.0.1:5000/get/1

Update the record

    curl -X PUT -H "Content-Type: application/json" -d '{"native_id": 888, "chain_name": "My test chain", "urls": ["https://polkadot-rpc.dwellir.com"], "api_class": "substrate"}' http://localhost:5000/update/1

Delete the record

    curl -X DELETE http://localhost:5000/delete/1

Get all records

    curl http://localhost:5000/all

Get an access token

    curl http://localhost:5000/token -d '{"username": "tmp", "password": "tmp"}' -H 'Content-Type: application/json'

Use access token in query

    curl http://localhost:5000/protected-route -H 'Authorization: Bearer <token>'

## Grafana

### Adding the datasource

- Select InfluxDB as the datasource type.
- Use Flux as the query language.
- Set the host IP and port (default port is 8086).
- Add the InflluxDB details, including the token generated when setting up the database.

![Example image](grafana-datasource-setup.png?raw=true "Example image")

### Running an influx query in grafana

You can use this example query in grafana, under the Explore section. Simply paste the code below and press "Run query". If both the `app.py` and `update_influxdb.py` scripts were started correctly, you should be getting a response from the database!

Example:

```
from(bucket: "blockheights")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "block_latency")
  |> filter(fn: (r) => r["url"] == "https://bsc-dataseed1.binance.org" or r["url"] == "https://bsc-dataseed1.defibit.io" or r["url"] == "https://bsc-dataseed1.ninicoin.io")
  |> filter(fn: (r) => r["_field"] == "block_height" or r["_field"] == "time_total")
```
