from fastapi import FastAPI
import requests
import math
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

app = FastAPI(title="AteşKes API", version="1.0.0")

# --- YARDIMCI FONKSİYONLAR ---


def hava_verisi_cek(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "windspeed_10m",
            "winddirection_10m",
            "relativehumidity_2m"
        ],
        "timezone": "Europe/Istanbul"
    }
    r = requests.get(url, params=params)
    if r.status_code == 200:
        c = r.json()["current"]
        return {
            "sicaklik": c["temperature_2m"],
            "ruzgar_hizi": c["windspeed_10m"],
            "ruzgar_yonu": c["winddirection_10m"],
            "nem": c["relativehumidity_2m"]
        }
    return None

def yukseklik_cek(lat, lon):
    url = "https://api.opentopodata.org/v1/srtm30m"
    offset = 0.0009
    noktalar = [
        (lat, lon),
        (lat + offset, lon),
        (lat - offset, lon),
        (lat, lon + offset),
        (lat, lon - offset),
    ]
    locations = "|".join(f"{n[0]},{n[1]}" for n in noktalar)
    r = requests.get(url, params={"locations": locations})
    if r.status_code == 200:
        s = r.json()["results"]
        return {
            "merkez": s[0]["elevation"],
            "kuzey" : s[1]["elevation"],
            "guney" : s[2]["elevation"],
            "dogu"  : s[3]["elevation"],
            "bati"  : s[4]["elevation"],
        }
    return None

def egim_hesapla(yukseklikler, aralik=100):
    merkez = yukseklikler["merkez"]
    farklar = [abs(merkez - yukseklikler[y]) for y in ["kuzey","guney","dogu","bati"]]
    return round(math.degrees(math.atan(max(farklar) / aralik)), 1)

def risk_skoru_hesapla(sicaklik, ruzgar_hizi, nem, egim_derece):
    # Normalize (0-1 arasına çek)
    sicaklik_norm    = min(max((sicaklik - 10) / 50, 0), 1)   # 10-60°C arası
    ruzgar_norm      = min(max(ruzgar_hizi / 80, 0), 1)        # 0-80 km/h arası
    nem_norm         = min(max((100 - nem) / 100, 0), 1)       # düşük nem = yüksek risk
    egim_norm        = min(max(egim_derece / 45, 0), 1)        # 0-45 derece arası

    # Etkileşim faktörü: sıcak + rüzgarlı = çok tehlikeli
    etkilesim = sicaklik_norm * ruzgar_norm

    risk = (
        sicaklik_norm * 0.25 +
        ruzgar_norm   * 0.25 +
        nem_norm      * 0.20 +
        egim_norm     * 0.15 +
        etkilesim     * 0.15
    )

    return round(min(max(risk, 0), 1), 3)

# --- ENDPOINTS ---

@app.get("/")
def root():
    return {"durum": "calisiyor", "proje": "AteşKes"}

@app.get("/saglik")
def saglik():
    return {"durum": "✅ API çalışıyor"}

@app.get("/debug")
def debug():
    key = os.getenv("MAP_KEY")
    return {"MAP_KEY": key}

@app.get("/debug-firms")
def debug_firms():
    key = os.getenv("MAP_KEY")
    # Türkiye bbox: 36,26,42,45
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/MODIS_NRT/26,36,45,42/1"
    r = requests.get(url)
    return {
        "url": url,
        "status_code": r.status_code,
        "ilk_100_karakter": r.text[:100]
    }

@app.get("/yangin-noktalari")
def yangin_noktalari(
    min_risk: float = 0.0,
    max_risk: float = 1.0,
    limit: int = 5
):
    MAP_KEY = os.getenv("MAP_KEY")
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/MODIS_NRT/26,36,45,42/1"
    r = requests.get(url)
    if r.status_code != 200:
        return {"hata": "FIRMS verisi alinamadi"}

    satirlar = r.text.strip().split("\n")
    basliklar = satirlar[0].split(",")
    sonuclar = []

    for satir in satirlar[1:]:
        if len(sonuclar) >= limit:  # limit kadar nokta yeterli
            break
        degerler = satir.split(",")
        if len(degerler) < 2:
            continue
        try:
            lat = float(degerler[basliklar.index("latitude")])
            lon = float(degerler[basliklar.index("longitude")])
            confidence = degerler[basliklar.index("confidence")] if "confidence" in basliklar else ""
            acq_date = degerler[basliklar.index("acq_date")] if "acq_date" in basliklar else ""
        except:
            continue

        hava = hava_verisi_cek(lat, lon)
        if hava is None:
            continue

        yukseklikler = yukseklik_cek(lat, lon)
        if yukseklikler is None:
            continue

        egim = egim_hesapla(yukseklikler)
        risk = risk_skoru_hesapla(
            hava["sicaklik"], hava["ruzgar_hizi"],
            hava["nem"], egim
        )

        if risk < min_risk or risk > max_risk:
            continue

        sonuclar.append({
            "bolge_id": f"nokta_{len(sonuclar)+1}",
            "lat": lat,
            "lon": lon,
            "risk_skoru": risk,
            "sicaklik": hava["sicaklik"],
            "ruzgar_hizi": hava["ruzgar_hizi"],
            "ruzgar_yonu": hava["ruzgar_yonu"],
            "nem": hava["nem"],
            "yukseklik_metre": yukseklikler["merkez"],
            "egim_derece": egim,
            "acq_date": acq_date,
            "confidence": confidence
        })

    return {"toplam_nokta": len(sonuclar), "veri": sonuclar}