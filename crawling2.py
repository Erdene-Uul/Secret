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

# Database connection
connection = psycopg2.connect(
        dbname="postgres",
        user="admin",
        password="socar", 
        host="18.167.136.248",
        port="5432"
    )
cur = connection.cursor()

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
        try:
            # Wait for the modal to appear
            modal = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "renewal_tax"))
            )
            print("Modal detected. Waiting for '닫기' button...")

            # Find the '닫기' button inside the modal
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn') and contains(text(), '닫기')]"))
            )

            # Use JavaScript to click the button to avoid interception
            driver.execute_script("arguments[0].click();", close_button)
            print("Closed the modal using JavaScript.")

            # Wait for the modal to disappear completely
            WebDriverWait(driver, 5).until(
                EC.invisibility_of_element_located((By.ID, "renewal_tax"))
            )
            print("Modal has disappeared.")

        except Exception as e:
            print(f"No modal detected or issue in closing it: {e}")

        # Now click on '전체' section
        try:
            first_div = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@class='link text-center']/a"))
            )
            print("Located the '전체' section.")

            # Scroll into view and click
            driver.execute_script("arguments[0].scrollIntoView();", first_div)
            driver.execute_script("arguments[0].click();", first_div)  # Using JS to avoid interception
            print("Clicked on '전체' section.")

        except Exception as e:
            print(f"Error clicking '전체': {e}")


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
                    car_details = {}
                    cars = WebDriverWait(driver, 10).until(
                        EC.presence_of_all_elements_located((By.CLASS_NAME, "car_one"))
                    )
                    car = cars[i]
                    try:
                        eval_score_element = car.find_element(By.XPATH, ".//strong[contains(text(),'평가점')]/parent::div")
                        eval_score = eval_score_element.text.strip()
                        print(f"평가점 (Evaluation Score): {eval_score}")
                        car_details["평가점"] = eval_score
                    except Exception as e:
                        print(f"평가점 not found for car {i + 1}: {e}")
                        car_details["평가점"] = None

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
                    # Extract Car Title Without Auction Number
                    try:
                        title_element = detail_soup.find("h2", class_="tit_style2")
                        if title_element:
                            car_title_raw = title_element.text.strip()
                            car_title_clean = re.sub(r"^\[\d+\]\s*", "", car_title_raw)  # Remove "[1001] "
                            car_details["car_name_kor"] = car_title_clean
                            print(f"Full Car Title: {car_title_clean}")

                            # Extract Manufacturer (First Word)
                            title_parts = car_title_clean.split()
                            manufacturer = title_parts[0] if title_parts else None
                            car_title_without_manufacturer = " ".join(title_parts[1:])  # Remove first word

                            print(f"Manufacturer: {manufacturer}")
                            print(f"Car Title Without Manufacturer: {car_title_without_manufacturer}")

                            # Save car_details
                            car_details["manufacturer"] = translate_text(manufacturer, src='ko', dest='en')
                            car_details["title"] = translate_text(car_title_without_manufacturer, src='ko', dest='en')
                        else:
                            print("Car title not found.")
                            car_details["title"] = None
                            car_details["manufacturer"] = None
                    except Exception as e:
                        print(f"Error extracting car title and manufacturer: {e}")

                    # Extract Start Price Without "만원"
                    try:
                        price_element = detail_soup.find("strong", class_="i_comm_main_txt2")
                        if price_element:
                            start_price = price_element.text.strip().replace(",", "")  # Remove commas
                            print(f"Start Price: {start_price} (in 10,000 KRW units)")
                            car_details["start_price"] = int(start_price)  # Convert to integer
                        else:
                            print("Start price not found.")
                            car_details["start_price"] = None
                    except Exception as e:
                        print(f"Error extracting start price: {e}")

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
                    
                    # Extract specific details from the car detail page
                    try:
                        for li in car_details_div.find_all("li"):
                            label_kr = li.find("span").text.strip() if li.find("span") else "Unknown"
                            value_kr = li.find("strong").text.strip() if li.find("strong") else "Unknown"

                            if label_kr == "차대번호":  # VIN Number
                                car_details["vin_number"] = value_kr
                                print(f"차대번호 (VIN): {value_kr}")

                            elif label_kr == "연식":  # Year (Only the year, remove extra text)
                                year_match = re.search(r"\d{4}", value_kr)
                                if year_match:
                                    car_details["year"] = year_match.group(0)
                                    print(f"연식 (Year): {car_details['year']}")

                            elif label_kr == "연료":  # Fuel Type
                                car_details["fuel_type"] = translate_text(value_kr, src='ko', dest='en')
                                print(f"연료 (Fuel): {value_kr}")

                            elif label_kr == "주행거리":  # Mileage (Remove `Km`)
                                mileage_clean = re.sub(r"[^\d]", "", value_kr)  # Remove non-numeric characters
                                car_details["mileage"] = mileage_clean
                                print(f"주행거리 (Mileage): {mileage_clean} Km")

                            elif label_kr == "배기량":  # Engine Capacity
                                car_details["engine_capacity"] = value_kr
                                print(f"배기량 (Engine Capacity): {value_kr}")

                            elif label_kr == "색상":  # Color (Only the color name)
                                color_match = re.search(r"[\w가-힣]+", value_kr)
                                car_details["color"] = translate_text(color_match.group(0) if color_match else None, src='ko', dest='en') 
                                print(f"색상 (Color): {car_details['color']}")

                    except Exception as e:
                        print(f"Error extracting car details: {e}")


                    print("Car Details:")
                    for key, value in car_details.items():
                        print(f"{key}: {value}")
                    try:
                        cur.execute("""
                        INSERT INTO cars (
                            vin_number, name, status, fuel_type, engine_displacement,
                            engine_model, starting_price, model_year, mileage, color, manufacturer, image_url, created_by, created_date, updated_by, updated_date, auction_date, name_korean
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) RETURNING id;
                        """, (
                        car_details['vin_number'],
                        car_details['title'],
                        1,
                        car_details.get('fuel_type'),
                        car_details.get('engine_capacity'),
                        car_details.get('engine'),
                        car_details.get('start_price'),
                        car_details.get('year'),
                        car_details.get('milage'),
                        car_details.get('color'),
                        car_details.get('manufacturer'),
                        main_img_url,
                        1,
                        datetime.now(),
                        1,
                        datetime.now(),
                        car_details.get('Auction Date'),
                        car_details.get('Car Name Korean')
                    ))
                        
                        # Insert car_details into CarImages table
                        car_details['Main Image'] = main_img_url
                        car_id = cur.fetchone()[0]
                        print(f"Car inserted with ID: {car_id}")
                        cur.execute("SELECT * FROM cars WHERE id = %s", (car_id,))
                        car = cur.fetchone()
                        connection.commit()
                        if car:
                            print(f"Car exists in table with ID: {car_id}")
                        else:
                            print(f"Car not found in table with ID: {car_id}")
                    
                        # Insert car_details into CarImages table using the auto-incremented car_id
                        car_images_values = [(car_id, img_name, 1, 1, datetime.now(), 1, datetime.now()) for img_name in unique_img_tags]
                        car_detail_data.append({'car':car_details, 'images':car_images_values})

                        # Use execute_values to insert all images related to this car
                        execute_values(cur, """
                            INSERT INTO car_images (car_id, name, status, created_by, created_date, updated_by, updated_date) 
                            VALUES %s;
                        """, car_images_values)
                        connection.commit()
                    except Exception as inst:
                        print(inst, '---eroor')
                        connection.rollback()
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
