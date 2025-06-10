import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Google Sheets bilan ulanish
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("shunchaki.json", scope)
client = gspread.authorize(creds)
sheet = client.open("MaktabBotData").sheet1

def save_to_sheet(data):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 📅 Sana va vaqt
    row = [
        timestamp,
        data['phone'],
        data['org'],
        data['event_count'],
        data['students'],
        ", ".join(data['photos'])
    ]
    sheet.append_row(row)
