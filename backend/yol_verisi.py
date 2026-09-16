import logging
import requests

logger = logging.getLogger("ateskes.yollar")

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_HEADERS = {"User-Agent": "AtesKesProject/1.0 (Biz Teknopark on kulucka)"}

# OSM highway etiketini üç kategoriye indirger.
_YOL_TIPI_ESLEME = {
    "motorway": "ana_yol", "trunk": "ana_yol", "primary": "ana_yol",
    "secondary": "tali_yol", "tertiary": "tali_yol",
    "unclassified": "tali_yol", "residential": "tali_yol",
    "track": "orman_yolu", "path": "orman_yolu",
}


def yol_verisi_cek(bbox, limit=150):
    """bbox: (min_lat, min_lon, max_lat, max_lon)

    Döner: [{"osm_id":.., "tip":"ana_yol"|"tali_yol"|"orman_yolu",
             "isim":.., "koordinatlar": [(lat, lon), ...]}, ...]
    Overpass cevap vermezse ya da bölgede yol yoksa: [] (sistem çökmez).
    """
    min_lat, min_lon, max_lat, max_lon = bbox
    sorgu = f"""
    [out:json][timeout:60];
    way["highway"]({min_lat},{min_lon},{max_lat},{max_lon});
    out geom;
    """
    try:
        r = requests.post(_OVERPASS_URL, data={"data": sorgu}, headers=_HEADERS, timeout=90)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error("Overpass yol verisi alinamadi (bbox=%s): %s", bbox, e)
        return []

    try:
        elemanlar = r.json()["elements"]
    except (ValueError, KeyError) as e:
        logger.error("Overpass yaniti parse edilemedi: %s", e)
        return []

    sonuc = []
    for e in elemanlar[:limit]:
        highway = e.get("tags", {}).get("highway", "")
        tip = _YOL_TIPI_ESLEME.get(highway)
        if tip is None:
            continue  # tanımadığımız highway tipini (steps, footway vb.) atla
        geometri = e.get("geometry", [])
        if len(geometri) < 2:
            continue  # tek noktalı/geçersiz segment
        sonuc.append({
            "osm_id": e.get("id"),
            "tip": tip,
            "isim": e.get("tags", {}).get("name", "isimsiz"),
            "koordinatlar": [(nokta["lat"], nokta["lon"]) for nokta in geometri],
        })

    logger.info("Overpass: %d yol segmenti bulundu (bbox=%s)", len(sonuc), bbox)
    return sonuc