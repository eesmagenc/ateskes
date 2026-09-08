import requests
import math

def yukseklik_cek(lat, lon):
    url = "https://api.opentopodata.org/v1/srtm30m"
    offset = 0.0009  # ~100 metre

    noktalar = [
        (lat, lon),
        (lat + offset, lon),   # kuzey
        (lat - offset, lon),   # güney
        (lat, lon + offset),   # doğu
        (lat, lon - offset),   # batı
    ]

    locations = "|".join(f"{n[0]},{n[1]}" for n in noktalar)
    response = requests.get(url, params={"locations": locations})

    if response.status_code == 200:
        sonuclar = response.json()["results"]
        return {
            "merkez": sonuclar[0]["elevation"],
            "kuzey" : sonuclar[1]["elevation"],
            "guney" : sonuclar[2]["elevation"],
            "dogu"  : sonuclar[3]["elevation"],
            "bati"  : sonuclar[4]["elevation"],
        }
    return None

def egim_hesapla(yukseklikler, nokta_araligi_metre=100):
    """
    4 komşu noktanın yükseklik farkından eğimi hesaplar.
    Sonuç: derece cinsinden eğim açısı
    """
    merkez = yukseklikler["merkez"]
    farklar = [
        abs(merkez - yukseklikler["kuzey"]),
        abs(merkez - yukseklikler["guney"]),
        abs(merkez - yukseklikler["dogu"]),
        abs(merkez - yukseklikler["bati"]),
    ]
    max_fark = max(farklar)
    egim_radyan = math.atan(max_fark / nokta_araligi_metre)
    return round(math.degrees(egim_radyan), 1)

# --- TEST ---
lat = 37.21  # Muğla il merkezi
lon = 28.36

print(f"📍 ({lat}, {lon}) için yükseklik ve eğim hesaplanıyor...\n")

yukseklikler = yukseklik_cek(lat, lon)

if yukseklikler:
    egim = egim_hesapla(yukseklikler)

    print(f"✅ Sonuçlar:")
    print(f"   📍 Merkez Yüksekliği : {yukseklikler['merkez']} metre")
    print(f"   ⬆️  Kuzey             : {yukseklikler['kuzey']} metre")
    print(f"   ⬇️  Güney             : {yukseklikler['guney']} metre")
    print(f"   ➡️  Doğu              : {yukseklikler['dogu']} metre")
    print(f"   ⬅️  Batı              : {yukseklikler['bati']} metre")
    print(f"\n   📐 Hesaplanan Eğim   : {egim}°")

    if egim < 5:
        print(f"   📊 Eğim Seviyesi     : Düz arazi")
    elif egim < 15:
        print(f"   📊 Eğim Seviyesi     : Hafif eğimli")
    elif egim < 30:
        print(f"   📊 Eğim Seviyesi     : Orta eğimli ⚠️")
    else:
        print(f"   📊 Eğim Seviyesi     : Dik arazi 🔴")