import requests
import psycopg2
from psycopg2.extras import execute_values
import pandas as pd
import re
import time
import random
from datetime import datetime
from typing import Optional, List, Set, Tuple
from googletrans import Translator
import logging

# =========================
# DB CONFIG
# =========================
connection = psycopg2.connect(
    dbname="postgres",
    user="admin",
    password="socar",
    host="18.167.136.248",
    port="5432"
)
cur = connection.cursor()

# =========================
# FILE
# =========================
EXCEL_FILE = "ENCAR LIST.xlsx"  # таны локал дээрх зам

# =========================
# ENCAR CONFIG
# =========================
LIST_API = "https://api.encar.com/search/car/list/premium"
DETAIL_API = "https://api.encar.com/v1/readside/vehicle/{id}"
DETAIL_INCLUDE = "CONTENTS,SPEC,PHOTOS,OPTIONS,CONDITION,ADVERTISEMENT,CONTACT,CATEGORY,VIEW,MANAGE,PARTNERSHIP"


HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://www.encar.com",
    "Referer": "https://www.encar.com/",
}

IMG_BASE = "https://ci.encar.com"

# =========================
# UTIL
# =========================
def sleep(a=0.5, b=1.2):
    time.sleep(random.uniform(a, b))

def parse_min_year(v) -> Optional[int]:
    """ '2016+', '2016', '2016~' гэх мэтийг 2016 болгож parse хийнэ """
    if v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and not v.strip()):
        return None
    m = re.search(r"\d{4}", str(v))
    return int(m.group()) if m else None

def year_range(min_year: int) -> str:
    # 2016 -> Year.range(201600..)
    return f"Year.range({min_year}00..)"

# =========================
# EXCEL NORMALIZATION (алдаа засах)
# =========================
MODEL_FIX = {
    "그렌저": "그랜저",
}

FUEL_FIX = {
    "휘발류": "휘발유",
    "가솔린": "휘발유",   # зарим excel дээр "가솔린" гэж бичдэг
    "디젤": "경유",       # зарим нь 디젤 гэж бичнэ
}

BRAND_NAME_MAP = {
    "현대": "Hyundai",
    "벤츠": "Mercedes",
}

FUEL_TYPE_MAP = {
    "휘발유": "Бензин",
    "경유": "Дизель",
    "겸용": "Хосолсон",
    "하이브리드": "Хайбрид",
    "CNG": "CNG",
    "전기": "Цахилгаан",
    "수소": "Ус төрөгчийн түлш",
}
def translate_text(text, src='ko', dest='en'):
    if isinstance(text, datetime) or text is None:
        return text  # Return as-is if it's datetime or None
    if "LPG" in text:
        return "Газ"
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

def clean_text(x) -> Optional[str]:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    if not s:
        return None
    # олон space цэвэрлэх
    s = re.sub(r"\s+", " ", s)
    return s

def normalize_model(model: Optional[str]) -> Optional[str]:
    if not model:
        return None
    for k, v in MODEL_FIX.items():
        model = model.replace(k, v)
    return model

def normalize_fuels(fuel_cell: Optional[str]) -> List[str]:
    """
    Excel-ийн "휘발유, LPG" зэрэг утгыг цэвэрлээд list болгоно.
    """
    if not fuel_cell:
        return []
    raw = str(fuel_cell)
    raw = raw.replace("，", ",")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    out = []
    for p in parts:
        p = p.strip()
        p = FUEL_FIX.get(p, p)  # алдаатай бичлэгийг засна
        out.append(p)
    # unique хэвээр
    seen = set()
    uniq = []
    for f in out:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return uniq

def fuel_to_q(fuel: str) -> Optional[str]:
    if not fuel:
        return None

    # LPG (general purchase) - таны Network дээрх хэлбэрээр
    if fuel == "LPG":
        return "FuelType.LPG(일반인 구입_)"

    # Бусад нь ихэнхдээ FuelType.<value>. хэлбэртэй явдаг
    # (шаардлагатай бол энд нэмэлт mapping өргөтгөнө)
    return f"FuelType.{fuel}."

def build_q(min_year: Optional[int], manu: str, model_group: str, fuel_q: Optional[str], adtype: Optional[str] = None) -> str:
    """
    ЯГ Network дээрх separator-тайгаар q үүсгэнэ:
      (And.Year.range(201600..)_.Hidden.N._.FuelType..._._(C.CarType.Y._.(C.Manufacturer..._.ModelGroup...)))
    """
    parts = ["(And"]

    if min_year:
        parts.append("." + year_range(min_year))
    # Hidden
    parts.append("._.Hidden.N._.")

    # Fuel
    if fuel_q:
        parts.append(fuel_q)
        parts.append("._.")

    # Category block
    # Network дээр: (C.CarType.Y._.(C.Manufacturer.기아._.ModelGroup.K8.))
    parts.append(f"(C.CarType.Y._.(C.Manufacturer.{manu}._.ModelGroup.{model_group}.))")

    # optional AdType
    if adtype:
        parts.append(f")_.AdType.{adtype}.)")
    else:
        parts.append("))")

    return "".join(parts)

# =========================
# READ & CLEAN EXCEL
# =========================
conditions = pd.read_excel(EXCEL_FILE)

# "Үйлдвэр" багана хоосон мөрүүдийг дээрхтэй нь fill
if "Үйлдвэр" in conditions.columns:
    conditions["Үйлдвэр"] = conditions["Үйлдвэр"].ffill()

# =========================
# ENCAR API
# =========================
def fetch_list(q: str, page: int, limit: int = 20, sort: str = "ModifiedDate") -> List[dict]:
    params = {
        "count": "true",
        "q": q,
        "sr": f"|{sort}|{(page - 1) * limit}|{limit}",
        "inav": "|Metadata|Sort"
    }
    r = requests.get(LIST_API, params=params, headers=HEADERS, timeout=25)
    # 400 гарвал q-гаа хэвлээд ойлгомжтой болгоё
    if r.status_code == 400:
        raise RuntimeError(f"400 Bad Request. q={q}\nURL={r.url}\nBody={r.text[:400]}")
    r.raise_for_status()
    return r.json().get("SearchResults", [])

def fetch_detail(vehicle_id: str) -> dict:
    r = requests.get(
        DETAIL_API.format(id=vehicle_id),
        params={"include": DETAIL_INCLUDE},
        headers=HEADERS,
        timeout=25
    )
    r.raise_for_status()
    return r.json()


# =========================
# NORMALIZE TO DB
# =========================
def normalize(detail: dict) -> dict:
    spec = detail.get("spec") or {}
    category = detail.get("category") or {}
    adv = detail.get("advertisement") or {}

       # ---- PHOTOS: code-оор ASC sort ----
    photos = detail.get("photos") or []

    photos_sorted = sorted(
        photos,
        key=lambda p: int(p.get("code", 0))  # "001" -> 1
    )

    images = [
        IMG_BASE + p["path"]
        for p in photos_sorted
        if p.get("path")
    ]

    title_en = " ".join(filter(None, [
        translate_text(category.get("modelName")),
        category.get("gradeEnglishName"),
        category.get("gradeDetailEnglishName"),
    ]))

    title_ko = " ".join(filter(None, [
        category.get("modelName"),
        category.get("gradeName"),
        category.get("gradeDetailName"),
    ]))


    return {
        "vin": detail.get("vin"),
        "title": title_en,
        "title_korean": title_ko,
        "manufacturer": category.get("manufacturerEnglishName") or translate_text(category.get("manufacturerName")),
        "fuel": translate_text(spec.get("fuelName")),
        "engine": spec.get("displacement"),
        "price": adv.get("price"),
        "year": category.get("formYear"),
        "mileage": spec.get("mileage"),
        "color": translate_text(spec.get("colorName")),
        "seat_count": spec.get("seatCount"),
        "images": images
    }

# =========================
# INSERT DB
# =========================
def insert_db(car: dict):
    if not car.get("vin"):
        return

    cur.execute(
        "SELECT vin_number FROM cars WHERE vin_number = %s",
        (car["vin"],)
    )
    if cur.fetchone():
        return

    cur.execute("""
        INSERT INTO cars (
            vin_number, name, name_korean, status, fuel_type,
            engine_displacement, starting_price,
            model_year, mileage, color, manufacturer,
            created_by, created_date, updated_by,
            updated_date, isready, seating_capacity
        ) VALUES (
            %s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,
            1,NOW(),1,NOW(),%s,%s
        ) RETURNING id
    """, (
        car["vin"],
        car.get("title"),
        car.get("title_korean"),
        car.get("fuel"),
        car.get("engine"),
        car.get("price"),
        car.get("year"),
        car.get("mileage"),
        car.get("color"),
        car.get("manufacturer"),
        True,
        car.get("seat_count") 
    ))

    car_id = cur.fetchone()[0]

    imgs = [
        (car_id, img, 1, 1, datetime.now(), 1, datetime.now())
        for img in (car.get("images") or [])
    ]

    if imgs:
        execute_values(cur, """
            INSERT INTO car_images
            (car_id, name, status, created_by, created_date, updated_by, updated_date)
            VALUES %s
        """, imgs)

    connection.commit()
    print("INSERTED:", car["vin"])

# =========================
# BUILD QUERIES FROM EXCEL (Fuel олон байвал тусад нь query)
# =========================
def queries_from_excel_row(row) -> List[Tuple[str, str]]:
    """
    Буцаах: [(q, debug_label), ...]
    Fuel олон байвал тус тусад нь q үүсгэнэ (найдвартай)
    """
    manu = clean_text(row.get("Үйлдвэр"))
    model = normalize_model(clean_text(row.get("Марк")))
    fuels = normalize_fuels(clean_text(row.get("Хөдөлгүүр")))
    min_year = parse_min_year(row.get("он"))

    # шаардлагатай field-үүд байхгүй бол алгасна
    if not manu or not model:
        return []

    # fuel хоосон бол FuelType filter-гүйгээр fetch хийнэ (та хүсвэл энд skip болгож болно)
    if not fuels:
        q = build_q(min_year, manu, model, fuel_q=None, adtype=None)
        label = f"{manu}/{model}/NOFUEL/{min_year or ''}"
        return [(q, label)]

    out = []
    for f in fuels:
        fq = fuel_to_q(f)
        if not fq:
            continue
        q = build_q(min_year, manu, model, fuel_q=fq, adtype=None)
        label = f"{manu}/{model}/{f}/{min_year or ''}"
        out.append((q, label))
    return out

# =========================
# MAIN
# =========================
def main():
    # нэг машин олон query-д давхцах боломжтой тул vehicleId-гаар давхар fetch хийхээс хамгаалъя
    seen_vehicle_ids: Set[str] = set()

    for idx, row in conditions.iterrows():
        qs = queries_from_excel_row(row)
        if not qs:
            print(f"[SKIP row {idx}] missing manufacturer/model or invalid data")
            continue

        for q, label in qs:
            print("ENCAR QUERY:", label)
            print("   q =", q)

            page = 1
            while True:
                try:
                    cars = fetch_list(q, page, limit=20, sort="ModifiedDate")
                except Exception as e:
                    print("LIST ERROR:", e)
                    break

                if not cars:
                    break

                # шинэ машин энэ page дээр байгаа эсэхийг эхлээд шалгана
                new_count = sum(
                    1 for c in cars
                    if str(c.get("Id")) and str(c.get("Id")) not in seen_vehicle_ids
                )
                if new_count == 0:
                    break

                for car in cars:
                    vid = str(car.get("Id"))
                    if not vid or vid in seen_vehicle_ids:
                        continue
                    seen_vehicle_ids.add(vid)

                    try:
                        detail = fetch_detail(vid)
                        data = normalize(detail)
                        insert_db(data)
                        sleep()
                    except Exception as e:
                        print("DETAIL/DB ERROR:", e)
                        connection.rollback()

                page += 1


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            connection.close()
        except Exception:
            pass
