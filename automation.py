import time
import pyautogui
import pyperclip
from pywinauto.application import Application
import pygetwindow as gw

def start_application():
    """Start the desktop application."""
    app_path = r"C:\Program Files (x86)\HyndaiGlovis\AutobellSmartAuction\AuctionPcApplication.exe"
    app = Application().start(app_path)
    return app

def wait_for_chrome_window(timeout=30):
    """Wait for a Chrome window to appear."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        windows = gw.getWindowsWithTitle('Google Chrome')
        if windows:
            return windows[0]
        time.sleep(0.3)
    return None

def get_current_url(chrome_window):
    """Get the current URL from the active Chrome window."""
    chrome_window.activate()
    time.sleep(2.5)

    pyautogui.hotkey('ctrl', 'l')  # Focus the URL bar
    time.sleep(0.2)
    pyautogui.hotkey('ctrl', 'c')  # Copy the URL
    time.sleep(0.7)
    url = pyperclip.paste()        # Retrieve the copied URL
    return url

def login_to_application():
    """Log in to the application."""
    # Input username
    pyautogui.moveTo(770, 466, duration=0.2)
    pyautogui.click()
    pyautogui.typewrite("9418")

    # Input password
    pyautogui.moveTo(770, 532, duration=0.2)
    pyautogui.click()
    pyautogui.typewrite("kaew2001!")

    # Click login button
    pyautogui.moveTo(960, 670, duration=0.2)
    pyautogui.click()

def navigate_to_web_view():
    """Navigate to the web view within the application."""
    time.sleep(6)
    pyautogui.moveTo(1100, 900, duration=0.2)
    pyautogui.click()
    time.sleep(5)
    pyautogui.moveTo(1100, 900, duration=0.2)
    pyautogui.click()
    time.sleep(4)
    pyautogui.moveTo(590, 85, duration=0.2)
    pyautogui.click()

def close_application(app, chrome_window):
    """Minimize Chrome and close the application."""
    try:
        # Minimize the Chrome window
        time.sleep(2)
        chrome_window.minimize()
        time.sleep(1)  # Wait for Chrome to minimize
        
        # Send Alt+F4 to close the active application window
        pyautogui.hotkey('alt', 'f4')
        time.sleep(2)  # Wait for the popup to appear
        
        # Click the "확인" (Confirm) button on the confirmation popup
        pyautogui.moveTo(920, 585, duration=0.2)  # Adjust these coordinates as necessary
        pyautogui.click()

    except Exception as e:
        print(f"Failed to close the application: {e}")

def main():
    """Main function to execute the workflow."""
    app = start_application()
    time.sleep(5)  # Wait for the application to start

    login_to_application()

    navigate_to_web_view()

    chrome_window = wait_for_chrome_window(timeout=30)
    if chrome_window:
        url = get_current_url(chrome_window)
        if url:
            print(f"Scraping URL: {url}")
            # Optionally, save the URL to a file
            with open('url.txt', 'w') as file:
                file.write(url)
        else:
            print("Failed to extract URL.")
    else:
        print("Chrome window did not appear within the timeout.")

    # Close the application after saving the URL
    close_application(app, chrome_window)

if __name__ == '__main__':
    main()
