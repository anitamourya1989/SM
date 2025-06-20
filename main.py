import requests
from bs4 import BeautifulSoup
from plyer import notification
import time
import logging
import re
import webbrowser
from datetime import datetime
import sqlite3

# BASE_URL = "https://www.screener.in/screens/1989343/near-ath-stocks-new/?page={}"
# BASE_URL = "https://www.screener.in/screens/2254716/ath-15/?page={}"
BASE_URL = "https://www.screener.in/screens/2380156/sme-gem-stocks/?page={}"

current_date = datetime.now().strftime('%Y-%m-%d')

# Logger for stock_position_log.txt
stock_logger = logging.getLogger('stock_logger')
stock_logger.setLevel(logging.INFO)
stock_handler = logging.FileHandler(f'stock_position_log_{current_date}.txt')
stock_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
stock_logger.addHandler(stock_handler)

# Logger for gem_log.txt
gem_logger = logging.getLogger('gem_logger')
gem_logger.setLevel(logging.INFO)
gem_handler = logging.FileHandler(f'gem_log_{current_date}.txt')
gem_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
gem_logger.addHandler(gem_handler)

# Track previously logged gems
logged_gems = set()

# Create a SQLite database connection
conn = sqlite3.connect('stock_positions.db')
cursor = conn.cursor()

# Create tables if they don't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_positions
    (company_name TEXT PRIMARY KEY, position INTEGER, down_52_high REAL, percent_down_ATH REAL, company_url TEXT, gem INTEGER, old_position INTEGER, new_position INTEGER, 
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, modified_at TEXT DEFAULT CURRENT_TIMESTAMP)
''')

def get_all_stock_positions():
    page_num = 1
    all_stock_positions = {}

    while True:
        url = BASE_URL.format(page_num)
        page = requests.get(url)
        soup = BeautifulSoup(page.content, "html.parser")
        
        rows = soup.find_all("tr", {"data-row-company-id": True})

        if page_num == 1:
            rowsdiv = soup.find_all("div", {"class": "flex-baseline options"})
            # Check if rowsdiv is not empty
            if rowsdiv:
                # Get all 'a' tags with class 'ink-900' in the first element of rowsdiv
                links = rowsdiv[0].find_all("a", class_="ink-900")
                
                # Check if 'links' is not empty
                if links:
                    last_ink_900 = links[-1]
                    last_ink_900_number = int(last_ink_900.text)
                else:
                    print("No links with class 'ink-900' found in rowsdiv[0].")
                    last_ink_900_number = 1  # Set a default value or handle appropriately
            else:
                print("No div found with class 'flex-baseline options'.")
                last_ink_900_number = 1  # Set a default value or handle appropriately

        # print(last_ink_900_number)
        if page_num == 9:
        # if page_num == last_ink_900_number:
            break
        if not rows:
            break

        for row in rows:
            number = row.find("td", class_="text").text.strip().rstrip('.')
            company_tag = row.find("a")
            company_name = company_tag.text.strip()

            url = company_tag['href']
            full_url = extract_company_id(url)

            company_url = "https://in.tradingview.com/chart/aeQ9eazg/?symbol={}".format(full_url)

            cells = row.find_all("td")

            # print(cells)
            current_price = float(cells[2].text.strip())
            all_time_high = float(cells[11].text.strip())

            down_52_high = float(cells[13].text.strip())
            week52_high = float(cells[12].text.strip())
            percent_down_ATH = round(((all_time_high - current_price) / all_time_high) * 100, 2)
            percent_down_52week = round(((week52_high - current_price) / week52_high) * 100, 2)

            gem = True if percent_down_ATH > down_52_high else False

            if gem is True:
                gem_logger.info(f"{company_name} with {percent_down_ATH}% of {all_time_high} high")
            
            if gem and company_name not in logged_gems:
                notification.notify(
                    title="New Gem Found!",
                    message=f"{company_name} with {percent_down_ATH}% of {all_time_high} high",
                    app_name="Stock Notifier",
                    timeout=10
                )
                webbrowser.open(company_url)
                logged_gems.add(company_name)

            all_stock_positions[company_name] = {
                'position': int(number),
                "down_52_high": down_52_high,
                "percent_down_ATH": percent_down_ATH,
                # "percent_down_52week": percent_down_52week,
                "company_url": company_url,
                "gem": gem
            }
        
        page_num += 1
    
    # Insert data into the database
    for company, details in all_stock_positions.items():
        cursor.execute('''
            INSERT OR REPLACE INTO stock_positions (company_name, position, down_52_high, percent_down_ATH, company_url, gem)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (company, details['position'], details['down_52_high'], details['percent_down_ATH'], details['company_url'], int(details['gem'])))
    conn.commit()

    # print(all_stock_positions)
    return all_stock_positions

def check_for_position_change(previous_positions, current_positions):
    for company, details in current_positions.items():
        if company in previous_positions and previous_positions[company]['position'] != details['position']:
        # if company in previous_positions:
            old_position = previous_positions[company]['position']
            new_position = details['position']
            gem = details['gem']
            percent_down_ATH = details['percent_down_ATH']
            
            # Update the database with the new positions
            cursor.execute('''
                UPDATE stock_positions 
                SET position = ?, down_52_high = ?, percent_down_ATH = ?, company_url = ?, gem = ?, 
                old_position = (SELECT position FROM stock_positions WHERE company_name = ?), 
                new_position = ?, modified_at = CURRENT_TIMESTAMP
                WHERE company_name = ?
            ''', (details['position'], details['down_52_high'], details['percent_down_ATH'], details['company_url'], int(details['gem']), company, details['position'], company))
            conn.commit()

            # if old_position is None and new_position < 20:
            if old_position is None:
                return company, previous_positions[company], details

            # print(old_position, new_position, company)
            # print("\n\n")
            if old_position > new_position and (old_position - new_position) >= 2 and new_position < 20:
                # print(old_position, new_position, company, '--------')
                return company, previous_positions[company], details

    return None, None, None

def extract_company_id(url):
    match = re.search(r'/company/([^/]+)/', url)
    if match:
        return match.group(1)
    return None

previous_positions = get_all_stock_positions()

while True:
    current_positions = get_all_stock_positions()
    company, old_pos, new_pos = check_for_position_change(previous_positions, current_positions)
    
    # print(company, old_pos, new_pos)
    if company:
        # print('yes')
        old_position = old_pos['position']
        new_position = new_pos['position']
        percent_down_ATH = new_pos['percent_down_ATH']
        
        stock_logger.info(f"{company} moved from {old_position} to {new_position} - {percent_down_ATH}%")

        # notification.notify(
        #     title="Stock Position Changed",
        #     message=f"{company} moved from {old_position} to {new_position}.",
        #     app_name="Stock Notifier",
        #     timeout=10
        # )

        if new_pos and "company_url" in new_pos:
            webbrowser.open(new_pos["company_url"])

        previous_positions = current_positions
    
    # print("Previous Positions: ", previous_positions)
    # print("Current Positions: ", current_positions)
    
    time.sleep(7)
