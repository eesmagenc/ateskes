import sqlite3

def veritabani_baglan():
    conn = sqlite3.connect("veriler.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bolgeler (
            bolge_id TEXT PRIMARY KEY,
            lat REAL, lon REAL,
            risk_skoru REAL, oncelik_skoru REAL, tahliye_skoru REAL,
            yangin_yonu_derece REAL, yayilma_hizi TEXT,
            yukseklik_metre REAL, egim_derece REAL,
            guncelleme_zamani TEXT
        )
        -- Esma ile karar: yangin_yonu_derece ve yayilma_hizi de DB'de
        -- saklanıyor (plandaki Hafta 2 örneği bunları içermiyordu,
        -- ekip kararıyla dahil edildi).
    """)
    return conn

def bolge_ekle(baglanti, bolge):
    baglanti.execute(
        "INSERT OR REPLACE INTO bolgeler VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (bolge["bolge_id"], bolge["lat"], bolge["lon"], bolge["risk_skoru"],
         bolge["oncelik_skoru"], bolge["tahliye_skoru"],
         bolge["yangin_yonu_derece"], bolge["yayilma_hizi"],
         bolge["yukseklik_metre"], bolge["egim_derece"],
         bolge["guncelleme_zamani"])
    )
    baglanti.commit()

def tum_bolgeleri_getir(baglanti):
    return baglanti.execute("SELECT * FROM bolgeler").fetchall()