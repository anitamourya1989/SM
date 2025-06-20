import requests
from bs4 import BeautifulSoup
from plyer import notification
import time
import json
from datetime import datetime

URL = "https://www.screener.in/screens/1989343/near-ath-stocks/?sort=down+from+52w+high&order=asc&limit=100&page=1"
LOG_FILE = "log.txt"

def get_stock_positions():
    page = requests.get(URL)
    soup = BeautifulSoup(page.content, "html.parser")
    rows = soup.find_all("tr", {"data-row-company-id": True})

    stock_positions = {}
    for row in rows:
        number = row.find("td", class_="text").text.strip().rstrip('.')
        company_tag = row.find("a")
        company_name = company_tag.text.strip()
        stock_positions[company_name] = int(number)
    
    return stock_positions

def log_positions(positions):
    with open(LOG_FILE, "a") as log:
        log.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {json.dumps(positions)}\n")

def load_previous_positions(date):
    with open(LOG_FILE, "r") as log:
        lines = log.readlines()
        for line in reversed(lines):
            log_date, log_positions = line.split(" - ")
            log_date = log_date.split()[0]
            if log_date == date:
                return json.loads(log_positions.strip())
    return None

def check_for_position_change(previous_positions, current_positions):
    changes = []
    for company, position in current_positions.items():
        if company not in previous_positions or previous_positions[company] != position:
            changes.append((company, previous_positions.get(company), position))
    return changes

def compare_at_330pm():
    current_time = datetime.now().strftime('%H:%M')
    if current_time == "15:30":
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        previous_positions = load_previous_positions(yesterday)
        current_positions = get_stock_positions()
        print(previous_positions)

        if previous_positions:
            changes = check_for_position_change(previous_positions, current_positions)
            for company, old_pos, new_pos in changes:
                notification.notify(
                    title="Stock Position Changed",
                    message=f"{company} moved from {old_pos} to {new_pos}.",
                    app_name="Stock Notifier",
                    timeout=10
                )
        else:
            print("No previous positions found for comparison.")
        
        log_positions(current_positions)  # Log today's positions at 3:30 PM.

# Main Loop
while True:
    current_time = datetime.now().strftime('%H:%M')
    
    if current_time == "15:30":
        compare_at_330pm()
    
    time.sleep(60)  # Check every minute to trigger at 3:30 PM.
