import json
import sqlite3

#
# Import and export json into database.
#

def import_json_file(filename, db_filename):
    """
    Imports data from a JSON file into a SQLite database.
    Assumes the JSON file has the same format as the output of the export_json_file() function.
    """
    with open(filename, 'r') as f:
        data = json.load(f)
    conn = sqlite3.connect(db_filename)
    c = conn.cursor()
    for row in data:
        native_id = row['native_id']
        chain_name = row['chain_name']
        urls = json.dumps(row['urls'])
        c.execute("INSERT INTO chain_data (native_id, chain_name, urls) VALUES (?, ?, ?)", (native_id, chain_name, urls))
    conn.commit()
    conn.close()

def export_json_file(filename, db_filename):
    """
    Exports data from a SQLite database into a JSON file.
    The output JSON file has the same format as the input file for the import_json_file() function.
    """
    conn = sqlite3.connect(db_filename)
    c = conn.cursor()
    rows = c.execute("SELECT native_id, chain_name, urls FROM chain_data").fetchall()
    data = []
    for row in rows:
        native_id = row[0]
        chain_name = row[1]
        urls = json.loads(row[2])
        data.append({'native_id': native_id, 'chain_name': chain_name, 'urls': urls})
    with open(filename, 'w') as f:
        json.dump(data, f)
    conn.close()
