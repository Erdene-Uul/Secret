import boto3
import psycopg2
from psycopg2.extras import execute_values
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json
import time
from googletrans import Translator
import requests
from io import BytesIO
from PIL import Image

# AWS S3 Configuration
s3 = boto3.client('s3', 
                  aws_access_key_id='YOUR_AWS_ACCESS_KEY', 
                  aws_secret_access_key='YOUR_AWS_SECRET_KEY',
                  region_name='YOUR_AWS_REGION')

bucket_name = 'your-s3-bucket-name'

# Database connection
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
                    for img_tag in img_tags:
                        if 'src' in img_tag.attrs:
                            image_urls.append(img_tag['src'])

                data = {}
                table_section = detail_soup.find('div', class_='info-box')
                if table_section:
                    dl_elements = table_section.find_all('dl')
                    for dl in dl_elements:
                        dt_elements = dl.find_all('dt')
                        dd_elements = dl.find_all('dd')
                        
                        for dt, dd in zip(dt_elements, dd_elements):
                            label = dt.text.strip()
                            value = dd.text.strip()
                            translated_label = translator.translate(label, src='ko', dest='en').text
                            translated_value = translator.translate(value, src='ko', dest='en').text
                            data[translated_label] = translated_value

                status_box = detail_soup.find('div', class_='status-box')
                main_image_url = None
                if status_box:
                    img_tag = status_box.find('div', class_='img-box').find('img')
                    main_image_url = img_tag['src'] if img_tag else None

                # Process and upload the main image to S3
                if main_image_url:
                    try:
                        response = requests.get(main_image_url)
                        img = Image.open(BytesIO(response.content))
                        main_image_name = f"{chassis_number}_main_{main_image_url.split('/')[-1]}"
                        main_image_name = main_image_name.replace("?", "_").replace("&", "_").replace("=", "_")  # Sanitize filename
                        
                        # Save the main image to S3
                        img_buffer = BytesIO()
                        img.save(img_buffer, img.format)
                        img_buffer.seek(0)
                        
                        s3.upload_fileobj(img_buffer, bucket_name, main_image_name)
                    except Exception as e:
                        print(f"Failed to process or upload main image: {main_image_url}, error: {e}")
                        main_image_name = None
                else:
                    main_image_name = None

                # Insert data into Cars table
                cur.execute("""
                    INSERT INTO Cars (
                        CarId, ImageUrl, ProductClassification, Fuel, Displacement, Salvation, 
                        UseDistinction, Primitives, Storage, Periodic, CompleteDocuments, 
                        CarNumber, Year, InitialRegistrationDate, Mileage, Color, Transmission, SeatNumber, Insufficiency
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    );
                """, (
                    chassis_number,
                    main_image_name,  # Save the main image name in the database
                    data.get('Product classification'),
                    data.get('fuel'),
                    data.get('Displacement'),
                    data.get('Salvation'),
                    data.get('Use/distinction'),
                    data.get('Primitives'),
                    data.get('Storage'),
                    data.get('Periodic'),
                    data.get('Complete documents'),
                    data.get('Car number'),
                    int(data.get('Year', '0').split()[1]) if 'Year' in data else None,
                    data.get('Initial registration date'),
                    int(data.get('Mileage', '0').replace(',', '').replace('km', '')) if 'Mileage' in data else None,
                    data.get('color'),
                    data.get('Transmission'),
                    data.get('Seat number'),
                    data.get('Insufficiency')
                ))

                # Process and upload additional images to S3
                car_images_values = []
                for img_url in image_urls:
                    try:
                        response = requests.get(img_url)
                        img = Image.open(BytesIO(response.content))
                        img_name = f"{chassis_number}_{img_url.split('/')[-1]}"
                        img_name = img_name.replace("?", "_").replace("&", "_").replace("=", "_")  # Sanitize filename
                        
                        # Save the image to S3
                        img_buffer = BytesIO()
                        img.save(img_buffer, img.format)
                        img_buffer.seek(0)
                        
                        s3.upload_fileobj(img_buffer, bucket_name, img_name)
                        
                        car_images_values.append((chassis_number, img_name))
                    except Exception as e:
                        print(f"Failed to process or upload image: {img_url}, error: {e}")

                # Insert data into CarImages table
                if car_images_values:
                    execute_values(cur, """
                        INSERT INTO CarImages (CarId, ImageUrl) 
                        VALUES %s;
                    """, car_images_values)

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
with open('car_detail_data.json', 'w', encoding='utf-8') as detail_json_file, open('car_images.json', 'w', encoding='utf-8') as image_json_file:
    json.dump(car_detail_data, detail_json_file, ensure_ascii=False, indent=4)

print("Data saved to car_detail_data.json and car_images.json")
