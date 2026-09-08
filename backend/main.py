import os
import sqlite3
import requests
import math
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# hesaplamalar.py'yi data-processing klasöründen import et
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'data-processing'))
from hesaplamalar import egim_hesapla, risk_skoru, oncelik_skoru, tahliye_skoru

load_dotenv()
app = FastAPI()

# -----------------------------------------------------------------------
# CORS AYARI — Sudenur'un frontend'i backend'e bağlanabilsin
# -----------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------
# VERİTABANI
# -----------------------------------------------------------------------
def veritabani_baglan():
    conn = sqlite3.connect("veriler.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bolgeler (
            bolge_id TEXT PRIMARY KEY,
            lat REAL, lon REAL,
            risk_skoru REAL, oncelik_skoru REAL, tahliye_skoru REAL,
            yukseklik_metre REAL, egim_derece REAL,
            guncelleme_zamani TEXT
        )
    """)
    conn.commit()
    return conn

# -----------------------------------------------------------------------
# YARDIMCI FONKSİYONLAR
# -----------------------------------------------------------------------
def hava_verisi_cek(lat, lon):
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
        }
        r = requests.get(url, params=params, timeout=10)
        c = r.json()["current"]
        return {
            "sicaklik": c["temperature_2m"],
            "nem": c["relative_humidity_2m"],
            "ruzgar_hizi": c["wind_speed_10m"],
            "ruzgar_yonu": c["wind_direction_10m"]
        }
    except:
        return None

def yukseklik_cek(lat, lon):
    try:
        offset = 0.0009
        noktalar = f"{lat},{lon}|{lat+offset},{lon}|{lat-offset},{lon}|{lat},{lon+offset}|{lat},{lon-offset}"
        url = f"https://api.opentopodata.org/v1/srtm30m?locations={noktalar}"
        r = requests.get(url, timeout=10)
        sonuclar = r.json()["results"]
        return {
            "merkez": sonuclar[0]["elevation"],
            "kuzey":  sonuclar[1]["elevation"],
            "guney":  sonuclar[2]["elevation"],
            "dogu":   sonuclar[3]["elevation"],
            "bati":   sonuclar[4]["elevation"],
        }
    except:
        return None

def db_den_yukseklik_getir(bolge_id, conn):
    row = conn.execute(
        "SELECT yukseklik_metre, egim_derece FROM bolgeler WHERE bolge_id=?", (bolge_id,)
    ).fetchone()
    return row  # (yukseklik_metre, egim_derece) ya da None

def son_guncelleme_eskimi(bolge_id, conn, dakika=30):
    row = conn.execute(
        "SELECT guncelleme_zamani FROM bolgeler WHERE bolge_id=?", (bolge_id,)
    ).fetchone()
    if row is None or row[0] is None:
        return True
    son = datetime.fromisoformat(row[0])
    return datetime.utcnow() - son > timedelta(minutes=dakika)

# -----------------------------------------------------------------------
# ENDPOİNTLER
# -----------------------------------------------------------------------
@app.get("/")
def ana_sayfa():
    return {"durum": "calisiyor", "proje": "AteşKes"}

@app.get("/saglik")
def saglik():
    return {"durum": "✅ API çalışıyor"}

@app.get("/bolgeler")
def bolgeler_getir(limit: int = 20, min_risk: float = 0.0, max_risk: float = 1.0):
    MAP_KEY = os.getenv("MAP_KEY")
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/MODIS_NRT/26,36,45,42/1"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return {"hata": "FIRMS verisi alinamadi"}

    satirlar = r.text.strip().split("\n")
    basliklar = satirlar[0].split(",")
    sonuclar = []
    conn = veritabani_baglan()

    for satir in satirlar[1:]:
        if len(sonuclar) >= limit:
            break
        degerler = satir.split(",")
        if len(degerler) < 2:
            continue
        try:
            lat = float(degerler[basliklar.index("latitude")])
            lon = float(degerler[basliklar.index("longitude")])
            acq_date = degerler[basliklar.index("acq_date")] if "acq_date" in basliklar else ""
            confidence = degerler[basliklar.index("confidence")] if "confidence" in basliklar else ""
        except:
            continue

        bolge_id = f"nokta_{lat}_{lon}"

        # --- Yükseklik/eğim: DB'de varsa tekrar çekme (sabit coğrafya) ---
        cached = db_den_yukseklik_getir(bolge_id, conn)
        if cached:
            yukseklik_metre, egim_derece = cached
        else:
            yukseklikler = yukseklik_cek(lat, lon)
            if yukseklikler is None:
                continue
            yukseklik_metre = yukseklikler["merkez"]
            egim_derece = egim_hesapla(yukseklikler)

        # --- Hava: 30 dakikada bir güncelle ---
        if son_guncelleme_eskimi(bolge_id, conn, dakika=30):
            hava = hava_verisi_cek(lat, lon)
            if hava is None:
                continue
            risk = risk_skoru(hava["sicaklik"], hava["ruzgar_hizi"], hava["nem"], egim_derece)
            oncelik = 0.7  # FIRMS noktaları için varsayılan
            tahliye = tahliye_skoru(risk, oncelik)

            conn.execute("""
                INSERT INTO bolgeler
                    (bolge_id, lat, lon, risk_skoru, oncelik_skoru, tahliye_skoru,
                     yukseklik_metre, egim_derece, guncelleme_zamani)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bolge_id) DO UPDATE SET
                    risk_skoru=excluded.risk_skoru,
                    oncelik_skoru=excluded.oncelik_skoru,
                    tahliye_skoru=excluded.tahliye_skoru,
                    yukseklik_metre=excluded.yukseklik_metre,
                    egim_derece=excluded.egim_derece,
                    guncelleme_zamani=excluded.guncelleme_zamani
            """, (bolge_id, lat, lon, risk, oncelik, tahliye,
                  yukseklik_metre, egim_derece, datetime.utcnow().isoformat()))
            conn.commit()
        else:
            row = conn.execute(
                "SELECT risk_skoru, oncelik_skoru, tahliye_skoru FROM bolgeler WHERE bolge_id=?",
                (bolge_id,)
            ).fetchone()
            risk, oncelik, tahliye = row
            hava = hava_verisi_cek(lat, lon)

        if risk < min_risk or risk > max_risk:
            continue

        sonuclar.append({
            "bolge_id": bolge_id,
            "lat": lat,
            "lon": lon,
            "risk_skoru": round(risk, 3),
            "oncelik_skoru": oncelik,
            "tahliye_skoru": tahliye,
            "sicaklik": hava["sicaklik"] if hava else None,
            "ruzgar_hizi": hava["ruzgar_hizi"] if hava else None,
            "ruzgar_yonu": hava["ruzgar_yonu"] if hava else None,
            "nem": hava["nem"] if hava else None,
            "yukseklik_metre": yukseklik_metre,
            "egim_derece": egim_derece,
            "acq_date": acq_date,
            "confidence": confidence
        })

    conn.close()
    return {"toplam_nokta": len(sonuclar), "veri": sonuclar}

@app.get("/debug-firms")
def debug_firms():
    key = os.getenv("MAP_KEY")
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/MODIS_NRT/26,36,45,42/1"
    r = requests.get(url)
    return {
        "url": url,
        "status_code": r.status_code,
        "ilk_100_karakter": r.text[:100]
    }