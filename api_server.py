from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime

app = Flask(__name__)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(credentials)

SPREADSHEET_ID = "your_spreadsheet_id_here"  # Replace with your real Spreadsheet ID

def append_sale(worksheet, sale):
    worksheet.append_row([
        sale.get("timestamp", datetime.utcnow().isoformat()),
        sale.get("item"),
        sale.get("price"),
        sale.get("amount"),
        sale.get("type")
    ])

@app.route('/post-sale', methods=['POST'])
def post_sale():
    try:
        data = request.get_json()

        if isinstance(data, list):
            # Batch: multiple sales at once
            for sale in data:
                sheet_name = sale.get('sheet')
                if not sheet_name:
                    return jsonify({"error": "Missing sheet field in batch entry."}), 400
                worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(sheet_name)
                append_sale(worksheet, sale)
        else:
            # Single: just one sale
            sheet_name = data.get('sheet')
            if not sheet_name:
                return jsonify({"error": "Missing sheet field."}), 400
            worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(sheet_name)
            append_sale(worksheet, data)

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
