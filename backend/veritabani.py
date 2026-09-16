import sqlite3

# Sütun sırasını TEK bir yerde tanımlıyoruz. Hem CREATE TABLE hem
# INSERT hem SELECT bu listeyi kullanacak — böylece "7. ve 8. değeri
# ters mi yazdım" tarzı hatalar imkansız hale geliyor.
SUTUNLAR = [
    "bolge_id", "lat", "lon",
    "risk_skoru", "oncelik_skoru", "tahliye_skoru",
    "yangin_yonu_derece", "yayilma_hizi",
    "yukseklik_metre", "egim_derece", "egim_yonu",
    "sicaklik", "nem", "ruzgar_hizi",
    "guncelleme_zamani",
]


def veritabani_baglan():
    conn = sqlite3.connect("veriler.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bolgeler (
            bolge_id TEXT PRIMARY KEY,
            lat REAL, lon REAL,
            risk_skoru REAL, oncelik_skoru REAL, tahliye_skoru REAL,
            yangin_yonu_derece REAL, yayilma_hizi TEXT,
            yukseklik_metre REAL, egim_derece REAL, egim_yonu TEXT,
            sicaklik REAL, nem REAL, ruzgar_hizi REAL,
            guncelleme_zamani TEXT
        )
    """)
    conn.commit()
    return conn


def bolge_ekle(baglanti, bolge: dict):
    """CREATE + UPDATE (bolge_id zaten varsa üzerine yazar)."""
    yer_tutucular = ", ".join(["?"] * len(SUTUNLAR))
    sutun_adlari = ", ".join(SUTUNLAR)
    baglanti.execute(
        f"INSERT OR REPLACE INTO bolgeler ({sutun_adlari}) VALUES ({yer_tutucular})",
        tuple(bolge.get(sutun) for sutun in SUTUNLAR),
    )
    baglanti.commit()


def bolge_getir(baglanti, bolge_id: str):
    """READ — tek bölge. Yoksa None döner."""
    row = baglanti.execute(
        "SELECT * FROM bolgeler WHERE bolge_id = ?", (bolge_id,)
    ).fetchone()
    return dict(zip(SUTUNLAR, row)) if row else None


def tum_bolgeleri_getir(baglanti):
    """READ — hepsi. Her satırı isimli sözlük (dict) olarak döner."""
    rows = baglanti.execute("SELECT * FROM bolgeler").fetchall()
    return [dict(zip(SUTUNLAR, row)) for row in rows]


def bolge_sil(baglanti, bolge_id: str):
    """DELETE"""
    baglanti.execute("DELETE FROM bolgeler WHERE bolge_id = ?", (bolge_id,))
    baglanti.commit()