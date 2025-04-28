from flask import Flask, request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = Flask(__name__)

# Setup Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# Open your Google Sheet
sheet = client.open("Discord Sales Logger")  # Change to your Google Sheet name

@app.route('/post-sale', methods=['POST'])
def post_sale():
    data = request.get_json()
    item = data.get('item')
    price = data.get('price')
    amount = data.get('amount')
    sale_type = data.get('type')  # Money / Token
    timestamp = data.get('timestamp')
    target_sheet = data.get('sheet')

    if not all([item, price, amount, sale_type, timestamp, target_sheet]):
        return "Missing data", 400

    try:
        worksheet = sheet.worksheet(target_sheet)
    except:
        return "Sheet not found", 404

    # Append to SalesLog
    worksheet.append_row([
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        item,
        price,
        amount,
        sale_type,
        timestamp
    ])

    return "Success", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
