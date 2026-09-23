# MusicProject — El Hareketiyle Senfoni

Web kamerasından el hareketlerini okuyup gerçek zamanlı MIDI akor çalan bir
Python uygulaması. Sol el hangi akoru (I–VII, majör/minör) çalacağını
belirler; sağ el ses seviyesini, akor formunu (voicing) ve filtre/tını
eğimini kontrol eder.

## Nasıl çalışır

- **El takibi**: [MediaPipe Hands](https://github.com/google/mediapipe) ile
  iki elin 21 landmark noktası gerçek zamanlı olarak tespit edilir.
- **Sol el → akor seçimi**: açık parmak sayısı/kombinasyonu I–VII arası bir
  gam derecesine, elin yatay eğimi majör/minör'e karşılık gelir.
- **Sağ el → ifade**: dikey konum ses seviyesini (volume), açık parmak
  sayısı akor formunu (triad / 1. çevrim / 7'li / 6'lı), başparmak bas
  oktavını, yatay eğim ise MIDI filtre kesim frekansını (CC74) kontrolü eder.
- **Stabilizasyon**: `ChordStabilizer` ani el titremelerinden kaynaklanan
  yanlış akor tetiklemelerini önlemek için bir "hold time" (100ms) uygular;
  `Smoother` ses/filtre değerlerini üstel ortalamayla yumuşatır.
- **Ses**: `pygame.midi` üzerinden sistemin varsayılan MIDI çıkışına
  (örn. bir DAW, sanal synth veya donanım synth) nota on/off ve CC
  mesajları gönderilir — ses üretimi uygulamanın kendisinde değil, dinlenen
  MIDI cihazında gerçekleşir.
- **Görsel geri bildirim**: OpenCV penceresinde el iskeleti, çalınan akor
  adı, form tipi ve filtre yüzdesi gösterilir; ayrıca sesin şiddetine ve
  filtre eğimine tepki veren animasyonlu "enerji dalgaları" çizilir.

## Gereksinimler

- Python 3.9+
- Bir web kamerası
- Sistemde kayıtlı bir MIDI çıkışı (örn. Windows'ta bir sanal MIDI synth,
  ya da DAW'ın MIDI girişini dinlemesi)

## Kurulum & Çalıştırma

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install opencv-python mediapipe numpy pygame

python main.py
```

Pencere açıldığında sol eli kameraya göster, parmak sayısı/kombinasyonuyla
akor seç; sağ eli ses/form/filtre kontrolü için kullan. Çıkmak için `q`.

## Kontrol Şeması

| El | Hareket | Etki |
|---|---|---|
| Sol | Açık parmak sayısı (1–5) | Akor derecesi I–V |
| Sol | İşaret + serçe parmak (+ başparmak) | VI / VII derecesi |
| Sol | El yatay eğimi | Majör / minör |
| Sağ | Dikey konum | Ses seviyesi |
| Sağ | Açık parmak sayısı | Akor formu (voicing) |
| Sağ | Başparmak | Bas oktavı aç/kapat |
| Sağ | Yatay eğim | Filtre (tını) |
