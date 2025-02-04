import logging
import psycopg2
from psycopg2.extras import execute_values
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
from googletrans import Translator
from datetime import datetime
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BRAND_NAME_MAP = {
    "현대": "Hyundai",
    "벤츠": "Mercedes",
}

FUEL_TYPE_MAP = {
    "휘발유": "Бензин",
    "경유": "Дизель",
    "LPG": "Газ",
    "겸용": "Хосолсон",
    "하이브리드": "Хайбрид",
    "CNG": "CNG",
    "전기": "Цахилгаан",
    "수소": "Ус төрөгчийн түлш",
}
def translate_text(text, src='ko', dest='en'):
    if isinstance(text, datetime) or text is None:
        return text  # Return as-is if it's datetime or None
    
    # Check for predefined mappings
    if text in FUEL_TYPE_MAP:
        return FUEL_TYPE_MAP[text]
    if text in BRAND_NAME_MAP:
        return BRAND_NAME_MAP[text]

    try:
        # Initialize the translator
        translator = Translator()
        translated = translator.translate(text, src=src, dest=dest)
        return translated.text  # Access .text on the translation result
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
driver.maximize_window()

# Navigate to the URL
url = "https://saa.co.kr/newfront/login.do"
car_list_url = "https://saa.co.kr/newfront/receive/rc/receive_rc_list.do"
driver.get(url)

# Wait for the page to load
time.sleep(3)

try:
    driver.find_element(By.ID, "i_sUserId").send_keys("711201")
    driver.find_element(By.ID, "i_sPswd").send_keys("2580")
    # Locate the login button by its class
    login_button = driver.find_element(By.XPATH, "//a[contains(@class, 'login_full_btn')]")


    
    if login_button is not None:
        # Click the login button
        login_button.click()
        print("Login button clicked.")
        time.sleep(2)
        first_div = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//div[@class='link text-center']/a")))
        print("Located the '전체' section.")

        # Scroll into view and click
        driver.execute_script("arguments[0].scrollIntoView();", first_div)
        first_div.click()
        print("Clicked on '전체' section.")
        time.sleep(2)
        span_element = BeautifulSoup(driver.page_source, 'html.parser').find('span', class_="i_comm_main_txt")
        print(span_element, '=========span')
        # Extract the text from the span
        full_text = span_element.text.strip()
        print(f"Full Text: {full_text}")
        date_match = re.search(r"\d{4}/\d{2}/\d{2}", full_text)
        if date_match:
            extracted_date = date_match.group(0)
            original_date = datetime.strptime(extracted_date, "%Y/%m/%d")
            # Add time part to the adjusted date and format it
            formatted_date = original_date.strftime("%Y-%m-%d 17:00:00.000")

            print(f"Original Date: {extracted_date}")
            print(f"Converted Date: {formatted_date}")
        else:
            print("Date not found in the span text.")
        while True:
            # Get all cars on the current page
            cars = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "car_one"))
            )
            print(f"Found {len(cars)} cars on this page.")
            for i in range(len(cars)):
                try:
                    cars = WebDriverWait(driver, 10).until(
                        EC.presence_of_all_elements_located((By.CLASS_NAME, "car_one"))
                    )
                    car = cars[i]

                            # Locate either the car image or car title link
                    car_image = car.find_element(By.XPATH, ".//div[@class='car-image']/a")
                    car_title = car.find_element(By.XPATH, ".//div[@class='car-title']/a")

                    # Click on the car image or title (image is prioritized)
                    if car_image:
                        car_image.click()
                        print(f"Clicked on car image for car {i + 1}.")
                    elif car_title:
                        car_title.click()
                        print(f"Clicked on car title for car {i + 1}.")
                    else:
                        print(f"No clickable element found for car {i + 1}.")
                        continue
                    print(f"Clicked on car {i + 1}.")
                    
                    # Wait for the car details page to load
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "details-block"))
                    )

                    # Verify that the page has navigated
                    print("Current Path:", driver.current_url)

                    # Extract car details
                    detail_soup = BeautifulSoup(driver.page_source, 'html.parser')
                    car_details_div = detail_soup.find('div', class_="details-block")
                    if not car_details_div:
                        raise Exception("Details block not found on the page.")
                    # Find all image URLs
                    images = detail_soup.find_all("img", class_="img-fluid")
                    image_urls = [img["src"] for img in images if "src" in img.attrs]

                    print("Image URLs:")
                    for url in image_urls:
                        print(url)
                    # Parse and print car details
                    car_details = {}
                    for li in car_details_div.find_all("li"):
                        label_kr = li.find("span").text.strip() if li.find("span") else "Unknown"
                        value_kr = li.find("strong").text.strip() if li.find("strong") else "Unknown"
                        print(label_kr)
                        print(value_kr)
                        if isinstance(label_kr, str):
                         label = translate_text(label_kr, src='ko', dest='en')
                        else:
                            label = label_kr

                        if isinstance(value_kr, str):
                            value = translate_text(value_kr, src='ko', dest='en')
                        else:
                            value = value_kr
                        car_details[label] = value

                    print("Car Details:")
                    for key, value in car_details.items():
                        print(f"{key}: {value}")

                    # Navigate back to the car list
                    driver.back()
                    time.sleep(2)
                except Exception as e:
                    print(f"Error processing car {i + 1}: {e}")
                    continue

            # Check for the "Next" button and click it
            try:
                next_button = driver.find_element(By.XPATH, "//a[contains(text(), '>')]")
                next_button.click()
                print("Navigated to next page.")
                time.sleep(2)
            except Exception as e:
                print("No more pages to navigate.")
                break

    else:
        print("Login button not found.")


except Exception as e:
    print(f"An error occurred: {e}")

# Close the driver after execution
driver.quit()
