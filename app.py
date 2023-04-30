#!/bin/env python3

from collections import OrderedDict
import json
from flask import Flask, jsonify, request
import sqlite3

app = Flask(__name__)

import os

app = Flask(__name__)

app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), 'live_database.db')

# Create the database table if it doesn't exist
def create_table():
    print(f"CREATING {app.config['DATABASE']}")
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS chain_data
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       chain_id INTEGER NOT NULL,
                       chain_name TEXT NOT NULL UNIQUE,
                       urls TEXT NOT NULL)''')
    conn.commit()
    conn.close()

# Create a new record
@app.route('/create', methods=['POST'])
def create_record():
    
    # Get the data from the request provided by flask
    data = request.get_json()

    # Check that all three entries are present
    if not all(key in data for key in ('chain_id', 'chain_name', 'urls')):
        return jsonify({'error': 'All three entries are required'}), 400

    # Extract the data from the request
    chain_id = data['chain_id']
    chain_name = data['chain_name']
    urls = data['urls']

    # Serialize the urls list to a JSON string
    urls_json = json.dumps(urls)

    # Insert the record into the app.config['DATABASE']
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('INSERT INTO chain_data (chain_id, chain_name, urls) VALUES (?, ?, ?)', (chain_id, chain_name, urls_json))
        record_id = c.lastrowid
        conn.commit()
        conn.close()
        return jsonify({'message': 'Record created successfully', 'id': record_id}), 201
    except sqlite3.IntegrityError as e:
        conn.rollback()  # Roll back the transaction
        conn.close()
        # Check the error message to see if the UNIQUE constraint was violated
        if "UNIQUE constraint failed: chain_data.chain_name" in str(e):
            error_msg = f"Chain name '{chain_name}' already exists."
        else:
            error_msg = str(e)
        return jsonify({'error': error_msg}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Get all records
@app.route('/all', methods=['GET'])
def get_all_records():
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('''SELECT id, chain_id, chain_name, urls
                      FROM chain_data''')
    records = cursor.fetchall()
    conn.close()
    results = []
    for record in records:
        results.append({'id': record[0],
                        'chain_id': record[1],
                        'chain_name': record[2],
                        'urls': json.loads(record[3])})
    return jsonify(results)

# Get a specific record by ID
@app.route('/get/<int:record_id>', methods=['GET'])
def get_record(record_id):
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('''SELECT id, chain_id, chain_name, urls
                      FROM chain_data
                      WHERE id = ?''', (record_id,))
    record = cursor.fetchone()
    conn.close()
    if record:
        return jsonify({'id': record[0],
                        'chain_id': record[1],
                        'chain_name': record[2],
                        'urls': json.loads(record[3])})
    else:
        return jsonify({'error': 'Record not found'}), 404


# Update an existing record
@app.route('/update/<int:record_id>', methods=['PUT'])
def update_record(record_id):
    try:
        chain_id = request.json['chain_id']
        chain_name = request.json['chain_name']
        urls = request.json['urls']
    except KeyError as e:
        return jsonify({'error': 'Missing required parameters'}), 400

    urls_json = json.dumps(urls)  # Convert list of URLs to JSON string
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute('''UPDATE chain_data
                        SET chain_id = ?, chain_name = ?, urls = ?
                        WHERE id = ?''',
                    (chain_id, chain_name, urls_json, record_id))
    except sqlite3.IntegrityError as e:
        conn.rollback()  # Roll back the transaction
        conn.close()
        # Check the error message to see if the UNIQUE constraint was violated
        if "UNIQUE constraint failed: chain_data.chain_name" in str(e):
            error_msg = f"Chain name '{chain_name}' already exists."
        else:
            error_msg = str(e)
        return jsonify({'error': error_msg}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        return jsonify({'error': 'No such record.'})
    else:
        return jsonify({'id': record_id,
                    'chain_id': chain_id,
                    'chain_name': chain_name,
                    'urls': urls})


# Delete a record by ID
@app.route('/delete/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('''DELETE FROM chain_data
                      WHERE id = ?''', (record_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Record deleted successfully'})

@app.route('/chain_info', methods=['GET'])
def get_chain_info():
    # Get parameters from the request URL
    chain_name = request.args.get('chain_name')
    chain_id = request.args.get('chain_id')

    # Connect to the app.config['DATABASE']
    conn = sqlite3.connect(app.config['DATABASE'])
    c = conn.cursor()

    # Query the app.config['DATABASE'] based on whether chain name or chain ID was provided
    if chain_name:
        c.execute("SELECT * FROM chain_data WHERE chain_name=?", (chain_name,))
    elif chain_id:
        c.execute("SELECT * FROM chain_data WHERE chain_id=?", (chain_id,))
    else:
        return jsonify({'error': 'Missing required parameters'}), 400

    # Fetch all the rows from the query
    rows = c.fetchall()

    # If no result was found, return an error
    if not rows:
        return jsonify({'error': 'Chain not found'}), 404

    # Convert the urls field from a string to a list
    result_dicts = []
    for result in rows:
        urls = json.loads(result[3])
        result_dict = {
            'id': result[0],
            'chain_id': result[1],
            'chain_name': result[2],
            'urls': urls
        }
        # Use OrderedDict to ensure that 'id' key is first
        ordered_dict = OrderedDict([('id', result[0])] + list(result_dict.items()))
        result_dicts.append(ordered_dict)
    # Return the chain info as JSON
    return jsonify(result_dicts), 200

if __name__ == '__main__':
    create_table()
    app.run(debug=True)

