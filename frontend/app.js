
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
  if (risk < 0.3) return "dusuk";
  if (risk < 0.6) return "orta";
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

map.addLayer(clusterGrup);

const legend = L.control({ position: "bottomright" });

legend.onAdd = function () {
  const div = L.DomUtil.create("div", "legend");
    div.innerHTML = `
    <h4>Risk Seviyesi</h4>
    <div class="legend-item"><span class="legend-dot kritik"></span> Kritik</div>
    <div class="legend-item"><span class="legend-dot yuksek"></span> Yüksek</div>
    <div class="legend-item"><span class="legend-dot orta"></span> Orta</div>
    <div class="legend-item"><span class="legend-dot dusuk"></span> Düşük</div>
    
    
    
  `;
  return div;
};

legend.addTo(map);

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
  // Filtre paneli veya toggle butonuna tıklandıysa dokunma
  if (filtrePaneli.contains(e.target) || filtreToggle.contains(e.target)) return;

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

  // Popup kapalıysa: panel açıksa kapat.
  filtrePaneli.classList.remove('acik');
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
        <span class="saha-label">Rüzgar</span>
      </div>
      <div class="saha-item">
        <div class="saha-ust">
          <i data-lucide="wind" class="saha-icon"></i>
          <span class="saha-value">${bolge.yayilma_hizi ?? '—'}</span>
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
});
