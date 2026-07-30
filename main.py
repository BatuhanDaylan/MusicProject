import cv2
import mediapipe as mp
import math
import numpy as np
import pygame.midi
import time

# ==========================================
# 1. YARDIMCI SINIFLAR
# ==========================================

class Smoother:
    def __init__(self, smoothing_factor=0.2):
        self.value = None
        self.factor = smoothing_factor

    def update(self, new_value):
        if self.value is None: self.value = new_value
        else: self.value = (self.value * (1 - self.factor)) + (new_value * self.factor)
        return self.value

class ChordStabilizer:
    def __init__(self, hold_time_ms=100):
        self.hold_time = hold_time_ms / 1000.0
        self.stable_state = None
        self.candidate_state = None
        self.candidate_since = 0

    def update(self, raw_state):
        if raw_state != self.candidate_state:
            self.candidate_state = raw_state
            self.candidate_since = time.time()
        
        if (time.time() - self.candidate_since) >= self.hold_time:
            self.stable_state = self.candidate_state
            
        return self.stable_state

# ==========================================
# 2. SES MOTORU
# ==========================================

class SoundEngine:
    def __init__(self):
        pygame.midi.init()
        try:
            self.player = pygame.midi.Output(pygame.midi.get_default_output_id(), 0)
            self.player.set_instrument(89) # 89: Warm Pad
            self.midi_active = True
            print("[BİLGİ] MIDI Motoru başarıyla çalıştırıldı.")
        except Exception as e:
            print(f"[HATA] MIDI Başlatılamadı: {e}")
            self.midi_active = False
            
        self.aktif_notalar = set()
        self.tonic_midi = 60 # C (Do)

        self.degree_semitones = {"I": 0, "II": 2, "III": 4, "IV": 5, "V": 7, "VI": 9, "VII": 11}
        
        # Roma rakamlarını okunabilir nota isimlerine eşleyen sözlük eklendi
        self.akor_isimleri = {
            "I": "Do (C)", "II": "Re (D)", "III": "Mi (E)", 
            "IV": "Fa (F)", "V": "Sol (G)", "VI": "La (A)", "VII": "Si (B)"
        }

    def play_chord(self, chord_roman, is_major, voicing_idx, octave_drop, volume, tilt):
        if not self.midi_active: return

        # Ana Sesi (Volume) MIDI'ye gönder
        vol_midi = int(np.clip(volume * 127, 0, 127))
        self.player.write_short(0xB0, 7, vol_midi)
        
        # Filtreyi (Tilt) MIDI'ye gönder
        filter_midi = int(np.interp(tilt, [-1, 1], [30, 127]))
        self.player.write_short(0xB0, 74, filter_midi)

        hedef_notalar = set()
        if chord_roman in self.degree_semitones and vol_midi > 0:
            kok_nota = self.tonic_midi + self.degree_semitones[chord_roman]
            if octave_drop: kok_nota -= 12 

            third = 4 if is_major else 3
            fifth = 7 if (is_major or chord_roman != "VII") else 6 
            
            if voicing_idx == 1: 
                hedef_notalar = {kok_nota, kok_nota + third, kok_nota + fifth}
            elif voicing_idx == 2: 
                hedef_notalar = {kok_nota + third, kok_nota + fifth, kok_nota + 12}
            elif voicing_idx == 3: 
                seventh = 11 if is_major else 10
                hedef_notalar = {kok_nota, kok_nota + third, kok_nota + fifth, kok_nota + seventh}
            elif voicing_idx == 4: 
                ext = 10 if is_major else 9
                hedef_notalar = {kok_nota, kok_nota + third, kok_nota + fifth, kok_nota + ext}

        for n in self.aktif_notalar - hedef_notalar:
            self.player.note_off(n, 127)
            
        if vol_midi > 5:
            for n in hedef_notalar - self.aktif_notalar:
                # Notalar artık maksimum Velocity (127) ile vuruluyor, gürlük dinamik olarak CC7 ile sağlanıyor.
                self.player.note_on(n, 127)
                
        self.aktif_notalar = hedef_notalar

    def close(self):
        if self.midi_active:
            for n in self.aktif_notalar: self.player.note_off(n, 127)
            del self.player
        pygame.midi.quit()

# ==========================================
# 3. GÖRÜNTÜ İŞLEME
# ==========================================

class HandDetector:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7)
    
    def is_finger_extended(self, lm, tip_idx, pip_idx):
        return lm[tip_idx].y < lm[pip_idx].y

    def is_thumb_extended(self, lm, handedness):
        if handedness == "Right": return lm[4].x > lm[3].x
        else: return lm[4].x < lm[3].x

    def get_tilt(self, lm, handedness):
        min_x = min(lm[9].x, lm[13].x)
        max_x = max(lm[9].x, lm[13].x)
        wrist_x = lm[0].x
        
        tilt = 0
        if wrist_x < min_x: tilt = (wrist_x - min_x) / 0.12
        elif wrist_x > max_x: tilt = (wrist_x - max_x) / 0.12
        
        tilt = max(-1.0, min(1.0, tilt))
        return -tilt if handedness == "Right" else tilt

    def process_frame(self, frame):
        results = self.hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        left_hand, right_hand = None, None
        
        if results.multi_hand_landmarks:
            for lm, hand_type in zip(results.multi_hand_landmarks, results.multi_handedness):
                label = "Left" if hand_type.classification[0].label == "Right" else "Right" 
                
                points = lm.landmark
                if label == "Left": left_hand = points
                else: right_hand = points
                
                mp.solutions.drawing_utils.draw_landmarks(frame, lm, self.mp_hands.HAND_CONNECTIONS)
                
        return frame, left_hand, right_hand

# ==========================================
# 4. GÖRSEL EFEKTLER
# ==========================================

def draw_energy_waves(frame, volume, tilt, chord_roman, is_major):
    if volume < 0.05 or chord_roman is None: return

    h, w = frame.shape[:2]
    center_y = h - 80
    
    colors = {
        "I": (61, 161, 232), "II": (120, 50, 210), "III": (150, 40, 180),
        "IV": (40, 210, 240), "V": (30, 120, 245), "VI": (40, 40, 230), "VII": (250, 200, 100)
    }
    b, g, r = colors.get(chord_roman, (150, 150, 150))
    if not is_major: 
        b, g, r = int(b*0.6), int(g*0.6), int(r*0.6) 
        
    thickness = max(1, int(volume * 10))
    time_sec = time.time() * 3
    chaos = (tilt + 1) / 2
    
    x_coords = np.arange(0, w, 15)
    
    for i in range(3):
        base_sine = np.sin(x_coords * 0.01 + time_sec + (i * 0.5)) * 30
        noise = (np.random.rand(len(x_coords)) - 0.5) * 40 * chaos
        y_coords = center_y + base_sine + noise + (i * 15 - 15)
        
        pts = np.vstack((x_coords, y_coords)).astype(np.int32).T
        cv2.polylines(frame, [pts], False, (b, g, r), thickness, cv2.LINE_AA)

# ==========================================
# 5. ANA DÖNGÜ
# ==========================================

def main():
    cap = cv2.VideoCapture(0)
    cap.set(3, 1280); cap.set(4, 720)
    
    detector = HandDetector()
    audio = SoundEngine()
    chord_stab = ChordStabilizer(100) 
    
    vol_smoother = Smoother(0.2)
    tilt_smoother = Smoother(0.2)
    
    while True:
        success, frame = cap.read()
        if not success: break
        frame = cv2.flip(frame, 1) 
        
        frame, left_lm, right_lm = detector.process_frame(frame)
        
        # --- SOL EL MANTIĞI ---
        raw_chord = None
        raw_is_major = True
        
        if left_lm:
            thumb = detector.is_thumb_extended(left_lm, "Left")
            index = detector.is_finger_extended(left_lm, 8, 6)
            middle = detector.is_finger_extended(left_lm, 12, 10)
            ring = detector.is_finger_extended(left_lm, 16, 14)
            pinky = detector.is_finger_extended(left_lm, 20, 18)
            
            if index and pinky and not middle and not ring:
                raw_chord = "VII" if thumb else "VI"
            else:
                count = sum([thumb, index, middle, ring, pinky])
                roman_map = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
                raw_chord = roman_map.get(count, None)
                
            raw_is_major = detector.get_tilt(left_lm, "Left") >= 0
            
        stable_state = chord_stab.update((raw_chord, raw_is_major))
        curr_chord, curr_major = stable_state if stable_state else (None, True)

        # --- SAĞ EL MANTIĞI ---
        vol, tilt, voicing_idx, octave_drop = 0.0, 0.0, 1, False
        
        if right_lm:
            # Ses hassasiyeti ergonomik hale getirildi:
            # 0.45 (Ekranın tam ortası) = %100 Ses
            # 0.85 (Ekranın alt kısmı) = %0 Ses (Sessiz)
            raw_vol = np.clip(np.interp(right_lm[0].y, [0.45, 0.85], [1.0, 0.0]), 0.0, 1.0)
            vol = vol_smoother.update(raw_vol)
            
            raw_tilt = detector.get_tilt(right_lm, "Right")
            tilt = tilt_smoother.update(raw_tilt)
            
            index = detector.is_finger_extended(right_lm, 8, 6)
            middle = detector.is_finger_extended(right_lm, 12, 10)
            ring = detector.is_finger_extended(right_lm, 16, 14)
            pinky = detector.is_finger_extended(right_lm, 20, 18)
            
            voicing_idx = max(1, sum([index, middle, ring, pinky]))
            octave_drop = detector.is_thumb_extended(right_lm, "Right")

        # --- GÜNCELLEMELER ---
        audio.play_chord(curr_chord, curr_major, voicing_idx, octave_drop, vol, tilt)
        draw_energy_waves(frame, vol, tilt, curr_chord, curr_major)

        # Roma rakamı yerine Müzikal Nota İsmini (Do, Re, Mi) alıyoruz
        gosterilen_akor = audio.akor_isimleri.get(curr_chord, "--") if curr_chord else "--"
        akor_turu = "Maj" if curr_major else "Min"

        cv2.putText(frame, f"Akor: {gosterilen_akor} {akor_turu}", 
                    (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(frame, f"Form: Tip {voicing_idx} | Bass Mode: {'Acik' if octave_drop else 'Kapali'}", 
                    (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 255, 200), 2)
        cv2.putText(frame, f"Filtre (Tilt): {int(tilt*100)}%", 
                    (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 200, 255), 2)

        cv2.imshow("PySynth - JS Port V2", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    audio.close()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()