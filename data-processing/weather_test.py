import requests

def hava_verisi_cek(lat, lon):
    """
    Verilen enlem/boylam için hava durumu verisi çeker.
    Döndürdüğü veriler: sıcaklık, rüzgar hızı, rüzgar yönü, nem
    """
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",        # sıcaklık (°C)
            "windspeed_10m",         # rüzgar hızı (km/h)
            "winddirection_10m",     # rüzgar yönü (derece)
            "relativehumidity_2m"    # nem (%)
        ],
        "timezone": "Europe/Istanbul"
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        current = data["current"]

        return {
            "sicaklik": current["temperature_2m"],
            "ruzgar_hizi": current["windspeed_10m"],
            "ruzgar_yonu": current["winddirection_10m"],
            "nem": current["relativehumidity_2m"]
        }
    else:
        print(f"Hata: {response.status_code}")
        return None

# Test: Muğla Marmaris koordinatları
lat = 36.85
lon = 28.27

print(f"Muğla Marmaris ({lat}, {lon}) için hava verisi çekiliyor...")
veri = hava_verisi_cek(lat, lon)

if veri:
    print(f"✅ Veri başarıyla çekildi!")
    print(f"   🌡️  Sıcaklık    : {veri['sicaklik']} °C")
    print(f"   💨  Rüzgar Hızı : {veri['ruzgar_hizi']} km/h")
    print(f"   🧭  Rüzgar Yönü : {veri['ruzgar_yonu']}°")
    print(f"   💧  Nem         : {veri['nem']} %")