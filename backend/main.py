import os
import sys
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- CRUD katmanı buradan geliyor, main.py bunları TEKRAR YAZMIYOR ---
from veritabani import veritabani_baglan, bolge_ekle, bolge_getir, tum_bolgeleri_getir

# hesaplamalar.py'yi data-processing klasöründen import et
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'data-processing'))
from hesaplamalar import (
    egim_hesapla, egim_yonu_belirle,
    risk_skoru, oncelik_skoru, tahliye_skoru,
    ruzgar_egime_uyumlu_mu, yayilma_hizi_belirle
)

load_dotenv()
app = FastAPI()

# -----------------------------------------------------------------------
# CORS AYARI
# -----------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    except requests.RequestException:
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
    except requests.RequestException:
        return None


def guncelleme_eskimi_mi(bolge, dakika=30):
    """bolge: veritabani.bolge_getir()'den gelen dict ya da None."""
    if bolge is None or bolge.get("guncelleme_zamani") is None:
        return True
    son = datetime.fromisoformat(bolge["guncelleme_zamani"])
    return datetime.utcnow() - son > timedelta(minutes=dakika)


# -----------------------------------------------------------------------
# ENDPOİNTLER
# -----------------------------------------------------------------------
@app.get("/")
def ana_sayfa():
    return {"durum": "calisiyor", "proje": "AteşKes"}


@app.get("/saglik")
def saglik():
    return {"durum": "API çalışıyor"}


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
        except (ValueError, IndexError):
            continue

        bolge_id = f"nokta_{lat}_{lon}"

        # --- CRUD: READ. Bu nokta daha önce işlendi mi? ---
        mevcut = bolge_getir(conn, bolge_id)

        # --- Yükseklik/eğim: coğrafya sabit, DB'de varsa tekrar çekme ---
        if mevcut and mevcut["yukseklik_metre"] is not None:
            yukseklik_metre = mevcut["yukseklik_metre"]
            egim_derece = mevcut["egim_derece"]
            egim_yonu = mevcut["egim_yonu"]  # coğrafi olarak sabit, DB'den okunuyor
        else:
            yukseklikler = yukseklik_cek(lat, lon)
            if yukseklikler is None:
                continue
            yukseklik_metre = yukseklikler["merkez"]
            egim_derece = egim_hesapla(yukseklikler)
            egim_yonu = egim_yonu_belirle(yukseklikler)

        # --- Hava + risk: sadece 30 dakikada bir yeniden hesapla ---
        if guncelleme_eskimi_mi(mevcut, dakika=30):
            hava = hava_verisi_cek(lat, lon)
            if hava is None:
                continue

            risk = risk_skoru(hava["sicaklik"], hava["ruzgar_hizi"], hava["nem"], egim_derece)
            oncelik = 0.7  # TODO: OSM kritik alan eşleştirmesi bitince oncelik_skoru() ile değiştir
            tahliye = tahliye_skoru(risk, oncelik)
            uyumlu = ruzgar_egime_uyumlu_mu(hava["ruzgar_yonu"], egim_yonu)
            yayilma = yayilma_hizi_belirle(hava["ruzgar_hizi"], egim_derece, uyumlu)

            bolge = {
                "bolge_id": bolge_id, "lat": lat, "lon": lon,
                "risk_skoru": round(risk, 3), "oncelik_skoru": oncelik, "tahliye_skoru": tahliye,
                "yangin_yonu_derece": hava["ruzgar_yonu"], "yayilma_hizi": yayilma,
                "yukseklik_metre": yukseklik_metre, "egim_derece": egim_derece, "egim_yonu": egim_yonu,
                "sicaklik": hava["sicaklik"], "nem": hava["nem"], "ruzgar_hizi": hava["ruzgar_hizi"],
                "guncelleme_zamani": datetime.utcnow().isoformat(),
            }
            # --- CRUD: CREATE/UPDATE. Hesaplanan veriyi DB'ye yaz ---
            bolge_ekle(conn, bolge)
        else:
            # Hava/risk taze — dış API'ye gitmeden DB'deki değerleri kullan
            bolge = mevcut

        if bolge["risk_skoru"] < min_risk or bolge["risk_skoru"] > max_risk:
            continue

        sonuclar.append({**bolge, "acq_date": acq_date, "confidence": confidence})

    conn.close()
    return {"toplam_nokta": len(sonuclar), "veri": sonuclar}


@app.get("/bolgeler/{bolge_id}")
def tek_bolge(bolge_id: str):
    conn = veritabani_baglan()
    bolge = bolge_getir(conn, bolge_id)
    conn.close()
    if bolge is None:
        return {"hata": "bolge bulunamadi"}
    return bolge


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