import requests
import pandas as pd
import os
from dotenv import load_dotenv
load_dotenv()
MAP_KEY = os.getenv("MAP_KEY")

# Türkiye koordinatları (batı,güney,doğu,kuzey)
# Muğla ve Ege bölgesi için
TURKEY_BBOX = "25.0,36.0,45.0,42.0"

# Son 1 günün yangın verilerini çek
url = (
   f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
    f"{MAP_KEY}/VIIRS_NOAA20_NRT/{TURKEY_BBOX}/1"
)

print("NASA FIRMS'den veri çekiliyor...")

response = requests.get(url)

if response.status_code == 200:
    # Gelen veriyi pandas ile oku
    from io import StringIO
    df = pd.read_csv(StringIO(response.text))
    print(f"✅ {len(df)} adet yangın noktası bulundu!")
    print(df[["latitude", "longitude", "acq_date", "confidence"]].head(10))
else:
    print(f"❌ Hata: {response.status_code}")
    print(response.text)