from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
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

# Loop through each page
while True:
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    list_section = soup.find_all('div', class_="item")

    if not list_section:
        print("No items found")
    else:
        for item in list_section:
            car_name = item.find('span', class_='car-name')
            if car_name:
                car_name = car_name.text.strip()
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
                options['Transmission'] = car_details[1].text.strip()
                options['Engine Size'] = car_details[2].text.strip()
                options['Mileage'] = car_details[3].text.strip().replace("\n", "").strip()
                options['Color'] = car_details[4].text.strip().replace("\n", "").strip()
                options['Fuel Type'] = car_details[5].text.strip()
                options['Usage Type'] = car_details[6].text.strip()
                options['Model'] = car_details[7].text.strip()

            car_data.append({'Name': car_name, 'Price': car_price, 'Image': car_image, "Options:": options})

    # Check if a "Next" button is present
    try:
        next_button = driver.find_element("xpath", '//button[contains(@class, "paging-next")]')
        if "disabled" in next_button.get_attribute("class"):
            break  # Exit loop if the "Next" button is disabled (no more pages)
        else:
            next_button.click()  # Click on the "Next" button
            time.sleep(3)  # Wait for the next page to load
    except:
        break  # Exit loop if the "Next" button is not found (no more pages)

driver.quit()

# Convert the data to a DataFrame and save it to a JSON file
df = pd.DataFrame(car_data)
json_data = df.to_dict(orient='records')

with open('car_data.json', 'w', encoding='utf-8') as json_file:
    json.dump(json_data, json_file, ensure_ascii=False, indent=4)

print("Data saved to car_data.json")
