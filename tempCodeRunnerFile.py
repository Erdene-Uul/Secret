import requests
import psycopg2
from psycopg2.extras import execute_values
import pandas as pd
import re
import time
import random
from datetime import datetime
from typing import Optional, List, Set, Tuple, Dict
import logging

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# =========================
# DB CONFIG
# =========================
DB_CONFIG = dict(
    dbname="postgres",
    user="admin",
    password="socar",
    host="18.167.136.248",
    port="5432"
)

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
# TUNING (ачаалал/хурд)
# =========================
PAGE_LIMIT = 20          # Encar list page size
MAX_PAGES_PER_QUERY = 5000  # хамгаалалт (та хүсвэл багасга)
BATCH_SIZE = 200         # DB insert batch size (100~500 зөв)
SLEEP_MIN = 0.15         # HTTP request хооронд
SLEEP_MAX = 0.45
ENABLE_TRANSLATE = True # googletrans их удаан/unstable байж болно

# =========================
# EXCEL NORMALIZATION
# =========================
MODEL_FIX = {"그렌저": "그랜저"}
FUEL_FIX = {
    "휘발류": "휘발유",
    "가솔린": "휘발유",
    "디젤": "경유",
}

# Англи/Монгол mapping (тогтвортой, хурдан)
BRAND_NAME_MAP = {
    "현대": "Hyundai",
    "벤츠": "Mercedes",
    "기아": "Kia",
    "토요타": "Toyota",
    "도요타": "Toyota",
}
FUEL_TYPE_MAP_MN = {
    "휘발유": "Бензин",
    "경유": "Дизель",
    "겸용": "Хосолсон",
    "하이브리드": "Хайбрид",
    "CNG": "CNG",
    "전기": "Цахилгаан",
    "수소": "Ус төрөгчийн түлш",
    # Encar spec fuelName дээр "가솔린+전기" гэх мэт ирж болно
    "가솔린+전기": "Хайбрид",
}

# =========================
# UTIL
# =========================
def sleep(a=SLEEP_MIN, b=SLEEP_MAX):
    time.sleep(random.uniform(a, b))

def clean_text(x) -> Optional[str]:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    if not s:
        return None
    s = re.sub(r"\s+", " ", s)
    return s

def parse_min_year(v) -> Optional[int]:
    if v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and not v.strip()):
        return None
    m = re.search(r"\d{4}", str(v))
    return int(m.group()) if m else None

def year_range(min_year: int) -> str:
    return f"Year.range({min_year}00..)"

def normalize_model(model: Optional[str]) -> Optional[str]:
    if not model:
        return None
    for k, v in MODEL_FIX.items():
        model = model.replace(k, v)
    return model

def normalize_fuels(fuel_cell: Optional[str]) -> List[str]:
    if not fuel_cell:
        return []
    raw = str(fuel_cell).replace("，", ",")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    out = []
    for p in parts:
        p = FUEL_FIX.get(p, p)
        out.append(p)

    # unique
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
    if fuel == "LPG":
        # network дээр танайд ингэж явсан:
        return "FuelType.LPG(일반인 구입_)"
    return f"FuelType.{fuel}"

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
# TRANSLATION (optional)
# =========================
_translator = None
_translate_cache: Dict[Tuple[str, str, str], str] = {}

def translate_text(text: Optional[str], src="ko", dest="en") -> Optional[str]:
    """
    - ENABLE_TRANSLATE=False үед: mapping байвал mapping, үгүй бол original буцаана.
    - True үед: googletrans ашиглана (cache-тэй)
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    if "LPG" in s:
        return "Газ"
    # known mappings (fast)
    if s in BRAND_NAME_MAP and dest == "en":
        return BRAND_NAME_MAP[s]
    if s in FUEL_TYPE_MAP_MN and dest == "mn":
        return FUEL_TYPE_MAP_MN[s]

    if not ENABLE_TRANSLATE:
        return s

    global _translator
    key = (s, src, dest)
    if key in _translate_cache:
        return _translate_cache[key]

    try:
        if _translator is None:
            from googletrans import Translator
            _translator = Translator()
        # googletrans translate (sync)
        res = _translator.translate(s, src=src, dest=dest)
        out = res.text
        _translate_cache[key] = out
        return out
    except Exception as e:
        logging.warning(f"Translation failed: {s} -> {dest}, err={e}")
        return s

# =========================
# HTTP SESSION (retry/backoff)
# =========================
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)

    # simple retry/backoff
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=50,
        pool_maxsize=50,
        max_retries=0
    )
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

def http_get_json(session: requests.Session, url: str, params: dict, timeout=25, max_try=5) -> dict:
    last_err = None
    for i in range(max_try):
        try:
            r = session.get(url, params=params, timeout=timeout)
            if r.status_code == 400:
                raise RuntimeError(f"400 Bad Request\nURL={r.url}\nBody={r.text[:600]}")
            if r.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {r.status_code} {r.text[:200]}")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            # exponential backoff
            wait = min(8.0, (2 ** i) * 0.5) + random.uniform(0, 0.3)
            logging.warning(f"HTTP retry {i+1}/{max_try} err={e} wait={wait:.2f}s")
            time.sleep(wait)
    raise last_err

# =========================
# ENCAR API
# =========================
def fetch_list(session: requests.Session, q: str, page: int, limit: int = PAGE_LIMIT, sort: str = "ModifiedDate") -> List[dict]:
    params = {
        "count": "true",
        "q": q,
        "sr": f"|{sort}|{(page - 1) * limit}|{limit}",
        "inav": "|Metadata|Sort"
    }
    data = http_get_json(session, LIST_API, params=params, timeout=25)
    return data.get("SearchResults", [])

def fetch_detail(session: requests.Session, vehicle_id: str) -> dict:
    url = DETAIL_API.format(id=vehicle_id)
    params = {"include": DETAIL_INCLUDE}
    return http_get_json(session, url, params=params, timeout=25)

# =========================
# NORMALIZE
# =========================
def normalize(detail: dict) -> dict:
    spec = detail.get("spec") or {}
    category = detail.get("category") or {}
    adv = detail.get("advertisement") or {}

    photos = detail.get("photos") or []
    photos_sorted = sorted(
        photos,
        key=lambda p: int(p.get("code") or 0)
    )
    images = [IMG_BASE + p["path"] for p in photos_sorted if p.get("path")]

    # title
    title_en = " ".join(filter(None, [
        translate_text(category.get("modelName"), dest="en"),
        category.get("gradeEnglishName"),
        category.get("gradeDetailEnglishName"),
    ]))
    title_ko = " ".join(filter(None, [
        category.get("manufacturerName"),
        category.get("modelName"),
        category.get("gradeName"),
        category.get("gradeDetailName"),
    ]))

    manufacturer_en = category.get("manufacturerEnglishName") or translate_text(category.get("manufacturerName"), dest="en")

    # fuelName дээр "가솔린+전기" гэх мэт ирдэг тул MN mapping ашиглая
    fuel_name = spec.get("fuelName")
    fuel_mn = translate_text(fuel_name, dest="mn")  # ENABLE_TRANSLATE=False үед mapping байвал MN, үгүй бол original

    return {
        "vin": detail.get("vin"),
        "title": title_en,
        "title_korean": title_ko,
        "manufacturer": manufacturer_en,
        "fuel": fuel_mn,
        "engine": spec.get("displacement"),
        "price": adv.get("price"),
        "year": category.get("formYear"),
        "mileage": spec.get("mileage"),
        "color": translate_text(spec.get("colorName"), dest="en") if ENABLE_TRANSLATE else (spec.get("colorName") or None),
        "seat_count": spec.get("seatCount"),
        "images": images
    }

# =========================
# DB HELPERS (batch)
# =========================
CAR_INSERT_SQL = """
INSERT INTO cars (
    vin_number, name, name_korean, status, fuel_type,
    engine_displacement, starting_price,
    model_year, mileage, color, manufacturer,
    created_by, created_date, updated_by, updated_date,
    isready, seating_capacity
) VALUES %s
ON CONFLICT (vin_number) DO NOTHING;
"""

def ensure_indexes(cur):
    # Давхардал хамгаалах (хэрэв байхгүй бол)
    # NOTE: үйлдвэрлэл дээр өмнө нь хийсэн байж магадгүй. Алдааг ignore.
    try:
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_cars_vin ON cars (vin_number);")
    except Exception:
        pass

def fetch_existing_vins(cur, vins: List[str]) -> Set[str]:
    if not vins:
        return set()
    cur.execute("SELECT vin_number FROM cars WHERE vin_number = ANY(%s)", (vins,))
    return {r[0] for r in cur.fetchall()}

def fetch_vin_to_id(cur, vins: List[str]) -> Dict[str, int]:
    if not vins:
        return {}
    cur.execute("SELECT vin_number, id FROM cars WHERE vin_number = ANY(%s)", (vins,))
    return {vin: cid for (vin, cid) in cur.fetchall()}

def insert_batch(cur, batch: List[dict]):
    """
    batch: [{vin,title,...,images:[...]}]
    - Cars: execute_values + ON CONFLICT DO NOTHING
    - Then: vin->id авч, images-г batch insert
    """
    # 1) cars insert values
    car_values = []
    vins = []
    for c in batch:
        vin = c.get("vin")
        if not vin:
            continue
        vins.append(vin)
        car_values.append((
            vin,
            c.get("title"),
            c.get("title_korean"),
            1,
            c.get("fuel"),
            c.get("engine"),
            c.get("price"),
            c.get("year"),
            c.get("mileage"),
            c.get("color"),
            c.get("manufacturer"),
            1,
            datetime.now(),
            1,
            datetime.now(),
            True,               # isready
            c.get("seat_count")
        ))

    if not car_values:
        return 0, 0

    # 2) insert cars (dedupe via unique index)
    execute_values(cur, CAR_INSERT_SQL, car_values, page_size=200)

    # 3) vin->id mapping
    vin_to_id = fetch_vin_to_id(cur, vins)

    # 4) images insert
    img_rows = []
    for c in batch:
        vin = c.get("vin")
        if not vin:
            continue
        car_id = vin_to_id.get(vin)
        if not car_id:
            continue
        for img in (c.get("images") or []):
            img_rows.append((car_id, img, 1, 1, datetime.now(), 1, datetime.now()))

    if img_rows:
        execute_values(cur, """
            INSERT INTO car_images
            (car_id, name, status, created_by, created_date, updated_by, updated_date)
            VALUES %s
        """, img_rows, page_size=500)

    return len(car_values), len(img_rows)

# =========================
# READ EXCEL -> QUERIES
# =========================
def queries_from_excel_row(row) -> List[Tuple[str, str]]:
    manu = clean_text(row.get("Үйлдвэр"))
    model = normalize_model(clean_text(row.get("Марк")))
    fuels = normalize_fuels(clean_text(row.get("Хөдөлгүүр")))
    min_year = parse_min_year(row.get("он"))

    if not manu or not model:
        return []

    if not fuels:
        q = build_q(min_year, manu, model, fuel_q=None)
        return [(q, f"{manu}/{model}/NOFUEL/{min_year or ''}")]

    out = []
    for f in fuels:
        fq = fuel_to_q(f)
        if not fq:
            continue
        q = build_q(min_year, manu, model, fuel_q=fq)
        out.append((q, f"{manu}/{model}/{f}/{min_year or ''}"))
    return out

# =========================
# MAIN
# =========================
def main():
    # Excel
    conditions = pd.read_excel(EXCEL_FILE)
    if "Үйлдвэр" in conditions.columns:
        conditions["Үйлдвэр"] = conditions["Үйлдвэр"].ffill()

    # DB
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    ensure_indexes(cur)
    conn.commit()

    # HTTP
    session = make_session()

    # Dedup by vehicleId (list дээр давхцахаас хамгаална)
    seen_vehicle_ids: Set[str] = set()

    # batch buffer
    batch: List[dict] = []
    inserted_cars_total = 0
    inserted_imgs_total = 0
    fetched_total = 0

    try:
        for idx, row in conditions.iterrows():
            qs = queries_from_excel_row(row)
            if not qs:
                logging.info(f"[SKIP row {idx}] missing manufacturer/model or invalid data")
                continue

            for q, label in qs:
                logging.info(f"QUERY: {label}")
                logging.debug(f"q={q}")

                page = 1
                while page <= MAX_PAGES_PER_QUERY:
                    cars = fetch_list(session, q, page, limit=PAGE_LIMIT, sort="ModifiedDate")
                    if not cars:
                        break

                    # энэ page дээр шинэ ID байхгүй бол зогсооно (асар их давхардалтай үед хурд нэмнэ)
                    new_count = 0
                    for c in cars:
                        vid = str(c.get("Id") or "")
                        if vid and vid not in seen_vehicle_ids:
                            new_count += 1
                    if new_count == 0:
                        break

                    for c in cars:
                        vid = str(c.get("Id") or "")
                        if not vid or vid in seen_vehicle_ids:
                            continue
                        seen_vehicle_ids.add(vid)

                        try:
                            detail = fetch_detail(session, vid)
                            data = normalize(detail)
                            fetched_total += 1

                            # batch-д хийнэ
                            if data.get("vin"):
                                batch.append(data)

                            # batch хүрвэл insert
                            if len(batch) >= BATCH_SIZE:
                                # өмнө нь байгаа VIN-үүдийг урьдчилан хасаж (DB ачаалал багасгана)
                                vins = [b["vin"] for b in batch if b.get("vin")]
                                existing = fetch_existing_vins(cur, vins)
                                batch_to_insert = [b for b in batch if b.get("vin") not in existing]

                                if batch_to_insert:
                                    cars_n, imgs_n = insert_batch(cur, batch_to_insert)
                                    conn.commit()
                                    inserted_cars_total += cars_n
                                    inserted_imgs_total += imgs_n
                                    logging.info(f"BATCH COMMIT: cars={cars_n}, images={imgs_n}, totalCars={inserted_cars_total}")
                                else:
                                    conn.commit()

                                batch.clear()

                            sleep()

                        except Exception as e:
                            logging.error(f"DETAIL/DB ERROR vid={vid}: {e}")
                            conn.rollback()

                    page += 1

        # үлдэгдэл batch
        if batch:
            vins = [b["vin"] for b in batch if b.get("vin")]
            existing = fetch_existing_vins(cur, vins)
            batch_to_insert = [b for b in batch if b.get("vin") not in existing]
            if batch_to_insert:
                cars_n, imgs_n = insert_batch(cur, batch_to_insert)
                conn.commit()
                inserted_cars_total += cars_n
                inserted_imgs_total += imgs_n
                logging.info(f"FINAL COMMIT: cars={cars_n}, images={imgs_n}, totalCars={inserted_cars_total}")
            batch.clear()

        logging.info(f"DONE. fetched={fetched_total}, insertedCars={inserted_cars_total}, insertedImages={inserted_imgs_total}")

    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        try:
            session.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
