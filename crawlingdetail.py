import psycopg2
from psycopg2.extras import execute_values
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
from googletrans import Translator

connection = psycopg2.connect(
        dbname="auction",
        user="postgres",
        password="qwerty",  # Replace with your password
        host="localhost",
        port="5432"
    )
cur = connection.cursor()
# Initialize the translator
translator = Translator()

# Load the URL from the text file
with open('url.txt', 'r') as file:
    url = file.read().strip()

options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

# Initialize the WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get(url)

car_data = []
car_detail_data = []
detail_base_url = "https://auction.autobell.co.kr/auction/exhibitView.do"

# Get the total number of pages from the "Last" button
try:
    last_page_button = driver.find_element("xpath", '//button[contains(@class, "paging-last")]')
    total_pages = int(last_page_button.get_attribute('onclick').split('fnPaging(')[1].split(')')[0])
except Exception as e:
    print("Could not determine the total number of pages. Exiting...")
    driver.quit()
    raise e

# Loop through each page
for page in range(1, 2):
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    list_section = soup.find_all('div', class_="item")

    if not list_section:
        print("No items found")
    else:
        for index, item in enumerate(list_section):
            detail_button = item.find('a', class_='btn_view')
            if detail_button and 'href' in detail_button.attrs:
                detail_href = detail_button['href']
                gn = detail_button.get('gn')
                rc = detail_button.get('rc')
                acc = detail_button.get('acc')
                atn = detail_button.get('atn')

                detail_url = f"{detail_base_url}?acc={acc}&gn={gn}&rc={rc}&atn={atn}"
                print(f"Detail URL: {detail_url}")

                # Navigate to the detail page
                driver.get(detail_url)
                time.sleep(3)  # Wait for the detail page to load
                detail_soup = BeautifulSoup(driver.page_source, 'html.parser')
                chassis_number = None
                chassis_number_span = detail_soup.find('span', id='h_chasno')
                
                if chassis_number_span:
                    chassis_number = chassis_number_span.text.strip()
                    cur.execute("SELECT id FROM Cars WHERE car_id = %s", (chassis_number,))
                    car_exists = cur.fetchone()
                    if car_exists:
                        continue
                    print(f"Extracted Chassis Number (차대번호): {chassis_number}")
                    
                else:
                    print("Chassis Number (차대번호) not found.")
                # Extract data from the detail page
                detail_data = {}
                number = 0
                # Extract all images from the "view-wrap" container
                image_urls = []
                view_wrap = detail_soup.find('div', class_='view-wrap')
                if view_wrap:
                    img_tags = view_wrap.find_all('img')
                    for img_tag in img_tags:
                        if 'src' in img_tag.attrs:
                            image_urls.append(img_tag['src'])

                bid_detail = detail_soup.find('div', class_='bid-detail')
                if bid_detail:
                    car_info = bid_detail.find('div', class_='car-info')
                    if car_info:
                        ul = car_info.find('ul')
                        if ul:
                            li_items = ul.find_all('li')
                            if len(li_items) > 1:
                                product_number = li_items[1].text.strip()  # This should be '품목번호 1001'
                                number = product_number.split()[-1]  # This extracts '1001'
                                print("Extracted Number:", number)     
                data = {}
                table_section = detail_soup.find('div', class_='info-box')

                if table_section:
                    # Find all <dl> elements
                    dl_elements = table_section.find_all('dl')
                    
                    for dl in dl_elements:
                        dt_elements = dl.find_all('dt')  # Find all <dt> tags
                        dd_elements = dl.find_all('dd')  # Find all <dd> tags
                        
                        for dt, dd in zip(dt_elements, dd_elements):
                            
                            label = dt.text.strip()
                            if dd.find('span'):
                                value = dd.find('span').text.strip()
                            else:
                                value = dd.text.strip()
                            print(value, '-----------hi')
                            # Translate the label and value from Korean to English
                            translated_label = translator.translate(label, src='ko', dest='en').text
                            translated_value = translator.translate(value, src='ko', dest='en').text
                            data[translated_label] = translated_value

                else:
                    print("Table section not found")
                status_box = detail_soup.find('div', class_='status-box')
             
                image_url = None
                if status_box:
                    img_tag = status_box.find('div', class_='img-box').find('img')
                    image_url = img_tag['src'] if img_tag else None
                    
                else:
                    print("Status box not found")

                # Example additional information extraction
                car_detail_data.append({
                    'Images': image_urls, # Include all images
                    'CarId': chassis_number,
                    'Image': image_url,
                    'Info':data 
                })
                cur.execute("""
                        INSERT INTO Cars (car_id, main_image_url) 
                        VALUES (%s, %s) 
                        RETURNING id;
                    """, (chassis_number, image_url))

                # Get the inserted car's ID
                car_db_id = cur.fetchone()[0]
                # Insert data into the CarInfo table
                car_info_values = [(car_db_id, label, value) for label, value in data.items()]
                execute_values(cur, """
                    INSERT INTO CarInfo (car_id, label, value) 
                    VALUES %s;
                """, car_info_values)
                    # Insert data into the CarImages table
                car_images_values = [(car_db_id, img_url) for img_url in image_urls]
                execute_values(cur, """
                    INSERT INTO CarImages (car_id, image_url) 
                    VALUES %s;
                """, car_images_values)
                # Go back to the main list page
                driver.back()
                time.sleep(3)
                if index == 1:
                    break
            break
    break
    if page < total_pages:
        next_page_button = driver.find_element("xpath", f'//button[@onclick="fnPaging({page + 1})"]')
        next_page_button.click()
        time.sleep(3)

driver.quit()
connection.commit()
# Close the connection
cur.close()
connection.close()
with open('car_detail_data.json', 'w', encoding='utf-8') as detail_json_file:
    json.dump(car_detail_data, detail_json_file, ensure_ascii=False, indent=4)

print("Data saved to car_detail_data.json")
