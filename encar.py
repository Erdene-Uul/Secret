import requests
import json
import time
import random

# ===================== CONFIG =====================
API_URL = "https://api.encar.com/search/car/list/general"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.encar.com",
    "Referer": "https://www.encar.com/",
}

# Hyundai (현대) – network дээрээс авсан q
Q = "(And.Hidden.N._.(C.CarType.Y._.Manufacturer.현대.))"

SORT = "ModifiedDate"
PAGE_SIZE = 20
SLEEP_RANGE = (0.6, 1.2)

OUT_FILE = "encar_list.json"
# ==================================================


def sleep():
    time.sleep(random.uniform(*SLEEP_RANGE))


def fetch_page(offset: int, size: int):
    """
    Нэг page list татна
    """
    params = {
        "count": "true",
        "q": Q,
        "sr": f"|{SORT}|{offset}|{size}",
        "inav": "|Metadata|Sort",
    }

    r = requests.get(API_URL, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def main():
    all_cars = []
    page = 1
    total = None

    
    for page in range(1, 10 + 1):
        offset = (page - 1) * PAGE_SIZE
        print(f"[INFO] Fetch page={page}, offset={offset}")

        data = fetch_page(offset, PAGE_SIZE)
        cars = data.get("SearchResults", [])

        if not cars:
            print("[INFO] No results, stop.")
            break

        all_cars.extend(cars)
        print(f"[INFO] Page {page} -> {len(cars)} items (total: {len(all_cars)})")

        sleep()

    # Save JSON
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_cars, f, ensure_ascii=False, indent=2)

    print(f"[DONE] Saved {len(all_cars)} cars to {OUT_FILE}")


if __name__ == "__main__":
    main()
