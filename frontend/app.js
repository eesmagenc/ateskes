
const map = L.map('map').setView([37.2153, 28.3636], 10);


L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=cb1_31bb_1_b53b43996e67049c65f76f0c', {
  attribution: '&copy; OpenStreetMap katkıda bulunanlar &copy; CARTO',
  subdomains: 'abcd',
  maxZoom: 19
}).addTo(map);


function bolgeEkVerileriniUret(bolge) {

  bolge.yangin_yonu_derece = Math.floor(Math.random() * 360);
  bolge.yayilma_hizi = ["yavas", "orta", "hizli"][Math.floor(Math.random() * 3)];
  bolge.yukseklik_metre = Math.floor(Math.random() * 600) + 50;
  bolge.egim_derece = +(Math.random() * 30 + 2).toFixed(1);

  const guncelleme = new Date();

  guncelleme.setMinutes(guncelleme.getMinutes() - Math.floor(Math.random() * 30));
  bolge.guncelleme_zamani = guncelleme.toISOString();
}


function riskKategori(risk) {
  if (typeof risk !== "number" || Number.isNaN(risk)) {
    console.warn("risk_skoru eksik/geçersiz geldi, 'veri-yok' olarak işaretlendi:", risk);
    return "veri-yok";
  }
  if (risk < 0.2) return "dusuk";
  if (risk < 0.5) return "orta";
  if (risk < 0.8) return "yuksek";
  return "kritik";
}


function riskBoyutu(kategori) {
  if (kategori === "dusuk") return 14;
  if (kategori === "orta") return 16;
  if (kategori === "yuksek") return 17;
  return 18; // kritik — artık en büyük
}


function ruzgarYonuMetni(derece) {
  const yonler = ["K", "KD", "D", "GD", "G", "GB", "B", "KB"];
  const index = Math.round(derece / 45) % 8;
  return `${yonler[index]} (${derece}°)`;
}

function yayilmaHiziMetni(hiz) {
  const esleme = {
    yavas: "Yavaş",
    orta: "Orta",
    hizli: "Hızlı"
  };
  return esleme[hiz] ?? "—";
}


const clusterGrup = L.markerClusterGroup({
  iconCreateFunction: function (cluster) {
    const sayi = cluster.getChildCount();
    // Cluster içindeki markerların risk skorlarına bakıp en yüksek olanı bul
    const enYuksekRisk = Math.max(
      ...cluster.getAllChildMarkers().map(m => m.options.riskSkoru)
    );
    const kategori = riskKategori(enYuksekRisk);

    return L.divIcon({
      className: "",
      html: `<div class="cluster-marker ${kategori}"><span>${sayi}</span></div>`,
      iconSize: [40, 40],
      iconAnchor: [20, 20]
    });
  },
  // Hover'da gösterilen kapsama alanının stili — dolgu şeffaf, sadece
  // ince mavi bir kenar çizgisi kalsın.
  polygonOptions: {
    fillColor: "#94a3b8",
    fillOpacity: 0.12,
    color: "#94a3b8",
    weight: 1.5,
    opacity: 0.7
  }
});


const tumMarkerlar = [];

function geojsonDonustur(bolgeler) {
  return {
    type: "FeatureCollection",
    features: bolgeler.map(b => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [b.lon, b.lat] },
      properties: {
        bolge_id: b.bolge_id,
        ad: b.ad,
        risk_skoru: b.risk_skoru,
        oncelik_skoru: b.oncelik_skoru,
        tahliye_skoru: b.tahliye_skoru,
        // hava_durumu: Ay 2 / Hafta 5'te kontrata girecek, şekli netleşince eklenecek.
        yangin_yonu_derece: b.yangin_yonu_derece,
        yayilma_hizi: b.yayilma_hizi,
        yukseklik_metre: b.yukseklik_metre,
        egim_derece: b.egim_derece,
        guncelleme_zamani: b.guncelleme_zamani
      }
    }))
  };
}


function bolgeleriHaritayaYukle(bolgeler) {
  const geojson = geojsonDonustur(bolgeler);

  const geojsonKatmani = L.geoJSON(geojson, {
    pointToLayer: function (feature, latlng) {
      const props = feature.properties;
      const kategori = riskKategori(props.risk_skoru);
      const boyut = riskBoyutu(kategori);

      const icon = L.divIcon({
        className: "",
        html: `<div class="risk-marker ${kategori}"></div>`,
        iconSize: [boyut, boyut],
        iconAnchor: [boyut / 2, boyut / 2]
      });

      const marker = L.marker(latlng, {
        icon,
        riskSkoru: props.risk_skoru
      });


      marker.bindPopup(() => popupIcerigi(props, kategori), {
        className: `popup-${kategori}`,
        maxWidth: 360
      });

      tumMarkerlar.push({ marker, kategori, ozellikler: props });
      return marker;
    }
  });

  geojsonKatmani.eachLayer(layer => clusterGrup.addLayer(layer));

  const heatPuanlari = bolgeler
    .filter(b => typeof b.risk_skoru === "number")
    .map(b => [b.lat, b.lon, b.risk_skoru]);
  heatmapKatmani.setLatLngs(heatPuanlari);

  statSeridiniGuncelle();
  filtreSayilariniGuncelle();

  setTimeout(() => {
    map.invalidateSize();
  }, 100);
}


function filtreSayilariniGuncelle() {
  const sayilar = { yuksek: 0, kritik: 0, orta: 0, dusuk: 0, "veri-yok": 0 };
  const gorunenMarkerlar = tumMarkerlar.filter(({ marker }) => clusterGrup.hasLayer(marker));
  gorunenMarkerlar.forEach(({ kategori }) => sayilar[kategori]++);

  document.getElementById("sayi-yuksek").textContent = sayilar.yuksek;
  document.getElementById("sayi-kritik").textContent = sayilar.kritik;
  document.getElementById("sayi-orta").textContent = sayilar.orta;
  document.getElementById("sayi-dusuk").textContent = sayilar.dusuk;
}


function statSeridiniGuncelle() {
  const toplam = tumMarkerlar.length;
  const kritikSayisi = tumMarkerlar.filter(({ kategori }) => kategori === "kritik").length;

  document.getElementById("stat-toplam").textContent = toplam;
  document.getElementById("stat-kritik").textContent = kritikSayisi;
}


fetch(BACKEND_URL)
  .then(r => {
    if (!r.ok) throw new Error(`Backend ${r.status} döndü`);
    return r.json();
  })
  .then(veri => {
    console.log(" Gerçek backend verisi kullanılıyor:", BACKEND_URL);
    bolgeleriHaritayaYukle(veri);
  })
  .catch(err => {
    console.warn(" Backend'e ulaşılamadı, mock veri kullanılıyor:", err.message);

    mockBolgeler.forEach(bolgeEkVerileriniUret);
    bolgeleriHaritayaYukle(mockBolgeler);
  });
// --- Isı Haritası (Güncellenmiş renk geçişleri) ---
const heatmapKatmani = L.heatLayer([], {
  radius: 50,
  blur: 50,
  maxZoom: 10,
  minOpacity: 0.35,
  max: 1.0,
  gradient: {
    0.1: "#3b82f6", // Düşük risk: hafif ton
    0.4: "#eab308", // Orta risk: canlı sarı
    0.7: "#f97316", // Yüksek risk: belirgin turuncu
    0.95: "#dc2626" // Kritik risk: derin parlayan kırmızı
  }
});

// --- Yollar (Canvas Görseliyle Tam Uyumlu Mock Veri) ---
const yolKatmani = L.layerGroup();
const mockYollar = [
  // Ana yol: Milas → Muğla merkez → Köyceğiz → Ortaca (D330 hattı, çok noktalı yumuşak güzergah)
  {
    koordinatlar: [
      [37.3164, 27.7847], [37.29, 27.92], [37.26, 28.05], [37.24, 28.18],
      [37.2153, 28.3636], [37.15, 28.42], [37.06, 28.52], [36.98, 28.62],
      [36.9633, 28.6889], [36.92, 28.70], [36.87, 28.71], [36.8394, 28.7594]
    ],
    tip: "ana"
  },
  // Ana yol: Bodrum → Muğla merkez → Fethiye (D400 hattı)
  {
    koordinatlar: [
      [37.0344, 27.4305], [37.08, 27.65], [37.12, 27.85], [37.16, 28.05],
      [37.2153, 28.3636], [37.10, 28.55], [36.95, 28.70], [36.80, 28.85],
      [36.6217, 29.1164]
    ],
    tip: "ana"
  },
  // Orman yolu: Milas → Marmaris iç hat
  {
    koordinatlar: [
      [37.3164, 27.7847], [37.20, 27.95], [37.05, 28.10],
      [36.95, 28.18], [36.8550, 28.2745]
    ],
    tip: "orman"
  },
  // Orman yolu: Köyceğiz → Datça iç hat
  {
    koordinatlar: [
      [36.9633, 28.6889], [36.85, 28.30], [36.78, 27.95], [36.7300, 27.6889]
    ],
    tip: "orman"
  }
];

// Plan üç kategori öngörüyor: ana yol / tali yol / orman yolu.
// Esma'nın backend'inin "tip" alanında hangi tam string'leri kullandığını
// henüz bilmiyoruz — bu fonksiyon hem Türkçe (ana/tali/orman) hem OSM'in
// kendi highway isimlerini (primary/secondary/track gibi) kabaca kategorize
// ediyor. Esma'dan kesin değerler gelince bu eşleştirme netleştirilecek.
function yolKategorisi(tip) {
  const deger = (tip || "").toLowerCase();
  if (["ana", "primary", "trunk", "motorway"].includes(deger)) return "ana";
  if (["tali", "secondary", "tertiary"].includes(deger)) return "tali";
  return "orman"; // track, unclassified, service, orman, vb. — bilinmeyen her şey
}

function yolCiz(yol) {
  const kategori = yolKategorisi(yol.tip);

  const stiller = {
    ana:   { renk: "#3b82f6", kalinlik: 1.8, kesikli: null },
    tali:  { renk: "#f59e0b", kalinlik: 1.5, kesikli: "3 3" },
    orman: { renk: "#8b5e3c", kalinlik: 1.2, kesikli: "5 5" }
  };
  const stil = stiller[kategori];

  // İnce, hafif koyu dış çizgi — belirginlik için, kalınlığı abartmadan
  L.polyline(yol.koordinatlar, {
    color: "#101820",
    weight: stil.kalinlik + 1.5,
    opacity: 0.6,
    lineCap: "round",
    lineJoin: "round",
    smoothFactor: 1.5
  }).addTo(yolKatmani);

  // Asıl ince renkli çizgi
  L.polyline(yol.koordinatlar, {
    color: stil.renk,
    weight: stil.kalinlik,
    opacity: 0.9,
    dashArray: stil.kesikli,
    lineCap: "round",
    lineJoin: "round",
    smoothFactor: 1.5
  }).addTo(yolKatmani);
}

function yollariGetir() {
  // /yollar zorunlu bounding box parametreleri istiyor (min_lat, min_lon,
  // max_lat, max_lon) — Muğla/Bodrum bölgesini kapsayan bir kutu veriyoruz.
  const yolUrl = BACKEND_URL.replace("/bolgeler", "/yollar") +
    "?min_lat=36.60&min_lon=27.30&max_lat=37.35&max_lon=29.15&egim_ekle=false";

  fetch(yolUrl)
    .then((r) => {
      if (!r.ok) throw new Error(`Backend ${r.status} döndü`);
      return r.json();
    })
    .then((yanit) => {
      console.log("Gerçek yol verisi kullanılıyor:", yolUrl);
      // Gerçek şekil: { toplam_yol, veri: [{ koordinatlar, tip, egim_derece }] }
      // "tip" alanının gerçek değerlerini (ana/orman mi, başka bir
      // sınıflandırma mı) Esma'dan teyit almadan kesin eşleştiremiyoruz,
      // şimdilik "ana" dışındaki her şeyi "orman" sayıyoruz.
      const gercekYollar = (yanit.veri || []).map((yol) => ({
        koordinatlar: yol.koordinatlar,
        tip: yol.tip
      }));
      if (gercekYollar.length === 0) {
        throw new Error("Yol verisi boş döndü");
      }
      gercekYollar.forEach(yolCiz);
    })
    .catch((err) => {
      console.warn("Yol verisine ulaşılamadı, mock veri kullanılıyor:", err.message);
      mockYollar.forEach(yolCiz);
    });
}

yollariGetir();

// --- Rota Vurgusu (Sultan'ın Hafta 3 A* notebook'undan) ---
// Senaryo: Gürece (yangın başlangıcı) -> Bodrum Amerikan Hastanesi (tahliye hedefi)
// A*, eğim cezası sayesinde kısa/dik rota yerine uzun/güvenli rotayı seçti.
const rotaKatmani = L.layerGroup();

const onerilenRota = [
  [37.039538, 27.322432], // yangin_baslangic — Gürece köy
  [37.041, 27.360],       // kavsak_duz
  [37.040, 27.395],       // kavsak_orta
  [37.039939, 27.428962]  // hastane_hedef — Bodrum Amerikan Hastanesi
];

// Koyu dış çizgi — belirginlik için
L.polyline(onerilenRota, {
  color: "#0a2e33",
  weight: 3,
  opacity: 0.7,
  lineCap: "round",
  lineJoin: "round"
}).addTo(rotaKatmani);

// Asıl turkuaz rota çizgisi
L.polyline(onerilenRota, {
  color: "#38bdf8",
  weight: 2,
  opacity: 0.9,
  lineCap: "round",
  lineJoin: "round",
  className: "rota-akis-cizgisi"
}).addTo(rotaKatmani);

// Başlangıç ve hedef noktalarını işaretle
// Rota başlangıç/bitiş noktalarına AYRI marker koymuyoruz — bu noktalar
// zaten birer risk bölgesi (kırmızı/sarı/yeşil marker olarak haritada
// duruyor). Sadece o iki noktayı ince bir turkuaz halkayla vurguluyoruz,
// "bu nokta aynı zamanda rota ucu" mesajını risk rengini bozmadan veriyoruz.
[onerilenRota[0], onerilenRota[onerilenRota.length - 1]].forEach((nokta) => {
  L.circleMarker(nokta, {
    radius: 3,
    color: "#22d3ee",
    weight: 1.5,
    fillOpacity: 1,
  }).addTo(rotaKatmani);
});

// --- Katman Grupları ve Haritaya Başlangıçta Ekleme ---
const riskNoktalari = clusterGrup; 
const kritikAlanlar = L.layerGroup(); // Şimdilik boş / yakında

// Sadece Risk Noktaları varsayılan açık; Yollar, Heatmap ve Rota
// kullanıcı Katmanlar panelinden manuel açana kadar haritaya
// eklenmiyor — ilk açılışta sade bir görünüm için.
riskNoktalari.addTo(map);

// --- Katman checkbox'ları (artık filtre panelinin içinde) ---
const katmanEslesme = {
  "risk-noktalari": riskNoktalari,
  "yollar": yolKatmani,
  "heatmap": heatmapKatmani,
  "rota": rotaKatmani
};

document.querySelectorAll('#filtre-paneli input[data-katman]').forEach((checkbox) => {
  checkbox.addEventListener("change", () => {
    const katman = katmanEslesme[checkbox.dataset.katman];
    if (!katman) return;
    if (checkbox.checked) map.addLayer(katman);
    else map.removeLayer(katman);
  });
});

// Filtre panelini aç/kapat
const filtreToggle = document.getElementById("filtre-toggle");
const filtrePaneli = document.getElementById("filtre-paneli");

filtreToggle.addEventListener("click", () => {
  filtrePaneli.classList.toggle("acik");
});

// Popup açık mı takibi — dışarı tıklama önceliğini belirlemek için kullanılıyor.
let popupAcikMi = false;

// Dışarı tıklama: capture fazında çalışıyor ki Leaflet kendi popup kapatma
// mantığını çalıştırmadan ÖNCE biz "popup açık mıydı" bilgisini yakalayalım.
document.addEventListener('click', (e) => {
  // Filtre paneli, dashboard paneli veya bunların toggle butonlarına tıklandıysa dokunma
  if (
    filtrePaneli.contains(e.target) ||
    filtreToggle.contains(e.target) ||
    dashboardPaneli.contains(e.target) ||
    dashboardToggle.contains(e.target)
  ) return;

  // Popup içine tıklandıysa dokunma
  if (e.target.closest('.leaflet-popup')) return;

  // Marker'a (veya cluster'a) tıklandıysa dokunma —
  // popup kendi açılsın, panel açıksa öylece kalsın.
  if (e.target.closest('.leaflet-marker-icon')) return;

  // Popup açıksa: SADECE popup'ı kapat, panele dokunma.
  if (popupAcikMi) {
    map.closePopup();
    return;
  }

  // Popup kapalıysa: paneller açıksa kapat.
  filtrePaneli.classList.remove('acik');
  dashboardPaneli.classList.remove('acik');
}, true);

function filtreleriUygula() {
  const checkboxlar = document.querySelectorAll('#filtre-paneli input[data-risk]');
  const aktifKategoriler = [];

  checkboxlar.forEach(cb => {
    if (cb.checked) aktifKategoriler.push(cb.dataset.risk);
  });

  clusterGrup.clearLayers();

  tumMarkerlar.forEach(({ marker, kategori }) => {
    if (aktifKategoriler.includes(kategori)) {
      clusterGrup.addLayer(marker);
    }
  });

  filtreSayilariniGuncelle();
}


document.querySelectorAll('#filtre-paneli input[data-risk]').forEach(cb => {
  cb.addEventListener('change', filtreleriUygula);
});
function popupIcerigi(bolge, kategori) {
  const riskMetni = { yuksek: 'YÜKSEK', kritik: 'KRİTİK', orta: 'ORTA', dusuk: 'DÜŞÜK' };
  const riskYuzde = Math.round(bolge.risk_skoru * 100);
  const altBaslikMetni = {
    yuksek: 'Tahliye önceliği yüksek · Kritik alanlara yakın',
    kritik: 'Tahliye önceliği çok yüksek · Yakından izlenmeli',
    orta: 'Yakından izlenmeli · Müdahale hazırlığı önerilir',
    dusuk: 'Şu an düşük öncelikli · Rutin takip yeterli'
  };
  const headerClass = kategori === 'orta' ? 'risk-orta'
  : kategori === 'dusuk' ? 'risk-dusuk'
  : kategori === 'kritik' ? 'risk-kritik'
  : kategori === 'yuksek' ? 'risk-yuksek'
  : '';
  const progressClass = kategori;

  const dakikaOnce = bolge.guncelleme_zamani
    ? Math.floor((new Date() - new Date(bolge.guncelleme_zamani)) / 60000)
    : null;
  const zamanMetni = dakikaOnce == null ? '' : (dakikaOnce < 1 ? 'Az önce' : `${dakikaOnce} dk önce`);


  const araziHTML = `
  <div class="saha-kosullari">
    <h4>Saha Koşulları</h4>
    <div class="saha-grid">
      <div class="saha-item">
        <div class="saha-ust">
          <i data-lucide="compass" class="saha-icon"></i>
          <span class="saha-value">${bolge.yangin_yonu_derece != null ? ruzgarYonuMetni(bolge.yangin_yonu_derece) : '—'}</span>
        </div>
        <span class="saha-label">Rüzgar Yönü</span>
      </div>
      <div class="saha-item">
        <div class="saha-ust">
          <i data-lucide="wind" class="saha-icon"></i>
          <span class="saha-value">${yayilmaHiziMetni(bolge.yayilma_hizi)}</span>
        </div>
        <span class="saha-label">Yayılma Hızı</span>
      </div>
      <div class="saha-item saha-alt-satir">
        <div class="saha-ust">
          <i data-lucide="mountain" class="saha-icon"></i>
          <span class="saha-value">${bolge.yukseklik_metre ?? '—'} m</span>
        </div>
        <span class="saha-label">Yükseklik</span>
      </div>
      <div class="saha-item saha-alt-satir">
        <div class="saha-ust">
          <i data-lucide="triangle" class="saha-icon"></i>
          <span class="saha-value">${bolge.egim_derece ?? '—'}°</span>
        </div>
        <span class="saha-label">Eğim</span>
      </div>
    </div>
  </div>
`;

  return `
    <div class="custom-popup">
      <div class="popup-header ${headerClass}">
  <div class="popup-header-top">
    <span class="header-icon-wrap"><i data-lucide="flame" class="header-icon"></i></span>
      <h3>${bolge.ad || bolge.bolge_id}</h3>
  </div>
  <span class="risk-badge">${riskMetni[kategori]} · %${riskYuzde}</span>
  <p class="popup-subtitle">${altBaslikMetni[kategori]}</p>
</div>

      <div class="popup-body">
        <div class="risk-scores">
          <div class="score-item">
            <div class="score-label">
              <span>Risk Skoru</span>
              <span class="score-value ${progressClass}">${(bolge.risk_skoru * 100).toFixed(0)}%</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill ${progressClass}" style="width: ${bolge.risk_skoru * 100}%"></div>
            </div>
          </div>

          <div class="score-item">
            <div class="score-label">
              <span>Öncelik Skoru</span>
              <span class="score-value ${progressClass}">${(bolge.oncelik_skoru * 100).toFixed(0)}%</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill ${progressClass}" style="width: ${bolge.oncelik_skoru * 100}%"></div>
            </div>
          </div>

          <div class="score-item">
            <div class="score-label">
              <span>Tahliye Skoru</span>
              <span class="score-value ${progressClass}">${(bolge.tahliye_skoru * 100).toFixed(0)}%</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill ${progressClass}" style="width: ${bolge.tahliye_skoru * 100}%"></div>
            </div>
          </div>
        </div>

        ${araziHTML}

        <div class="last-update">${zamanMetni}</div>
      </div>
    </div>
  `;
}

// Popup her açıldığında Lucide ikonlarını render et + açık olduğunu işaretle
map.on('popupopen', () => {
  popupAcikMi = true;
  lucide.createIcons();
});

// Popup kapandığında bayrağı sıfırla
map.on('popupclose', () => {
  popupAcikMi = false;
});
window.addEventListener('load', () => {
  setTimeout(() => {
    map.invalidateSize();
  }, 200);
  lucide.createIcons();
});

let dashChart = null;

function istatistikleriGuncelle(istatistik) {
  document.getElementById("dash-kritik-sayi").textContent =
    tumMarkerlar.filter(m => m.kategori === "kritik").length;
  document.getElementById("dash-ortalama-risk").textContent =
    Math.round(istatistik.ortalama_risk * 100) + "%";

  const liste = document.getElementById("dash-kritik-liste");
  liste.innerHTML = "";
  istatistik.en_yuksek_riskli_3.forEach((bolge) => {
    const kategori = riskKategori(bolge.risk_skoru);
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="dash-liste-dot ${kategori}"></span>
      <span class="dash-liste-ad">${bolge.ad ?? bolge.bolge_id}</span>
      <strong class="dash-liste-yuzde ${kategori}">%${Math.round(bolge.risk_skoru * 100)}</strong>
    `;
    liste.appendChild(li);
  });

  dashGrafigiCiz();
}

function dashGrafigiCiz() {
  const sayilar = { kritik: 0, yuksek: 0, orta: 0, dusuk: 0 };
  tumMarkerlar.forEach(({ kategori }) => {
    if (sayilar[kategori] !== undefined) sayilar[kategori]++;
  });

  const toplam = sayilar.kritik + sayilar.yuksek + sayilar.orta + sayilar.dusuk;
  document.getElementById("dash-chart-toplam").innerHTML = `${toplam}<br><span>Bölge</span>`;

  document.getElementById("rs-dusuk").textContent = `${sayilar.dusuk} (%${toplam ? Math.round(sayilar.dusuk / toplam * 100) : 0})`;
  document.getElementById("rs-orta").textContent = `${sayilar.orta} (%${toplam ? Math.round(sayilar.orta / toplam * 100) : 0})`;
  document.getElementById("rs-yuksek").textContent = `${sayilar.yuksek} (%${toplam ? Math.round(sayilar.yuksek / toplam * 100) : 0})`;
  document.getElementById("rs-kritik").textContent = `${sayilar.kritik} (%${toplam ? Math.round(sayilar.kritik / toplam * 100) : 0})`;

  const ctx = document.getElementById("dash-chart");
  if (dashChart) dashChart.destroy();

  dashChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Kritik", "Yüksek", "Orta", "Düşük"],
      datasets: [{
        data: [sayilar.kritik, sayilar.yuksek, sayilar.orta, sayilar.dusuk],
        backgroundColor: ["#e74c3c", "#e8590c", "#f1c40f", "#2ecc71"],
        borderColor: "#141414",
        borderWidth: 2
      }]
    },
    options: {
      cutout: "68%",
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.label}: ${ctx.raw} bölge`
          }
        }
      }
    }
  });
}

const dashboardToggle = document.getElementById("dashboard-toggle");
const dashboardPaneli = document.getElementById("dashboard-paneli");

function istatistikleriGetir() {
  const istatistikUrl = BACKEND_URL.replace("/bolgeler", "/istatistikler");

  fetch(istatistikUrl)
    .then((r) => {
      if (!r.ok) throw new Error(`Backend ${r.status} döndü`);
      return r.json();
    })
    .then((veri) => {
      console.log("Gerçek istatistik verisi kullanılıyor:", istatistikUrl);
      istatistikleriGuncelle(veri);
    })
    .catch((err) => {
      console.warn("İstatistik verisine ulaşılamadı, mock veri kullanılıyor:", err.message);
      istatistikleriGuncelle(mockIstatistikler);
    });
}

dashboardToggle.addEventListener("click", () => {
  dashboardPaneli.classList.toggle("acik");
  istatistikleriGetir();
  lucide.createIcons();
});