# --- Flask API for Google Sheets Logging ---

from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import threading, time, os, re
from datetime import datetime

app = Flask(__name__)

# Load Files
def load_file_set(filename):
    s = set()
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                s.add(line.strip())
    return s

def load_hidden_abilities():
    ha = {}
    if os.path.exists("hidden_abilities.txt"):
        with open("hidden_abilities.txt", "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    name, abils = line.strip().split(":", 1)
                    ha[name.strip()] = [a.strip() for a in abils.split(",")]
    return ha

HIDDEN_ABILITIES = load_hidden_abilities()
EXOTIC_PREFIXES = load_file_set("exotic_prefixes.txt")
LEGENDARY_SPECIES = load_file_set("legendary_species.txt")

# Sheet setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("/etc/secrets/credentials.json", scope)
client = gspread.authorize(credentials)
worksheet = client.open("Discord Sales Logger").worksheet("GoldenSalesLog")

batch_rows = []
batch_lock = threading.Lock()

def clean_item_name(item):
    item = re.sub(r"\[.*?\]", "", item)
    item = re.sub(r"[^\w\s()%-]", "", item)
    item = re.sub(r"\b\d+x\b", "", item, flags=re.IGNORECASE)
    item = re.sub(r"\bii\b", "", item, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", item).strip().title()

@app.route("/post-sale", methods=["POST"])
def post_sale():
    try:
        data = request.json
        if not isinstance(data, list):
            data = [data]

        for sale in data:
            raw_item = sale["item"]
            ability = sale["ability"]
            ivs = sale["ivs"]
            price = sale["price"]
            amount = sale["amount"]
            currency = sale["type"]
            ts_raw = sale["timestamp"]
            is_hidden = sale.get("hidden", False)

            token_match = re.search(r"\[\?\s?([\d,]+)\]", raw_item)
            if token_match:
                item_name = f"{token_match.group(1).replace(',', '').strip()} Tokens"
                ability, ivs, is_hidden = "", "", False
            else:
                cleaned = clean_item_name(raw_item.replace("⭐", ""))
                form = ""
                is_shiny, texture = False, ""
                if "(" in cleaned and ")" in cleaned:
                    form = cleaned[cleaned.find("(")+1 : cleaned.find(")")]
                    cleaned = cleaned[:cleaned.find("(")].strip()

                words = cleaned.split()
                base = []
                for w in words:
                    if w.lower() == "shiny":
                        is_shiny = True
                    elif w in EXOTIC_PREFIXES:
                        texture = w
                    else:
                        base.append(w)
                base_species = " ".join(base)
                if base_species in HIDDEN_ABILITIES and ability in HIDDEN_ABILITIES[base_species]:
                    is_hidden = True
                item_name = " ".join(filter(None, ["Shiny" if is_shiny else "", texture, base_species]))
                if form:
                    item_name += f" ({form})"
                if is_hidden: item_name += " ⭐"
                if is_shiny: item_name += " ✨"
                if texture: item_name += " 🌀"
                if base_species in LEGENDARY_SPECIES: item_name += " 🗲"

            try:
                dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                sale_ts = dt.strftime('%Y/%m/%d %H:%M:%S')
            except:
                sale_ts = ts_raw
            inserted_ts = time.strftime('%Y/%m/%d %H:%M:%S', time.gmtime())

            with batch_lock:
                batch_rows.append([
                    inserted_ts,
                    ability,
                    ivs,
                    item_name,
                    amount,
                    price,
                    currency,
                    sale_ts
                ])
        return jsonify({"success": True}), 200
    except Exception as e:
        print(f"API error: {e}")
        return jsonify({"error": str(e)}), 500

def flush_worker():
    while True:
        time.sleep(5)
        with batch_lock:
            if batch_rows:
                try:
                    worksheet.append_rows(batch_rows, value_input_option="USER_ENTERED")
                    print(f"✅ Flushed {len(batch_rows)} rows.")
                    batch_rows.clear()
                except Exception as e:
                    print(f"❌ Failed flush: {e}")

threading.Thread(target=flush_worker, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
