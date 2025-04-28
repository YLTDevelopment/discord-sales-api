from flask import Flask, request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = Flask(__name__)

# Set up Google Sheets access
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# Open your main Google Sheet
sheet = client.open("Discord Sales Logger")  # <- Change to your Sheet name if needed

@app.route('/post-sale', methods=['POST'])
def post_sale():
    data = request.get_json()
    item = data.get('item')
    price = data.get('price')
    timestamp = data.get('timestamp')
    target_sheet = data.get('sheet')

    if not item or not price or not timestamp or not target_sheet:
        return "Missing data", 400

    try:
        worksheet = sheet.worksheet(target_sheet)
    except:
        return "Sheet not found", 404

    # Insert into SalesLog
    worksheet.append_row([
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        item,
        price,
        timestamp
    ])

    return "Success", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
