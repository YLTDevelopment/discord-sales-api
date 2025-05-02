from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import threading
import time
from datetime import datetime
import os

app = Flask(__name__)

# Load Hidden Abilities
HIDDEN_ABILITY_FILE = "hidden_abilities.txt"

def load_hidden_abilities():
    abilities = {}
    if os.path.exists(HIDDEN_ABILITY_FILE):
        with open(HIDDEN_ABILITY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and ":" in line:
                    name, abils = line.split(":", 1)
                    abilities[name.strip()] = [a.strip() for a in abils.split(",")]
    return abilities

HIDDEN_ABILITIES = load_hidden_abilities()

# Google Sheets Setup
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

credentials = ServiceAccountCredentials.from_json_keyfile_name("/etc/secrets/credentials.json", scope)
client = gspread.authorize(credentials)

SPREADSHEET_NAME = "Discord Sales Logger"
WORKSHEET_NAME = "GoldenSalesLog"
spreadsheet = client.open(SPREADSHEET_NAME)
worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

batch_lock = threading.Lock()
batch_rows = []
FLUSH_INTERVAL = 5

def flush_worker():
    global batch_rows
    while True:
        time.sleep(FLUSH_INTERVAL)
        with batch_lock:
            if batch_rows:
                try:
                    worksheet.append_rows(batch_rows, value_input_option="USER_ENTERED")
                    print(f"✅ Flushed {len(batch_rows)} rows to sheet.")
                    batch_rows = []
                except Exception as e:
                    print(f"❌ Error flushing batch: {e}")

flush_thread = threading.Thread(target=flush_worker, daemon=True)
flush_thread.start()

@app.route('/post-sale', methods=['POST'])
def post_sale():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON payload"}), 400

        if not isinstance(data, list):
            data = [data]

        for sale in data:
            required_fields = ["item", "price", "amount", "type", "timestamp", "sheet", "ability", "ivs"]
            if not all(field in sale for field in required_fields):
                return jsonify({"error": "Missing fields in payload"}), 400

            item = sale["item"]
            price = sale["price"]
            amount = sale["amount"]
            sale_type = sale["type"]
            ability = sale["ability"]
            ivs = sale["ivs"]

            # ⭐ Append star if hidden ability matches
            if item in HIDDEN_ABILITIES and ability in HIDDEN_ABILITIES[item]:
                item += " ⭐"

            try:
                dt = datetime.fromisoformat(sale["timestamp"].replace("Z", "+00:00"))
                sale_timestamp = dt.strftime("%Y/%m/%d %H:%M:%S")
            except Exception as e:
                print(f"❌ Error parsing timestamp: {e}")
                sale_timestamp = sale["timestamp"]

            inserted_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

            with batch_lock:
                batch_rows.append([
                    inserted_at,
                    ability,
                    ivs,
                    item,
                    amount,
                    price,
                    sale_type,
                    sale_timestamp
                ])

        return jsonify({"success": True}), 200

    except Exception as e:
        print(f"❌ API error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
