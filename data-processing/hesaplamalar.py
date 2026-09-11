"""AteşKes ortak veri işleme modülü.

Sultan (Veri İşleme & Model) tarafından Hafta 1-2 kapsamında yazıldı;
Esma bu modülü FastAPI tarafında import edip /bolgeler endpoint'ine bağlayacak.
Fonksiyon imzaları 6 Aylık Aksiyon Planı'ndaki (Eylül 2026) tanımlarla birebir uyumludur.
"""
import math

# ---------------------------------------------------------------------------
# Hafta 1 — Eğim ve 4 faktörlü risk skoru
# ---------------------------------------------------------------------------

def egim_hesapla(yukseklikler, nokta_araligi_metre=100):
    """yukseklikler: {"merkez":.., "kuzey":.., "guney":.., "dogu":.., "bati":..}
    Döner: eğim (derece)."""
    merkez = yukseklikler["merkez"]
    farklar = [abs(merkez - yukseklikler[y]) for y in ["kuzey", "guney", "dogu", "bati"]]
    max_fark = max(farklar)
    egim_radyan = math.atan(max_fark / nokta_araligi_metre)
    return round(math.degrees(egim_radyan), 1)


def egim_yonu_belirle(yukseklikler):
    """4 komşu noktadan en yüksek olanın yönünü döndürür ("yokuş yukarı" yön)."""
    komsular = {y: yukseklikler[y] for y in ["kuzey", "guney", "dogu", "bati"]}
    return max(komsular, key=komsular.get)


def risk_skoru(sicaklik, ruzgar_hizi, nem, egim_derece):
    """4 faktörlü risk skoru (0-1 arası normalize). Ağırlıklar bu ay için
    kural tabanlı/kabaca dengelenmiş; 2. ayda gerçek veriyle kalibre edilecek."""
    risk = (
        sicaklik * 0.25
        + ruzgar_hizi * 0.25
        - nem * 0.15
        + egim_derece * 0.35
    )
    return min(max(risk / 100, 0), 1)


# Kritik alan tipine göre öncelik ağırlığı
ONCELIK_AGIRLIKLARI = {
    "hastane": 1.0,
    "okul": 0.9,
    "huzurevi": 0.9,
    "koy": 0.7,
    "tarim_alani": 0.5,
}


def oncelik_skoru(alan_tipi):
    return ONCELIK_AGIRLIKLARI.get(alan_tipi, 0.5)


# ---------------------------------------------------------------------------
# Hafta 2 — Mekânsal eşleştirme, tahliye skoru, yayılma tahmini
# ---------------------------------------------------------------------------

def haversine_mesafe(lat1, lon1, lat2, lon2):
    """İki nokta arası kuş uçuşu mesafe (metre)."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def en_yakin_kritik_alan(yangin_lat, yangin_lon, kritik_alanlar):
    """kritik_alanlar: [{"lat":.., "lon":.., "tip":"hastane", ...}, ...]
    Döner: (en_yakin_alan_dict, mesafe_metre) ya da (None, None) liste boşsa."""
    en_yakin, en_kisa = None, float("inf")
    for alan in kritik_alanlar:
        mesafe = haversine_mesafe(yangin_lat, yangin_lon, alan["lat"], alan["lon"])
        if mesafe < en_kisa:
            en_kisa, en_yakin = mesafe, alan
    return en_yakin, (None if en_yakin is None else en_kisa)


def tahliye_skoru(risk, oncelik):
    """Evacuation Score = Risk × Priority"""
    return round(risk * oncelik, 3)


YON_ACISI = {"kuzey": 0, "dogu": 90, "guney": 180, "bati": 270}


def ruzgar_egime_uyumlu_mu(ruzgar_yonu_derece, yokus_yukari_yon, tolerans_derece=45):
    """ruzgar_yonu_derece: meteorolojik kural — rüzgarın ESTİĞİ (geldiği) yön (0=kuzeyden).
    Yangın rüzgarın GİTTİĞİ yöne yayılır, bu yüzden 180 derece çeviriyoruz.
    Sonuç: rüzgarın gittiği yön ile yokuş yukarı yön örtüşüyor mu (bool)."""
    ruzgarin_gittigi_yon = (ruzgar_yonu_derece + 180) % 360
    hedef_aci = YON_ACISI[yokus_yukari_yon]
    fark = abs((ruzgarin_gittigi_yon - hedef_aci + 180) % 360 - 180)
    return fark <= tolerans_derece


def yayilma_hizi_belirle(ruzgar_hizi, egim_derece, ruzgar_yonu_egime_uyumlu):
    """Rüzgar yönü eğimin yokuş yukarı yönüyle örtüşüyorsa yayılma hızlanır."""
    hiz_puani = ruzgar_hizi * 0.6 + egim_derece * 0.4
    if ruzgar_yonu_egime_uyumlu:
        hiz_puani *= 1.3
    if hiz_puani < 30:
        return "yavas"
    elif hiz_puani < 60:
        return "orta"
    return "hizli"


def bolge_oncelik_belirle(lat, lon, kritik_alanlar, maks_mesafe_metre=None):
    """/bolgeler endpoint'i için tek çağrıda gerçek öncelik skoru.

    en_yakin_kritik_alan() + oncelik_skoru()'nu sarmalar; backend tarafında
    sabit bir varsayım (örn. oncelik = 0.7) yazmak yerine bunu kullanın.

    kritik_alanlar: [{"lat":.., "lon":.., "tip":"hastane"|"okul"|"huzurevi"|"koy", ...}, ...]
    maks_mesafe_metre: verilirse, en yakın kritik alan bu mesafeden uzaksa
        (örn. tenha bir bölgede yangın) varsayılan öncelik döner — hastane/okul
        yakınında olmayan bir noktayı yanlışlıkla "hastane önceliğiyle" etiketlemez.

    Döner: (oncelik_skoru, en_yakin_alan | None, mesafe_metre | None)
    kritik_alanlar boşsa veya hiç eşleşme yoksa: (0.5, None, None) — nötr varsayılan.
    """
    alan, mesafe = en_yakin_kritik_alan(lat, lon, kritik_alanlar)
    if alan is None:
        return 0.5, None, None
    if maks_mesafe_metre is not None and mesafe > maks_mesafe_metre:
        return 0.5, None, mesafe
    return oncelik_skoru(alan["tip"]), alan, mesafe


# ---------------------------------------------------------------------------
# Hafta 1 — OSM'den kritik alan çekme (network I/O)
# ---------------------------------------------------------------------------
# Not: hesaplamalar.py'nin geri kalanı saf fonksiyonlardır; bu iki fonksiyon
# istisna çünkü Esma'nın backend'inin kritik alan listesini nereden alacağını
# ayrı ayrı yazmasına gerek kalmasın diye buraya taşındı (Hafta 1 notebook'ta
# test edilen sorgunun aynısı).

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_OVERPASS_HEADERS = {"User-Agent": "AtesKesProject/1.0 (Biz Teknopark on kuluçka)"}
_OSM_TIP_ESLEME = {"hospital": "hastane", "school": "okul", "nursing_home": "huzurevi", "village": "koy"}


def osm_kritik_alanlari_cek(il_adi="Muğla", limit=30, deneme_sayisi=4):
    """Overpass API'den hastane/okul/huzurevi/köy noktalarını çeker.

    Genel Overpass sunucusu zaman zaman 504 (gateway timeout) dönebiliyor;
    bu yüzden birkaç deneme yapılıyor. Sonuç çeşitlilik için tiplere göre
    sırayla dağıtılır (hepsi aynı tip olmasın diye).

    Döner: [{"isim":.., "tip":"hastane"|"okul"|"huzurevi"|"koy", "lat":.., "lon":..}, ...]
    """
    import time
    import requests

    sorgu = f"""
    [out:json][timeout:60];
    area["name"="{il_adi}"]["admin_level"="4"]->.aranan;
    (
      node["amenity"="hospital"](area.aranan);
      node["amenity"="school"](area.aranan);
      node["amenity"="nursing_home"](area.aranan);
      node["place"="village"](area.aranan);
    );
    out center;
    """
    son_hata = None
    for deneme in range(deneme_sayisi):
        try:
            r = requests.post(_OVERPASS_URL, data={"data": sorgu}, headers=_OVERPASS_HEADERS, timeout=90)
            r.raise_for_status()
            break
        except requests.exceptions.HTTPError as e:
            son_hata = e
            time.sleep(5)
    else:
        raise son_hata

    elemanlar = r.json()["elements"]
    tip_gruplari = {}
    for e in elemanlar:
        tip = e["tags"].get("amenity") or e["tags"].get("place")
        tip_tr = _OSM_TIP_ESLEME.get(tip, tip)
        tip_gruplari.setdefault(tip_tr, []).append({
            "isim": e["tags"].get("name", "isimsiz"),
            "tip": tip_tr,
            "lat": e["lat"],
            "lon": e["lon"],
        })

    sonuc = []
    tur_listeleri = list(tip_gruplari.values())
    i = 0
    while len(sonuc) < limit and any(tur_listeleri):
        tur = tur_listeleri[i % len(tur_listeleri)]
        if tur:
            sonuc.append(tur.pop(0))
        i += 1
        if i > limit * 10:
            break
    return sonuc[:limit]
