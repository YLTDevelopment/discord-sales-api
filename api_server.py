from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import threading
import time

app = Flask(__name__)

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# Use the secret file Render provides
credentials = ServiceAccountCredentials.from_json_keyfile_name("/etc/secrets/credentials.json", scope)
client = gspread.authorize(credentials)

# Target Spreadsheet and Worksheet
SPREADSHEET_NAME = "YourSpreadsheetNameHere"  # <- change to your real sheet name
WORKSHEET_NAME = "Sheet1"  # or whatever tab you want

spreadsheet = client.open(SPREADSHEET_NAME)
worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

# Batching
batch_lock = threading.Lock()
batch_rows = []

# Interval for flushing (in seconds)
FLUSH_INTERVAL = 5

# Background flush thread
def flush_worker():
    global batch_rows
    while True:
        time.sleep(FLUSH_INTERVAL)
        with batch_lock:
            if batch_rows:
                try:
                    worksheet.append_rows(batch_rows, value_input_option="RAW")
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

        required_fields = ["item", "price", "amount", "type", "timestamp", "sheet"]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing fields in payload"}), 400

        item = data["item"]
        price = data["price"]
        amount = data["amount"]
        sale_type = data["type"]
        timestamp = data["timestamp"]

        # Add to batch
        with batch_lock:
            batch_rows.append([timestamp, item, price, amount, sale_type])

        return jsonify({"success": True}), 200
    except Exception as e:
        print(f"❌ API error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
