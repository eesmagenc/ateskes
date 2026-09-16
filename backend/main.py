import os
import sys
import logging
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

# --- CRUD katmanı buradan geliyor, main.py bunları TEKRAR YAZMIYOR ---
from veritabani import veritabani_baglan, bolge_ekle, bolge_getir, tum_bolgeleri_getir

# hesaplamalar.py'yi data-processing klasöründen import et
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'data-processing'))
from hesaplamalar import (
    egim_hesapla, egim_yonu_belirle,
    risk_skoru, tahliye_skoru,
    ruzgar_egime_uyumlu_mu, yayilma_hizi_belirle,
    bolge_oncelik_belirle, osm_kritik_alanlari_cek,
)
from yol_verisi import yol_verisi_cek

load_dotenv()

# --- Loglama: hata olduğunda terminalde görünür kayıt tutar (sunumda "neden
#     çöktü" sorusuna cevap verir). basicConfig sadece burada, bir kere. ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ateskes.main")

app = FastAPI(
    title="AteşKes API",
    description="Yangın risk skoru, tahliye önceliği ve eğime duyarlı rota verisi sunan backend.",
    version="0.3.0",
)

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


# --- OSM kritik alanları (hastane/okul/huzurevi/köy) — sadece 1 kez çekilir,
#     bellekte tutulur. Overpass'a her /bolgeler isteğinde gitmiyoruz. ---
_kritik_alanlar_cache = None


def kritik_alanlari_getir():
    global _kritik_alanlar_cache
    if _kritik_alanlar_cache is None:
        try:
            _kritik_alanlar_cache = osm_kritik_alanlari_cek()
        except Exception:
            # Overpass o an cevap vermiyorsa sistem çökmesin; boş liste ile
            # devam et, bolge_oncelik_belirle() bu durumda 0.5 (nötr) döner.
            _kritik_alanlar_cache = []
    return _kritik_alanlar_cache


# -----------------------------------------------------------------------
# ENDPOİNTLER
# -----------------------------------------------------------------------
@app.get("/")
def ana_sayfa():
    return {"durum": "calisiyor", "proje": "AteşKes"}


@app.get("/saglik")
def saglik():
    return {"durum": "API çalışıyor"}


@app.get(
    "/bolgeler",
    summary="Aktif yangın noktalarını risk/eğim/tahliye bilgisiyle döndürür",
)
def bolgeler_getir(
    limit: int = Query(20, description="Döndürülecek maksimum nokta sayısı", example=20),
    min_risk: float = Query(0.0, ge=0.0, le=1.0, description="0-1 arası minimum risk skoru filtresi"),
    max_risk: float = Query(1.0, ge=0.0, le=1.0, description="0-1 arası maksimum risk skoru filtresi"),
):
    """NASA FIRMS'ten aktif yangın noktalarını çeker; her nokta için Open-Meteo
    hava verisi ve Open-Topo-Data eğim/yükseklik verisiyle Sultan'ın risk,
    öncelik ve tahliye formüllerini uygular. Coğrafi veriler (yükseklik, eğim,
    öncelik) veritabanında önbelleklenir; hava/risk 30 dakikada bir tazelenir.
    """
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
            oncelik, en_yakin_alan, _ = bolge_oncelik_belirle(
                lat, lon, kritik_alanlari_getir(), maks_mesafe_metre=20000
            )
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


@app.get(
    "/yollar",
    summary="Bölgedeki yolları eğim etiketiyle döndürür",
    response_description="Ana yol / tali yol / orman yolu olarak sınıflandırılmış, her segmentte egim_derece alanı olan yol listesi.",
)
def yollar_getir(
    min_lat: float = Query(..., description="Bounding box güney sınırı, örn. 36.75", example=36.75),
    min_lon: float = Query(..., description="Bounding box batı sınırı, örn. 28.15", example=28.15),
    max_lat: float = Query(..., description="Bounding box kuzey sınırı, örn. 36.95", example=36.95),
    max_lon: float = Query(..., description="Bounding box doğu sınırı, örn. 28.40", example=28.40),
    egim_ekle: bool = Query(True, description="True ise her segmentin egim_derece alanı hesaplanır (yavaşlatır)."),
):
    """
    Verilen bounding box içindeki yolları OSM/Overpass'tan çeker.

    egim_ekle=true olduğunda her segmentin başlangıç ve bitiş noktasında
    Sultan'ın egim_hesapla() fonksiyonu çağrılır, ikisinin ortalaması
    segmentin egim_derece alanına yazılır (Sultan'ın A* Eğim Cezası bu
    alanı kullanacak).
    """
    yollar = yol_verisi_cek((min_lat, min_lon, max_lat, max_lon))
    if not yollar:
        logger.warning("Bu bbox icin yol verisi bulunamadi: %s", (min_lat, min_lon, max_lat, max_lon))
        return {"hata": "Yol verisi alinamadi veya bu bolgede yol yok", "toplam_yol": 0, "veri": []}

    if egim_ekle:
        # Aynı düğüm birçok segmentte başlangıç/bitiş olarak tekrar edebilir
        # (kavşaklar) — aynı koordinat için Open-Topo-Data'yı iki kez
        # çağırmamak için bu istek boyunca geçerli basit bir bellek önbelleği.
        _egim_onbellek = {}

        def egim_al(lat, lon):
            anahtar = (round(lat, 5), round(lon, 5))
            if anahtar not in _egim_onbellek:
                yukseklikler = yukseklik_cek(lat, lon)
                _egim_onbellek[anahtar] = egim_hesapla(yukseklikler) if yukseklikler else None
            return _egim_onbellek[anahtar]

        for yol in yollar:
            baslangic = yol["koordinatlar"][0]
            bitis = yol["koordinatlar"][-1]
            egimler = [e for e in (egim_al(*baslangic), egim_al(*bitis)) if e is not None]
            yol["egim_derece"] = round(sum(egimler) / len(egimler), 1) if egimler else None

    return {"toplam_yol": len(yollar), "veri": yollar}


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