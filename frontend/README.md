# AteşKes — Frontend

Muğla bölgesi için GIS tabanlı yangın risk haritası. Leaflet.js ile
oluşturulmuş, vanilla HTML/CSS/JavaScript (build sistemi yok).

## Kurulum

1. Bu klasörü (`frontend/`) bir Live Server ile aç (VS Code Live Server
   eklentisi önerilir).
2. `config.example.js` dosyasını `config.js` olarak kopyala, gerçek
   CARTO key ve backend URL'ini gir (key ekip içi paylaşılıyor, Sude'ye
   sor).

## Özellikler

- Leaflet.js harita, GeoJSON tabanlı risk bölgesi gösterimi
- Risk seviyesine göre filtreleme (Kritik/Yüksek/Orta/Düşük)
- Katman yönetimi: Risk Noktaları, Yollar, Isı Haritası, Önerilen Rota
- Chart.js ile özet istatistik paneli
- Mock veri desteği — backend erişilemezse otomatik devreye girer

## Performans Stratejisi

Mevcut MVP'de iki farklı görselleştirme yöntemi var:
- **Marker Clustering** — az sayıda bölge (örn. <100) için, her noktayı
  ayrı ayrı görmek isteyen kullanıcılar için idealdir.
- **Heatmap** — çok sayıda bölge (örn. 100+) olduğunda, tek tek marker
  render etmek performans sorunu yaratabilir; heatmap tek bir canvas
  katmanı olduğu için çok daha hafiftir.

Şu an kullanıcı ikisi arasında Katmanlar panelinden manuel geçiş
yapabiliyor. İleride (Ay 5, "Performans ve Güvenilirlik" haftasında)
bu geçiş otomatikleştirilebilir: bölge sayısı belirli bir eşiği
(örn. 150) geçtiğinde, sistem otomatik olarak heatmap moduna geçip
kullanıcıyı bilgilendirebilir.

## Bilinen Eksikler

- `/yollar`'daki yol tipi (`tip`) eşleştirmesi geçici — Esma'nın gerçek
  OSM highway sınıflandırmasını teyit etmesi bekleniyor.
- Rüzgar/yayılma yönü (`yangin_yonu_derece`) şu an ham rüzgar verisi;
  gerçek yayılma yönü hesaplaması (Sultan) henüz backend'e eklenmedi.