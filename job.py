import schedule
import time
import subprocess

def run_scripts():
    """Run the Python scripts."""
    print("Starting scripts...")
    try:
        subprocess.run(["python", "automation.py"], check=True)
        print('Finished automation.py')
        subprocess.run(["python", "crawling.py"], check=True)
        print("Finished crawling.py")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running the scripts: {e}")
    print("Scripts finished.")

def main():
    """Main function to set up the schedule."""
    # Schedule the job to run every hour
    schedule.every().second.do(run_scripts)
    
    print("Scheduler started. Running scripts every hour...")
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
