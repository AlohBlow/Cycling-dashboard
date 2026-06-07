"""
Runs build_dashboard.py twice daily (06:00 and 18:00 local time).
Keep this process running in the background, or use Task Scheduler / cron instead.
"""

import logging
import schedule
import time
from build_dashboard import run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

schedule.every().day.at("06:00").do(run)
schedule.every().day.at("18:00").do(run)

print("Scheduler running. Press Ctrl+C to stop.")
print("Next runs: 06:00 and 18:00 daily.")

# Run once immediately on startup
run()

while True:
    schedule.run_pending()
    time.sleep(30)
