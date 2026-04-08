import httpx

Q = "(And.(And.Hidden.N._.(C.CarType.Y._.(C.Manufacturer.현대._.ModelGroup.아반떼.)))_.AdType.B.)"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Origin": "https://www.encar.com",
    "Referer": "https://www.encar.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
}

def fetch_premium(page: int = 1, size: int = 20):
    params = {
        "count": "true",
        "q": Q,                   # httpx will percent-encode it
        "from": (page - 1) * size,
        "size": size,
        "sr": "|ModifiedDate|"    # keep sort key; paging controlled by from/size
    }
    with httpx.Client(http2=True, trust_env=False, headers=HEADERS, timeout=20) as c:
        r = c.get("https://api.encar.com/search/car/list/premium", params=params)
        r.raise_for_status()
        return r.json()

if __name__ == "__main__":
    data = fetch_premium(page=3, size=20)  # ← 3rd page, 20 results
    print("Total:", data["Count"], "Page items:", len(data.get("SearchResults", [])))
    # quick peek at first item
    if data.get("SearchResults"):
        first = data["SearchResults"][0]
        print(first["Id"], first["Manufacturer"], first["Model"], first["Price"])
