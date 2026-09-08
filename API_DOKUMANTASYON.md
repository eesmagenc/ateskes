# AteşKes API Dokümantasyonu

## Base URL
http://localhost:8000

---

## Endpointler

### 1. GET /
API'nin çalışıp çalışmadığını kontrol eder.

**Örnek Yanıt:**
{"durum": "calisiyor", "proje": "AteşKes"}

---

### 2. GET /saglik
API sağlık kontrolü.

**Örnek Yanıt:**
{"durum": "✅ API çalışıyor"}

---

### 3. GET /yangin-noktalari
Türkiye'deki aktif yangın noktalarını risk skoruyla döndürür.

**Parametreler:**

| Parametre | Tip     | Varsayılan | Açıklama                  |
|-----------|---------|------------|---------------------------|
| min_risk  | float   | 0.0        | Minimum risk skoru (0-1)  |
| max_risk  | float   | 1.0        | Maksimum risk skoru (0-1) |
| limit     | int     | tümü       | Kaç nokta dönsün          |

**Örnek İstek:**
GET /yangin-noktalari?min_risk=0.2&limit=10

**Örnek Yanıt:**
{
  "toplam_nokta": 2,
  "veri": [
    {
      "bolge_id": "nokta_1",
      "lat": 36.95,
      "lon": 31.14,
      "risk_skoru": 0.306,
      "sicaklik": 31.1,
      "ruzgar_hizi": 9.5,
      "ruzgar_yonu": 189,
      "nem": 28,
      "yukseklik_metre": 34.0,
      "egim_derece": 5.7,
      "acq_date": "2026-09-08",
      "confidence": "100"
    }
  ]
}

**Alan Açıklamaları:**

| Alan             | Açıklama                              |
|------------------|---------------------------------------|
| bolge_id         | Nokta kimliği                         |
| lat / lon        | Koordinatlar                          |
| risk_skoru       | 0-1 arası risk (1 = çok tehlikeli)    |
| sicaklik         | °C cinsinden sıcaklık                 |
| ruzgar_hizi      | km/h cinsinden rüzgar hızı            |
| ruzgar_yonu      | Derece cinsinden rüzgar yönü          |
| nem              | % cinsinden nem                       |
| yukseklik_metre  | Deniz seviyesinden yükseklik          |
| egim_derece      | Arazi eğimi (derece)                  |
| acq_date         | Verinin alındığı tarih                |
| confidence       | FIRMS güven skoru (0-100)             |

---

## Risk Skoru Nasıl Hesaplanır?

Risk skoru 0 ile 1 arasındadır:

| Skor        | Anlam          |
|-------------|----------------|
| 0.0 - 0.2   | 🟢 Düşük risk  |
| 0.2 - 0.5   | 🟡 Orta risk   |
| 0.5 - 0.8   | 🟠 Yüksek risk |
| 0.8 - 1.0   | 🔴 Kritik risk |

Hesaplamada kullanılan faktörler:
- Sıcaklık (ağırlık: %25)
- Rüzgar hızı (ağırlık: %25)
- Nem (ağırlık: %20)
- Arazi eğimi (ağırlık: %15)
- Sıcaklık x Rüzgar etkileşimi (ağırlık: %15)

---

## Notlar
- Veriler NASA FIRMS (MODIS_NRT) kaynağından anlık çekilmektedir.
- Hava durumu Open-Meteo API'den alınmaktadır.
- Yükseklik ve eğim verisi OpenTopoData API'den alınmaktadır.