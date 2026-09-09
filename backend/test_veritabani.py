from veritabani import veritabani_baglan, bolge_ekle, tum_bolgeleri_getir

conn = veritabani_baglan()

ornek_bolge = {
    "bolge_id": "test_bolge_01",
    "lat": 37.2153,
    "lon": 28.3636,
    "risk_skoru": 0.75,
    "oncelik_skoru": 0.68,
    "tahliye_skoru": 0.55,
    "yangin_yonu_derece": 45,
    "yayilma_hizi": "orta",
    "yukseklik_metre": 340,
    "egim_derece": 18.5,
    "guncelleme_zamani": "2026-08-14T12:00:00Z"
}

bolge_ekle(conn, ornek_bolge)
print("Bölge eklendi.")


tum_veriler = tum_bolgeleri_getir(conn)
print(" Veritabanındaki tüm bölgeler:")
for satir in tum_veriler:
    print(satir)

conn.close()