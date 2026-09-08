from fastapi import FastAPI
import requests
import math
import os
from dotenv import load_dotenv
load_dotenv()

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
    risk = (
        sicaklik    * 0.25 +
        ruzgar_hizi * 0.25 -
        nem         * 0.15 +
        egim_derece * 0.35
    )
    return round(min(max(risk / 100, 0), 1), 3)

# --- ENDPOINTS ---

@app.get("/")
def root():
    return {"durum": "calisiyor", "proje": "AteşKes"}

@app.get("/saglik")
def saglik():
    return {"durum": "✅ API çalışıyor"}

@app.get("/yangin-noktalari")
def yangin_noktalari():
    # Muğla bölgesi FIRMS verisi
    MAP_KEY = os.getenv("MAP_KEY")
    BBOX = "25.0,36.0,45.0,42.0"

    url = (
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{MAP_KEY}/VIIRS_NOAA20_NRT/{BBOX}/1"
    )

    r = requests.get(url)
    if r.status_code != 200:
        return {"hata": "FIRMS verisi çekilemedi"}

    satirlar = r.text.strip().split("\n")
    if len(satirlar) <= 1:
        return {"mesaj": "Şu an aktif yangın noktası yok", "veri": []}

    import csv, io
    reader = csv.DictReader(io.StringIO(r.text))
    sonuclar = []

    for satir in reader:
        try:
            lat = float(satir["latitude"])
            lon = float(satir["longitude"])

            # Hava verisi
            hava = hava_verisi_cek(lat, lon)
            if not hava:
                continue

            # Yükseklik ve eğim
            yukseklik = yukseklik_cek(lat, lon)
            egim = egim_hesapla(yukseklik) if yukseklik else 0.0
            yukseklik_m = yukseklik["merkez"] if yukseklik else 0.0

            # Risk skoru
            risk = risk_skoru_hesapla(
                hava["sicaklik"],
                hava["ruzgar_hizi"],
                hava["nem"],
                egim
            )

            sonuclar.append({
                "bolge_id": f"nokta_{len(sonuclar)+1}",
                "lat": lat,
                "lon": lon,
                "risk_skoru": risk,
                "sicaklik": hava["sicaklik"],
                "ruzgar_hizi": hava["ruzgar_hizi"],
                "ruzgar_yonu": hava["ruzgar_yonu"],
                "nem": hava["nem"],
                "yukseklik_metre": yukseklik_m,
                "egim_derece": egim,
                "acq_date": satir.get("acq_date", ""),
                "confidence": satir.get("confidence", "")
            })

        except Exception as e:
            continue

    return {
        "toplam_nokta": len(sonuclar),
        "veri": sonuclar
    }