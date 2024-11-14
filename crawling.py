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
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d')  # Convert datetime to string in the format 'YYYY-MM-DD'
    raise TypeError("Type not serializable")

def extract_manufacturer_and_clean_name(car_name):
    manufacturer = None
    match = re.search(r'\[(.*?)\]', car_name)
    if match:
        manufacturer = match.group(1)
        car_name = re.sub(r'\[.*?\]', '', car_name).strip() 
    return manufacturer, car_name

# Database connection
connection = psycopg2.connect(
        dbname="postgres",
        user="admin",
        password="socar", 
        host="18.167.136.248",
        port="5432"
    )
cur = connection.cursor()
# Load the URL from the text file
with open('url.txt', 'r') as file:
    url = file.read().strip()

# Initialize logging
logging.basicConfig(level=logging.INFO)
def translate_text(text, src='ko', dest='en'):
    if isinstance(text, datetime) or text == None:
        return text  # Convert datetime to string format 'YYYY-MM-DD'
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

korean_date_format = "%Y년 %m월 %d일"
# Get the total number of pages from the "Last" button

select_element = driver.find_element("id", "searchAuctno")
auction_options = select_element.find_elements(By.TAG_NAME, "option")

url_parts = urlparse(driver.current_url)
query_params = parse_qs(url_parts.query)  # Parse query parameters

# Check if 'atn' parameter exists in the URL
if 'atn' in query_params:
    start_atn = int(query_params['atn'][0])  # Get the starting 'atn' value
else:
    raise ValueError("The 'atn' parameter is missing from the URL.")
for option in range(len(auction_options)):
    # Select the option by clicking on it
    current_atn = start_atn + option  # Increment `atn` by one on each iteration
    print(current_atn, "current_atn")
    query_params['atn'] = [str(current_atn)]  # Update 'atn' parameter in query
    
    # Reconstruct the URL with the updated query parameters
    new_query = urlencode(query_params, doseq=True)
    new_url = urlunparse((url_parts.scheme, url_parts.netloc, url_parts.path, url_parts.params, new_query, url_parts.fragment))
    
    # Navigate to the new URL
    driver.get(new_url)
    print("Navigated to URL:", driver.current_url)
    time.sleep(3) 
    try:
        last_page_button = driver.find_element("xpath", '//button[contains(@class, "paging-last")]')
        total_pages = int(last_page_button.get_attribute('onclick').split('fnPaging(')[1].split(')')[0])
        print(total_pages, "total_pages")
    except Exception as e:
        print("Could not determine the total number of pages. Exiting...", e)
        driver.quit()
        raise e

    # Loop through each page
    for page in range(1, total_pages + 1):  # Adjust this range as needed
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
                        cur.execute("SELECT vin_number FROM cars WHERE vin_number = %s", (chassis_number,))
                        print(chassis_number,'----chasis')
                        car_exists = cur.fetchone()
                        print(car_exists, '----car_exists')
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
                            style = img_tag.get('style')
                            if img_url and img_url not in seen_urls and (not style or 'display: none' not in style):
                                seen_urls.add(img_url)
                                unique_img_tags.append(img_url)
                    data = {}
                    car_name = None
                    manufacturer = None
                    car_name_tag = detail_soup.find('div', class_='head-box').find('h2', class_='car-name')
                    if car_name_tag:
                        car_name = translate_text(car_name_tag.text.strip(), src='ko', dest='en')
                        print(f"Original Car Name: {car_name}")
                        manufacturer, cleaned_car_name = extract_manufacturer_and_clean_name(car_name)
                     
                    # Extract the auction date and time  
                    date_element = detail_soup.find('div', class_='date-set').find('span', class_='date')
                    date_text = date_element.text.strip()
                    cleaned_date_text = re.sub(r'\s*\(.*?\)\s*', ' ', date_text)  # Remove text within parentheses
                    date_obj = datetime.strptime(cleaned_date_text, "%y/%m/%d %H:%M")
                    print("Parsed Date and Time:", date_obj)
                    
                    # Extract the car price
                    car_price = None
                    price_tag = detail_soup.find('div', class_='price-box').find('strong', class_='point')
                    if price_tag:
                        car_price = translate_text(price_tag.text.strip().replace(',',''), src='ko', dest='en')
                        print(f"Car Price: {car_price} 만원")

                    # Now add car name and price to the data dictionary
                    data['Car Name'] = cleaned_car_name
                    data['Auction Date'] = date_obj
                    data['Manufacturer'] = manufacturer
                    data['Car Price'] = car_price
                    index = 0
                    data_labels = [ 
                        # 'Product type',
                        'Fuel Type',
                        'Engine Displacement',
                        'Seating Capacity',
                        # 'Purpose',
                        'Engine Model',
                        # 'Warranty',
                        # 'Last Regular Inspection',
                        'License Plate Number',
                        'Model Year',
                        # 'First Registration Date',
                        'Mileage',
                        'Color',
                        # 'Transmission',
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
                                if dt_text == '완비서류' or dt_text == '차대번호' or dt_text == '미비서류':
                                    continue
                                if dt_text =='차량번호':
                                    license_plate_span = dd.find('span', id='h_carno')
                                    if license_plate_span:
                                        value = license_plate_span.text.strip()
                                    else:
                                        value = dd.text.strip()  
                                elif dt_text == '인승':  
                                    seating_capacity_text = dd.text.strip()
                                    seating_capacity = ''.join(filter(str.isdigit, seating_capacity_text))
                                    value = seating_capacity
                                elif dt_text == '연식':  # 'Model Year'
                                    model_year_text = dd.text.strip()
                                    model_year = ''.join(filter(str.isdigit, model_year_text))
                                    value = model_year
                                elif dt_text == '주행거리':  # 'Mileage'
                                    mileage_text = dd.text.strip()
                                    # Remove commas and non-numeric characters (like 'km') from mileage
                                    mileage = ''.join(filter(str.isdigit, mileage_text))
                                    value = mileage
                                elif dt_text == '배기량':  # 'Engine Displacement'
                                    engine_displacement_text = dd.text.strip()
                                    engine_displacement = ''.join(filter(str.isdigit, engine_displacement_text))
                                    value = engine_displacement
                                elif dt_text == '정기검사일': 
                                    continue
                                elif dt_text == '최초등록일': 
                                    continue
                                elif dt_text == '상품구분': 
                                    continue
                                elif dt_text == '용도/구분': 
                                    continue
                                elif dt_text == '보관품': 
                                    continue
                                elif dt_text == '변속기': 
                                    continue
                                else:   
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
                    print(data.get('Last Regular Inspection'), '----date')
                    print(data.get('First Registration Date'), '----date2')
                    try:
                        cur.execute("""
                        INSERT INTO cars (
                            vin_number, name, status, fuel_type, engine_displacement, seating_capacity, 
                            engine_model, starting_price, license_plate_number, model_year, mileage, color, seat_number, manufacturer, image_url, created_by, created_date, updated_by, updated_date, auction_date
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) RETURNING id;
                        """, (
                        chassis_number,
                        data['Car Name'],
                        1,
                        data.get('Fuel Type'),
                        data.get('Engine Displacement'),
                        data.get('Seating Capacity'),
                        data.get('Engine Model'),
                        data.get('Car Price'),
                        data.get('License Plate Number'),
                        data.get('Model Year'),
                        data.get('Mileage'),
                        data.get('Color'),
                        data.get('Seat Number'),
                        data.get('Manufacturer'),
                        main_image_url,
                        1,
                        datetime.now(),
                        1,
                        datetime.now(),
                        data.get('Auction Date')
                    ))
                        
                        # Insert data into CarImages table
                        data['Main Image'] = main_image_url
                        car_id = cur.fetchone()[0]
                        print(f"Car inserted with ID: {car_id}")
                        cur.execute("SELECT * FROM cars WHERE id = %s", (car_id,))
                        car = cur.fetchone()
                        connection.commit()
                        if car:
                            print(f"Car exists in table with ID: {car_id}")
                        else:
                            print(f"Car not found in table with ID: {car_id}")
                    
                        # Insert data into CarImages table using the auto-incremented car_id
                        car_images_values = [(car_id, img_url, 1, 1, datetime.now(), 1, datetime.now()) for img_url in unique_img_tags]
                        car_detail_data.append({'car':data, 'images':car_images_values})

                        # Use execute_values to insert all images related to this car
                        execute_values(cur, """
                            INSERT INTO car_images (car_id, name, status, created_by, created_date, updated_by, updated_date) 
                            VALUES %s;
                        """, car_images_values)
                        connection.commit()
                    except Exception as inst:
                        print(inst, '---eroor')
                        connection.rollback()

                    # Go back to the main list page
                    driver.back()
                    time.sleep(3)
        print(f"Page {page} extracted successfully.")

        # Navigate to the next page
        # Print the current page URL
        driver.get(new_url)
        time.sleep(8)
        print("Current page URL:", driver.current_url)
       
        if page < total_pages:
            next_page_button = driver.find_element("xpath", f'//button[@onclick="fnPaging({page + 1})"]')
            next_page_button.click()
            time.sleep(5)
              

driver.quit()
connection.commit()
cur.close()
connection.close()

# Save the extracted data to a JSON file
with open('car_detail_data.json', 'w', encoding='utf-8') as detail_json_file:
    json.dump(car_detail_data, detail_json_file, ensure_ascii=False, indent=4, default=json_serial)

print("Data saved to car_detail_data.json")
