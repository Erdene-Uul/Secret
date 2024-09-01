import schedule
import time
import subprocess

def run_automation():
    """Run the automation.py script."""
    print("Starting automation.py...")
    try:
        subprocess.run(["python", "automation.py"], check=True)
        print("Finished automation.py")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running automation.py: {e}")

def run_crawling():
    """Run the crawling.py script."""
    print("Starting crawling.py...")
    try:
        subprocess.run(["python", "crawling.py"], check=True)
        print("Finished crawling.py")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running crawling.py: {e}")

def main():
    """Main function to set up the schedule."""
    # Schedule automation.py to run at 58 minutes past every hour
    schedule.every().hour.at(":58").do(run_automation)
    run_automation
    
    # Schedule crawling.py to run at 2 minutes past every hour
    schedule.every().hour.at(":02").do(run_crawling)
    
    print("Scheduler started. Running automation.py at 58 min of every hour and crawling.py at 2 min of every hour...")
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
