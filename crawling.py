from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from googletrans import Translator
import pandas as pd
import json
import time

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

# Initialize the translator
translator = Translator()

# Get the total number of pages from the "Last" button
try:
    last_page_button = driver.find_element("xpath", '//button[contains(@class, "paging-last")]')
    total_pages = int(last_page_button.get_attribute('onclick').split('fnPaging(')[1].split(')')[0])
except Exception as e:
    print("Could not determine the total number of pages. Exiting...")
    driver.quit()
    raise e

# Loop through each page
for page in range(1, total_pages + 1):
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    list_section = soup.find_all('div', class_="item")

    if not list_section:
        print("No items found")
    else:
        for item in list_section:
            car_name = item.find('span', class_='car-name')
            if car_name:
                car_name = translator.translate(car_name.text.strip(), src='ko', dest='en').text
            car_price = item.find('span', class_='num')
            if car_price:
                car_price = car_price.text.strip()
            car_image_tag = item.find('img')
            if car_image_tag and 'src' in car_image_tag.attrs:
                car_image = car_image_tag['src']
            else:
                car_image = None
            option_section = item.find('div', class_='option')

            options = {}
            if option_section:
                car_details = option_section.find_all('span')

            if len(car_details) >= 8:  # Ensure there are enough elements
                options['Year'] = car_details[0].text.strip()
                options['Transmission'] = translator.translate(car_details[1].text.strip(), src='ko', dest='en').text
                options['Engine Size'] = car_details[2].text.strip()
                options['Mileage'] = car_details[3].text.strip().replace("\n", "").strip()
                options['Color'] = translator.translate(car_details[4].text.strip().replace("\n", "").strip(), src='ko', dest='en').text
                options['Fuel Type'] = translator.translate(car_details[5].text.strip(), src='ko', dest='en').text
                options['Usage Type'] = translator.translate(car_details[6].text.strip(), src='ko', dest='en').text
                options['Model'] = translator.translate(car_details[7].text.strip(), src='ko', dest='en').text

            # Extract the detail URL
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

                # Extract data from the detail page
                detail_data = {
                    'Name': car_name,
                    'Price': car_price,
                    'Image': car_image,
                    'Options': options,
                    'DetailURL': detail_url
                }

                # Extract specific details from the detail page (example)
                car_name = translator.translate(detail_soup.find('h2', class_='car-name').text.strip(), src='ko', dest='en').text
                # Extract car price and other main details
                price_info = detail_soup.find('div', class_='spec-detail').find_all('span', class_='price')
                initial_price = price_info[0].text.strip() if len(price_info) > 0 else None
                estimated_price = price_info[1].text.strip() if len(price_info) > 1 else None

                # Extract car information
                car_info_section = detail_soup.find('div', class_='new-car-info').find_all('span')
                car_info = {
                    "Registration Date": car_info_section[0].text.strip() if len(car_info_section) > 0 else None,
                    "Mileage": car_info_section[1].text.strip() if len(car_info_section) > 1 else None,
                    "Transmission": translator.translate(car_info_section[2].text.strip(), src='ko', dest='en').text if len(car_info_section) > 2 else None,
                    "Color": translator.translate(car_info_section[3].text.strip(), src='ko', dest='en').text if len(car_info_section) > 3 else None,
                }

                car_detail_data.append({
                    'Name': car_name,
                    'Initial Price': initial_price,
                    'Estimated Price': estimated_price,
                    'Car Info': car_info
                })

                # Go back to the main list page
                driver.back()
                time.sleep(3)

            car_data.append({'Name': car_name, 'Price': car_price, 'Image': car_image, "Options": options})
            break
    # If it's not the last page, click the "Next" button
    break
    if page < total_pages:
        next_page_button = driver.find_element("xpath", f'//button[@onclick="fnPaging({page + 1})"]')
        next_page_button.click()
        time.sleep(3)  # Wait for the next page to load

driver.quit()

# Save the list page data to a JSON file
df = pd.DataFrame(car_data)
json_data = df.to_dict(orient='records')
with open('car_data.json', 'w', encoding='utf-8') as json_file:
    json.dump(json_data, json_file, ensure_ascii=False, indent=4)

# Save the detailed car data to another JSON file
with open('car_detail_data.json', 'w', encoding='utf-8') as detail_json_file:
    json.dump(car_detail_data, detail_json_file, ensure_ascii=False, indent=4)

print("Data saved to car_data.json and car_detail_data.json")
