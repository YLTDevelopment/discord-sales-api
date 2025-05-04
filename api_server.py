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
def load_hidden_abilities():
    abilities = {}
    if os.path.exists("hidden_abilities.txt"):
        with open("hidden_abilities.txt", "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    name, abils = line.strip().split(":", 1)
                    abilities[name.strip()] = [a.strip() for a in abils.split(",")]
    return abilities

# Load Exotic Textures
def load_exotic_prefixes():
    prefixes = set()
    if os.path.exists("exotic_prefixes.txt"):
        with open("exotic_prefixes.txt", "r", encoding="utf-8") as f:
            for line in f:
                prefixes.add(line.strip())
    return prefixes

# Load Legendary Species
def load_legendary_species():
    legends = set()
    if os.path.exists("legendary_species.txt"):
        with open("legendary_species.txt", "r", encoding="utf-8") as f:
            for line in f:
                legends.add(line.strip())
    return legends

HIDDEN_ABILITIES = load_hidden_abilities()
EXOTIC_PREFIXES = load_exotic_prefixes()
LEGENDARY_SPECIES = load_legendary_species()

# Item cleaner
def clean_item_name(item):
    item = re.sub(r"\[.*?\]", "", item)  # remove bracketed content
    item = re.sub(r"[^\w\s()%-]", "", item)  # remove emojis/symbols
    item = re.sub(r"\b\d+x\b", "", item, flags=re.IGNORECASE)  # remove 5x etc.
    item = re.sub(r"\bii\b", "", item, flags=re.IGNORECASE)  # remove 'ii'
    item = re.sub(r"\s+", " ", item)  # collapse spaces
    return item.strip().title()

# Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("/etc/secrets/credentials.json", scope)
client = gspread.authorize(credentials)
worksheet = client.open("Discord Sales Logger").worksheet("GoldenSalesLog")

batch_rows = []
batch_lock = threading.Lock()
FLUSH_INTERVAL = 5

def flush_worker():
    global batch_rows
    while True:
        time.sleep(FLUSH_INTERVAL)
        with batch_lock:
            valid_rows = [row for row in batch_rows if len(row) == 8]
            if valid_rows:
                try:
                    worksheet.append_rows(
                        valid_rows,
                        value_input_option="USER_ENTERED",
                        insert_data_option="INSERT_ROWS",
                        table_range="A2"
                    )
                    print(f"✅ Flushed {len(valid_rows)} valid rows.")
                    batch_rows = []
                except Exception as e:
                    print(f"❌ Error writing to sheet: {e}")
            else:
                print("⚠️ No valid rows to flush (missing columns).")

threading.Thread(target=flush_worker, daemon=True).start()

@app.route("/post-sale", methods=["POST"])
def post_sale():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No payload"}), 400
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
            is_hidden = sale.get("hidden", False)

            # Token item special case
            token_match = re.search(r"\[\?\s?([\d,]+)\]", raw_item)
            if token_match:
                token_amount = token_match.group(1).replace(",", "").strip()
                item_name = f"{token_amount} Tokens"
                ability = ""
                ivs = ""
                is_hidden = False
            else:
                cleaned_item = clean_item_name(raw_item.replace("⭐", "").strip())

                form = ""
                is_shiny = False
                texture = ""
                base_species = cleaned_item

                if "(" in cleaned_item and ")" in cleaned_item:
                    start = cleaned_item.find("(")
                    end = cleaned_item.find(")", start)
                    form = cleaned_item[start+1:end].strip()
                    base_species = cleaned_item[:start].strip()

                words = base_species.split()
                remaining = []
                for word in words:
                    if word.lower() == "shiny":
                        is_shiny = True
                    elif word in EXOTIC_PREFIXES and word != "Shiny":
                        texture = word
                    else:
                        remaining.append(word)
                base_species = " ".join(remaining)

                if base_species in HIDDEN_ABILITIES and ability in HIDDEN_ABILITIES[base_species]:
                    is_hidden = True

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
