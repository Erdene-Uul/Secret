import math
from typing import Any, Dict, List, Optional

IMG_BASE = "https://ci.encar.com"  # зураг ихэвчлэн эндээс явдаг (шаардлагатай бол cdn өөр байж болно)

def safe_int(x) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(float(x))
    except Exception:
        return None

def parse_year_month(year_float) -> Dict[str, Optional[int]]:
    """
    Encar-ын Year: 201707.0 гэх мэт ирдэг.
    -> year=2017, month=7
    """
    y = safe_int(year_float)
    if not y:
        return {"year": None, "month": None}
    year = y // 100
    month = y % 100
    if month < 1 or month > 12:
        month = None
    return {"year": year, "month": month}

def photo_urls(item: Dict[str, Any], limit: int = 10) -> List[str]:
    """
    Photos[].location дээрээс бүтэн URL үүсгэнэ.
    """
    urls = []
    photos = item.get("Photos") or []
    for p in photos:
        loc = p.get("location")
        if loc and isinstance(loc, str):
            if not loc.startswith("http"):
                urls.append(IMG_BASE + loc)
            else:
                urls.append(loc)
        if len(urls) >= limit:
            break
    return urls

def main_photo_url(item: Dict[str, Any]) -> Optional[str]:
    """
    Photo: "/carpicture09/pic4089/40890325_" -> ихэвчлэн cover нь _001.jpg байдаг.
    """
    base = item.get("Photo")
    if not base:
        # Photos эхнийхийг fallback
        urls = photo_urls(item, limit=1)
        return urls[0] if urls else None

    # аль хэдийн http байвал тэр чигээр нь
    if isinstance(base, str) and base.startswith("http"):
        return base

    # Encar cover зураг ихэвчлэн _001.jpg
    return IMG_BASE + base + "001.jpg"

def normalize_car(item: Dict[str, Any]) -> Dict[str, Any]:
    ym = parse_year_month(item.get("Year"))

    norm = {
        "id": str(item.get("Id")) if item.get("Id") is not None else None,

        "manufacturer": item.get("Manufacturer"),
        "model": item.get("Model"),
        "badge": item.get("Badge"),
        "badge_detail": item.get("BadgeDetail"),

        "fuel_type": item.get("FuelType"),
        "ev_type": item.get("EvType"),
        "green_type": item.get("GreenType"),

        "year_month_raw": safe_int(item.get("Year")),     # 201707
        "year": ym["year"],                               # 2017
        "month": ym["month"],                             # 7
        "form_year": item.get("FormYear"),

        "mileage_km": safe_int(item.get("Mileage")),
        "price_million_krw": float(item["Price"]) if item.get("Price") is not None else None,  # 1590.0 = 1590만원

        "sell_type": item.get("SellType"),
        "buy_type": item.get("BuyType") or [],

        "office_city_state": item.get("OfficeCityState"),

        "separation": item.get("Separation") or [],
        "trust": item.get("Trust") or [],
        "service_mark": item.get("ServiceMark") or [],
        "condition": item.get("Condition") or [],

        "home_service_verification": item.get("HomeServiceVerification"),
        "home_service": True if item.get("HomeServiceVerification") == "Y" else False,

        "main_photo": main_photo_url(item),
        "photo_urls": photo_urls(item, limit=20),
    }
    return norm


# --- Example usage with your sample dict -----------------
if __name__ == "__main__":
    sample = {
        "Id": "40895672",
        "Separation": ["B"],
        "Trust": ["ExtendWarranty", "HomeService"],
        "ServiceMark": ["EncarMeetgo", "EncarDiagnosisP1"],
        "Condition": ["Inspection", "Record", "Resume"],
        "Photo": "/carpicture09/pic4089/40890325_",
        "Photos": [
            {"type": "001", "location": "/carpicture09/pic4089/40890325_001.jpg", "updatedDate": "2025-11-17T03:21:35Z", "ordering": 1.0},
            {"type": "003", "location": "/carpicture09/pic4089/40890325_003.jpg", "updatedDate": "2025-11-17T03:21:35Z", "ordering": 3.0},
        ],
        "Manufacturer": "현대",
        "Model": "그랜저 IG 하이브리드",
        "Badge": "익스클루시브",
        "BadgeDetail": "(세부등급 없음)",
        "GreenType": "Y",
        "EvType": "하이브리드",
        "FuelType": "가솔린+전기",
        "Year": 201707.0,
        "FormYear": "2018",
        "Mileage": 100315.0,
        "HomeServiceVerification": "Y",
        "ServiceCopyCar": "DUPLICATION",
        "Price": 1590.0,
        "SellType": "일반",
        "BuyType": ["Delivery"],
        "OfficeCityState": "경기"
    }

    print(normalize_car(sample))
