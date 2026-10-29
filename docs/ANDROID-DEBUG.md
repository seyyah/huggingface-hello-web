# Android: kurulum, kablosuz hata ayıklama ve sorun giderme

Bu belge `mobile/` uygulamasını (**huggingface hello**) gerçek bir Android telefona kurmayı,
kablosuz bağlanmayı, log okumayı ve kendi backend'imize (`rails-api/`) bağlamayı anlatır.
Aşağıdaki komutların hepsi bu projede gerçekten denendi (Xiaomi/MIUI telefon, Windows 11 + WSL2
mirrored ağ, 2026-10-29).

---

## 0. Gerekenler (bilgisayar)

| Araç | Not |
|---|---|
| `adb` (platform-tools) | Ubuntu/WSL: `sudo apt install adb` ya da Android SDK `platform-tools/` |
| Android SDK + NDK + Java 17 | Yalnız APK **derlemek** için (`ANDROID_HOME` ayarlı olmalı) |
| Node 20+ | `mobile/` için |

> **WSL2 notu:** `adb` WSL içinde çalışır ve telefona Wi-Fi üzerinden bağlanır, USB
> passthrough gerekmez. WSL'in `networkingMode=mirrored` olması (`%UserProfile%\.wslconfig`)
> telefondan bilgisayara erişimi de kolaylaştırır (bkz. §6).

---

## 1. Telefonda geliştirici seçenekleri

1. **Ayarlar → Telefon hakkında → MIUI/Yapı numarası**'na 7 kez dokun → "Geliştiricisiniz".
2. **Ayarlar → Ek ayarlar → Geliştirici seçenekleri**:
   - **USB hata ayıklama**: açık.
   - **Kablosuz hata ayıklama** (Wireless debugging): açık (Android 11+).
   - *(MIUI, isteğe bağlı)* **USB hata ayıklama (Güvenlik ayarları)**: adb'nin dokunma/klavye
     enjekte etmesi (`adb shell input …`) için gerekir. Kapalıyken `INJECT_EVENTS permission`
     hatası alınır. Bu bir güvenlik ayarıdır; yalnız test süresince açın.
   - *(MIUI)* **USB üzerinden yükle**: kablo ile `adb install` için gerekebilir.

---

## 2. Kablosuz bağlanma (kablo yok)

Telefon ve bilgisayar **aynı Wi-Fi**'da olmalı.

### Önerilen düzen: 3 terminal

| Terminal | Komut | Not |
|---|---|---|
| 1: adb sunucusu | `adb nodaemon server` | **Açık kalsın.** Kapanırsa tüm bağlantılar ve `reverse` kurallarıyla birlikte gider |
| 2: backend | `cd rails-api && bin/rails server -b 0.0.0.0 -p 3031` | Port örnek; §6'daki `reverse` ile eşleşmeli |
| 3: komutlar | `adb connect …`, `adb -s … reverse …`, `adb logcat …` | Aşağıdaki adımlar |

> **Neden `adb nodaemon server`?** `adb start-server` ve `adb kill-server` sunucuyu arka plana
> atıp "hazır" cevabı bekler. WSL çöktükten sonra bu adım **süresiz takıldı** (`kill-server`
> dakikalarca döndü). Sunucunun kendisi sorunsuz çalıştığı için onu ayrı bir terminalde ön
> planda (`nodaemon`) başlatmak bu takılmayı tamamen atlar. Takılırsa:
> ```bash
> pgrep -af adb                                  # artık süreç var mı?
> pkill -x adb                                   # varsa öldür
> timeout 3 bash -c 'echo > /dev/tcp/127.0.0.1/5037' && echo "5037 dolu" || echo "5037 boş"
> adb nodaemon server                            # (Terminal 1) yeniden başlat
> ```
> WSL mirrored modda 5037 portunu Windows'taki bir adb de (Android Studio, scrcpy, telefon
> yazılımları) tutabilir; bu durumda WSL içindeki `ss`/`pgrep` onu göstermez, yukarıdaki
> `/dev/tcp` testi gösterir.

```bash
# (a) Eşleştirme — yalnız ilk sefer (ya da eşleşme silinince)
#     Telefonda: Kablosuz hata ayıklama → "Eşleştirme koduyla cihaz eşleştir"
#     Ekranda IP:PORT ve 6 haneli kod görünür (bu port YALNIZ eşleştirme içindir)
adb pair 192.168.1.50:41567
# Enter pairing code: 123456      ← telefonda görünen 6 haneli kod (değerler örnektir)
# → Successfully paired to 192.168.1.50:41567

# (b) Bağlanma — "Kablosuz hata ayıklama" ana ekranındaki IP:PORT (eşleştirme portundan FARKLI)
adb connect 192.168.1.50:37123
# → connected to 192.168.1.50:37123

adb devices
# 192.168.1.50:37123	device      ← "unauthorized" ise telefondaki izin penceresini onaylayın
```

- Bağlantı **portu her açılışta değişir**. Telefon kilitlenince ya da Wi-Fi değişince bağlantı
  düşebilir; o zaman yalnız (b)'yi yeni portla tekrarlayın.
- **`adb: error: more than one device/emulator`**: kablosuzda aynı telefon iki kez görünebilir
  (`192.168.1.50:37123` ve mDNS ile bulunan `adb-…._adb-tls-connect._tcp`). `adb devices -l` ile
  bakın. Komutlara cihazı açıkça verin; betiklerde **her zaman** `-s` kullanın:
  ```bash
  D=192.168.1.50:37123
  adb -s $D reverse tcp:3100 tcp:3031
  adb -s $D shell …
  ```
- `adb devices` takılırsa sunucuyu yukarıdaki kutudaki gibi `adb nodaemon server` ile yeniden
  başlatın (`kill-server`/`start-server` WSL'de takılabiliyor).

### Kablo ile (alternatif)
Native Linux'ta kabloyu takıp `adb devices` yeterli. WSL'de USB için `usbipd-win` gerekir; Wi-Fi
yöntemi daha basit.

---

## 3. APK derleme ve kurulum

```bash
cd mobile
npm install                      # postinstall: patch-package (onnxruntime yaması)
npm run build:apk                # expo prebuild + gradlew assembleRelease (arm64, ~53 MB, ~2-6 dk)
adb install -r android/app/build/outputs/apk/release/app-release.apk
# Performing Streamed Install
# Success
```

- `-r`: üzerine kur (veriler korunur). Paket kimliği `io.github.seyyah.huggingfacehello` sabit kaldıkça
  yeni APK eskisini günceller.
- APK Expo'nun **debug anahtarıyla** imzalıdır, yalnız test içindir (Play Store'a gitmez).
- `INSTALL_FAILED_UPDATE_INCOMPATIBLE` (imza farkı) → `adb uninstall io.github.seyyah.huggingfacehello` ve tekrar kur.
- Eski 32-bit telefon gerekiyorsa `build:apk` içindeki `-PreactNativeArchitectures=arm64-v8a`
  değerini `armeabi-v7a,arm64-v8a` yapın.

### Uygulamayı komutla başlatma / durdurma
```bash
adb shell monkey -p io.github.seyyah.huggingfacehello -c android.intent.category.LAUNCHER 1   # başlat
adb shell am force-stop io.github.seyyah.huggingfacehello                                    # durdur
adb shell pidof io.github.seyyah.huggingfacehello                                            # çalışıyor mu?
adb shell pm clear io.github.seyyah.huggingfacehello                                         # verileri sil (HF önbelleği dahil)
```

---

## 4. Log okuma ve çökme (crash) teşhisi

**Release APK'nın sunucuya ihtiyacı yoktur**: JS bundle ve gömülü model APK'nın içindedir.
Uygulama "tıklayınca kapanıyorsa" sebep neredeyse her zaman log'dadır.

```bash
adb logcat -c                                                  # eski log'u temizle
adb shell monkey -p io.github.seyyah.huggingfacehello -c android.intent.category.LAUNCHER 1
sleep 5
# Uygulamaya ait önemli satırlar
adb logcat -d -v brief | grep -E "ReactNativeJS|FATAL|Fatal signal|libc\+\+abi|AndroidRuntime: |onnx"
# Yalnız crash tamponu (native stack)
adb logcat -d -b crash -v brief | tail -60
# Canlı izleme
adb logcat -v brief | grep -E "ReactNativeJS|FATAL|libc\+\+abi"
```

Nasıl okunur:

| Log'da gördüğünüz | Anlamı |
|---|---|
| `E/ReactNativeJS: … TypeError …` | JS hatası. Mesaj doğrudan sebebi söyler |
| `libc++abi: terminating … JavascriptException` + `Fatal signal 6 (SIGABRT)` | JS hatası uygulamayı öldürdü (bir üst satıra bakın) |
| `AndroidRuntime: FATAL EXCEPTION` | Java/Kotlin tarafında çökme |
| `I/ReactNativeJS: Running "main"` ve FATAL yok | Uygulama sorunsuz açıldı |
| `Load …/libonnxruntimejsi.so … ok` | ONNX Runtime native kütüphanesi yüklendi |

### Bu projede yaşanan gerçek örnek
```
E/ReactNativeJS: [runtime not ready]: TypeError: Cannot read property 'install' of null
F/libc: Fatal signal 6 (SIGABRT) … (mqt_v_js)
```
→ `onnxruntime-react-native` native modülü **autolink edilmemişti** (paket eski bir
`unimodule.json` taşıyor; Expo onu kendi modülü sanıp RN autolinking'den düşürüyor).
Çözüm `mobile/react-native.config.js`'te. Kontrol:
```bash
cd mobile
npx expo-modules-autolinking react-native-config --platform android --json | grep -o onnxruntime-react-native
grep OnnxruntimePackage android/app/build/generated/autolinking/src/main/java/com/facebook/react/PackageList.java
```

### Ekran görüntüsü / UI ağacı (dokunmadan inceleme)
```bash
adb exec-out screencap -p > ekran.png
adb shell uiautomator dump /sdcard/ui.xml && adb exec-out cat /sdcard/ui.xml > ui.xml   # buton koordinatları
adb shell input tap 540 1600          # MIUI'de "USB hata ayıklama (Güvenlik ayarları)" gerekir
```

---

## 5. Geliştirme modu (canlı yenileme, JS debugger)

Release APK hızlı denemek içindir. Kod değiştirip anında görmek için **development build**:

```bash
cd mobile
npm run android        # expo run:android → dev build'i bağlı telefona kurar + Metro'yu başlatır
```
- Bu modda telefon JS'yi bilgisayardaki **Metro sunucusundan** (port 8081) çeker. Kablosuzda
  `adb reverse tcp:8081 tcp:8081` gerekir (`expo run:android` çoğu zaman kendisi yapar).
- Uygulamada geliştirici menüsü: telefonu sallayın ya da `adb shell input keyevent 82`.
- **Expo Go çalışmaz**: `onnxruntime-react-native` native modüldür, Expo Go'da yoktur.

---

## 6. Telefonu kendi backend'imize (`rails-api`) bağlama

Uygulamada **"Sunucu (kendi backend)"** seçeneği, tahmini `rails-api`'ye yaptırır. Sunucuyu
başlatın:
```bash
cd rails-api && bin/rails server -b 0.0.0.0 -p 3100
```
> Port **3100** seçildi; bu makinede 3000 (Windows tarafında) başka bir süreç tarafından kullanılıyordu.

Telefonun sunucuya ulaşmasının iki yolu var:

### (a) `adb reverse` (önerilen, ağ/firewall ayarı gerektirmez)
```bash
D=192.168.1.50:37123
adb -s $D reverse tcp:3100 tcp:3100      # telefondaki localhost:3100 → bilgisayardaki :3100
adb -s $D reverse --list                 # host-NN tcp:3100 tcp:3100
```
Uygulamada adres: `http://localhost:3100` (varsayılan).

- **Portlar farklı olabilir:** sol taraf telefondaki port, sağ taraf bilgisayardaki port.
  Rails başka bir portta çalışıyorsa (örn. 3031) uygulamadaki adresi değiştirmek yerine:
  `adb -s $D reverse tcp:3100 tcp:3031`.
- `reverse` kuralları **adb sunucusuna bağlıdır**. adb sunucusu (Terminal 1) ya da kablosuz
  bağlantı koparsa kurallar kaybolur; `connect` ve `reverse` tekrarlanmalı.
- Kaldırmak için: `adb -s $D reverse --remove tcp:3100` ya da `--remove-all`.

### (b) Aynı Wi-Fi üzerinden doğrudan IP
Uygulamada adres: `http://<bilgisayar-LAN-IP>:3100` (WSL mirrored modda Windows'un IP'si, örn.
`192.168.1.20`). Windows Defender Firewall gelen bağlantıyı engelleyebilir. Gerekirse
**yönetici PowerShell**'de:
```powershell
New-NetFirewallRule -DisplayName "rails-api 3100" -Direction Inbound -Protocol TCP -LocalPort 3100 -Action Allow
```
(Kural, güvenlik ayarı olduğu için bilinçli olarak eklenmeli; testten sonra silinebilir.)

### Düz HTTP notu
Android release build'leri `http://`'yi varsayılan olarak engeller. Test için `app.json`'da
`expo-build-properties` → `android.usesCleartextTraffic: true` açıldı. **Üretimde HTTPS
kullanın ve bu ayarı kapatın.**

### Hızlı kontrol (katman katman)
```bash
D=192.168.1.50:37123; PORT=3031                          # Rails'in portu
curl -s -m 5 http://127.0.0.1:$PORT/up                    # 1) Rails ayakta mı? → 200
adb -s $D reverse --list                                   # 2) tcp:3100 tcp:$PORT görünmeli
adb -s $D shell 'curl -s -m 5 -o /dev/null -w "%{http_code}\n" http://localhost:3100/up'   # 3) telefon → Rails: 200
tail -f rails-api/log/development.log                      # 4) uygulamanın istekleri burada görünür
```
- Telefondan curl'e **her zaman `-m 5`** verin. Zaman aşımı olmadan, cevap gelmeyen bir
  bağlantıda (örn. kapalı porta giden eski bir `reverse` kuralı) curl süresiz bekler ve
  "`adb shell` takıldı" gibi görünür.
- 3. adım 200 dönüyor ama 4. adımda uygulamanın isteği (`GET /api/v1/model`,
  `POST /api/v1/predictions`) görünmüyorsa uygulama sunucuyu **kullanmıyordur**. Ekrandaki
  **"Kaynak:"** satırına bakın: `Kaynak: API http://localhost:3100 ← …` olmalı.
  `Kaynak: gömülü` yazıyorsa tahmin telefonda yapılıyordur.
  - Bu projede gerçekten yaşandı: eski sürümde kaynak butonu yalnız *seçiyor*, modeli
    "Modeli yükle"ye basılınca yüklüyordu. "Sunucu" seçili görünürken tahmin gömülü
    modelle yapıldı.
  - Artık kaynağa dokunmak o kaynağı **hemen yükler**. Adresi değiştirdiyseniz yine
    "Modeli yükle"ye basın.

---

## 7. Sık hatalar

| Belirti | Sebep / çözüm |
|---|---|
| Uygulama açılır açılmaz kapanıyor | §4: `logcat`'e bakın. `install of null` → autolinking (`react-native.config.js`) |
| `Model yüklenemedi: … Network request failed` (Sunucu modu) | `adb reverse` yok/koptu, sunucu kapalı, yanlış port ya da cleartext kapalı |
| `HTTP 422 …missing/invalid` | Form alanı boş ya da sayı değil (API doğrulaması) |
| Uzak (HF) modu hata veriyor | İnternet yok ya da repo adı yanlış/private |
| `adb: device offline` / `unauthorized` | Telefonda izin penceresi; adb sunucusunu yeniden başlat (§2 kutusu); §2(b) tekrar |
| `adb kill-server` / `start-server` dakikalarca dönmüyor | §2 kutusu: Ctrl+C, `pkill -x adb`, `adb nodaemon server` |
| `adb: error: more than one device/emulator` | Aynı telefon iki kayıtla görünüyor (IP:port + mDNS) → `adb -s <IP:PORT> …` |
| `adb shell curl …` takılıyor | curl'e `-m 5` verin; `reverse` kuralını ve Rails portunu kontrol edin (§6) |
| Rails log'unda uygulamanın isteği yok, `/up` var | Uygulama gömülü modeli kullanıyor: ekranda "Kaynak:" satırına bakın (§6) |
| `INJECT_EVENTS permission` | MIUI güvenlik ayarı (§1); dokunmaları elle yapın |
| Gradle: `Could not get unknown property 'VersionNumber'` | `npm install` yapılmamış → `patches/` uygulanmamış |
| Gradle: `SoftwareComponent with name 'release' not found` | Genelde yukarıdaki hatanın yan etkisi |
