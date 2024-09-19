import logging
import psycopg2
from psycopg2.extras import execute_values
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json
import time
from googletrans import Translator
from datetime import datetime

# Database connection
connection = psycopg2.connect(
        dbname="auction",
        user="postgres",
        password="qwerty",  # Replace with your password
        host="localhost",
        port="5432"
    )
cur = connection.cursor()
# Load the URL from the text file
with open('url.txt', 'r') as file:
    url = file.read().strip()

# Initialize logging
logging.basicConfig(level=logging.INFO)
def translate_text(text, src='ko', dest='en'):
    try:
        # Initialize the translator
        translator = Translator()
        translated = translator.translate(text, src=src, dest=dest).text
        return translated
    except Exception as e:
        logging.warning(f"Translation failed for text: {text}. Error: {e}")
        return text  # Return the original text if translation fails
    
# Set up WebDriver options
options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

# Initialize the WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get(url)

car_detail_data = []
detail_base_url = "https://auction.autobell.co.kr/auction/exhibitView.do"

date_format = '%B %d, %Y'
# Get the total number of pages from the "Last" button
try:
    last_page_button = driver.find_element("xpath", '//button[contains(@class, "paging-last")]')
    total_pages = int(last_page_button.get_attribute('onclick').split('fnPaging(')[1].split(')')[0])
except Exception as e:
    print("Could not determine the total number of pages. Exiting...")
    driver.quit()
    raise e

# Loop through each page
for page in range(1, 2):  # Adjust this range as needed
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
                    cur.execute("SELECT carid FROM Cars WHERE CarId = %s", (chassis_number,))
                    car_exists = cur.fetchone()
                    if car_exists:
                        continue
                    print(f"Extracted Chassis Number (차대번호): {chassis_number}")
                    
                else:
                    print("Chassis Number (차대번호) not found.")
                    continue

                # Extract data from the detail page
                detail_data = {}
                image_urls = []
                
                # Extract all images from the "view-wrap" container
                view_wrap = detail_soup.find('div', class_='view-wrap')
                if view_wrap:
                    img_tags = view_wrap.find_all('img')
                    
                    seen_urls = set()
                    unique_img_tags = []
                    
                    for img_tag in img_tags:
                        img_url = img_tag.get('src')
                        if img_url not in seen_urls:
                            seen_urls.add(img_url)
                            unique_img_tags.append(img_url)
                data = {}
                car_name = None
                car_name_tag = detail_soup.find('div', class_='head-box').find('h2', class_='car-name')
                if car_name_tag:
                    car_name = car_name_tag.text.strip()
                    print(f"Car Name: {car_name}")

                # Extract the car price
                car_price = None
                price_tag = detail_soup.find('div', class_='price-box').find('strong', class_='point')
                if price_tag:
                    car_price = price_tag.text.strip()
                    print(f"Car Price: {car_price} 만원")

                # Now add car name and price to the data dictionary
                data['Car Name'] = car_name
                data['Car Price'] = car_price
                index = 0
                data_labels = [ 
                    'Product type',
                    'Fuel Type',
                    'Engine Displacement',
                    'Seating Capacity',
                    'Purpose',
                    'Engine Model',
                    'Warranty',
                    'Last Regular Inspection',
                    'License Plate Number',
                    'Model Year',
                    'First Registration Date',
                    'Mileage',
                    'Color',
                    'Transmission',
                    'Seat Number'
                ]

                table_section = detail_soup.find('div', class_='info-box')
                if table_section:
                    dl_elements = table_section.find_all('dl')
                    for dl in dl_elements:
                        dt_elements = dl.find_all('dt')
                        dd_elements = dl.find_all('dd')

                        for dt, dd in zip(dt_elements, dd_elements):
                            dt_text = dt.text.strip()
                            
                            # Skip the element with dt as '완비서류'
                            if dt_text == '완비서류':
                                continue
                            
                            if dt_text == '차대번호':
                                continue
                            
                            if dt_text == '미비서류':
                                continue

                            # Process the corresponding dd value
                            value = dd.text.strip()
                            translated_value = translate_text(value, src='ko', dest='en')
                            
                            # Store in the data dictionary with the appropriate label
                            if index < len(data_labels):
                                data[data_labels[index]] = translated_value
                                index += 1

                
                status_box = detail_soup.find('div', class_='status-box')
                main_image_url = None
         
                if status_box:
                    img_tag = status_box.find('div', class_='img-box').find('img')
                    main_image_url = img_tag['src'] if img_tag else None
                # Insert data into Cars table
                # cur.execute("""
                #     INSERT INTO Cars (
                #         CarId, ImageUrl, ProductClassification, Fuel, Displacement, Salvation, 
                #         UseDistinction, Primitives, Storage, Periodic, CompleteDocuments, 
                #         CarNumber, YearType, InitialRegistrationDate, Mileage, Color, Transmission, SeatNumber, Insufficiency
                #     ) VALUES (
                #         %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                #     );
                # """, (
                #     chassis_number,
                #     main_image_url,
                #     data.get('Product classification'),
                #     data.get('fuel'),
                #     data.get('Displacement'),
                #     data.get('Salvation'),
                #     data.get('Use/distinction'),
                #     data.get('Primitives'),
                #     data.get('Storage'),
                #     datetime.strptime(data.get('Periodic'), date_format),
                #     data.get('Complete documents'),
                #     data.get('Car number'),
                #     int(data.get('Year')[-4:]) if 'Year' in data else None,
                #     datetime.strptime(data.get('Initial registration date'), date_format),
                #     int(data.get('Mileage', '0').replace(',', '').replace('km', '')) if 'Mileage' in data else None,
                #     data.get('color'),
                #     data.get('Transmission'),
                #     data.get('Seat number'),
                #     data.get('Insufficiency')
                # ))

                # Insert data into CarImages table
                car_images_values = [(chassis_number, img_url) for img_url in unique_img_tags]
                car_detail_data.append({'car':data, 'images': car_images_values})
                print(len(car_images_values),'-------len2')
                # execute_values(cur, """
                #     INSERT INTO CarImages (CarId, ImageUrl) 
                #     VALUES %s;
                # """, car_images_values)
                
                # Commit after each car data insertion
                connection.commit()

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
cur.close()
connection.close()

# Save the extracted data to a JSON file
with open('car_detail_data.json', 'w', encoding='utf-8') as detail_json_file:
    json.dump(car_detail_data, detail_json_file, ensure_ascii=False, indent=4)

print("Data saved to car_detail_data.json")
