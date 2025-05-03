from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import threading
import time
from datetime import datetime
import os
import re

app = Flask(__name__)

# Load Hidden Abilities
HIDDEN_ABILITY_FILE = "hidden_abilities.txt"
def load_hidden_abilities():
    abilities = {}
    if os.path.exists(HIDDEN_ABILITY_FILE):
        with open(HIDDEN_ABILITY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    name, abils = line.strip().split(":", 1)
                    abilities[name.strip()] = [a.strip() for a in abils.split(",")]
    return abilities

# Load Exotic Textures
EXOTIC_FILE = "exotic_prefixes.txt"
def load_exotic_prefixes():
    prefixes = set()
    if os.path.exists(EXOTIC_FILE):
        with open(EXOTIC_FILE, "r", encoding="utf-8") as f:
            for line in f:
                prefixes.add(line.strip())
    return prefixes

# Load Legendary Species
LEGENDARY_FILE = "legendary_species.txt"
def load_legendary_species():
    legends = set()
    if os.path.exists(LEGENDARY_FILE):
        with open(LEGENDARY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                legends.add(line.strip())
    return legends

HIDDEN_ABILITIES = load_hidden_abilities()
EXOTIC_PREFIXES = load_exotic_prefixes()
LEGENDARY_SPECIES = load_legendary_species()

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("/etc/secrets/credentials.json", scope)
client = gspread.authorize(credentials)
spreadsheet = client.open("Discord Sales Logger")
worksheet = spreadsheet.worksheet("GoldenSalesLog")

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

threading.Thread(target=flush_worker, daemon=True).start()

@app.route('/post-sale', methods=['POST'])
def post_sale():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON payload"}), 400
        if not isinstance(data, list):
            data = [data]

        for sale in data:
            required = ["item", "price", "amount", "type", "timestamp", "sheet", "ability", "ivs"]
            if not all(k in sale for k in required):
                return jsonify({"error": "Missing fields in payload"}), 400

            raw_item = sale["item"].strip()
            ability = sale["ability"]
            ivs = sale["ivs"]
            amount = sale["amount"]
            price = sale["price"]
            currency = sale["type"]
            timestamp_raw = sale["timestamp"]

            # Detect HA
            is_hidden = sale.get("hidden", False)
            if raw_item in HIDDEN_ABILITIES and ability in HIDDEN_ABILITIES[raw_item]:
                is_hidden = True

            clean_item = raw_item.replace("⭐", "").strip()
            form = ""
            is_shiny = False
            texture = ""
            base_species = clean_item

            if "(" in clean_item and ")" in clean_item:
                start = clean_item.find("(")
                end = clean_item.find(")", start)
                form = clean_item[start+1:end].strip()
                base_species = clean_item[:start].strip()

            words = base_species.split()
            remaining = []
            for word in words:
                if word.lower() == "shiny":
                    is_shiny = True
                elif word in EXOTIC_PREFIXES:
                    if word != "Shiny":
                        texture = word
                else:
                    remaining.append(word)
            base_species = " ".join(remaining)

            # Build full display name
            parts = []
            if is_shiny: parts.append("Shiny")
            if texture: parts.append(texture)
            parts.append(base_species)
            item_name = " ".join(parts)
            if form:
                item_name += f" ({form})"
            if is_hidden: item_name += " ⭐"
            if is_shiny: item_name += " ✨"
            if texture: item_name += " 🌀"
            if base_species in LEGENDARY_SPECIES: item_name += " 🗲"

            # Timestamp formatting
            try:
                dt = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
                sale_timestamp = dt.strftime("%Y/%m/%d %H:%M:%S")
            except:
                sale_timestamp = timestamp_raw
            inserted_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

            with batch_lock:
                batch_rows.append([
                    inserted_at,
                    ability,
                    ivs,
                    item_name,
                    amount,
                    price,
                    currency,
                    sale_timestamp
                ])

        return jsonify({"success": True}), 200

    except Exception as e:
        print(f"❌ API error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
