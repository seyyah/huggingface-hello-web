# `mobile/` — "huggingface hello": React Native (Expo SDK 57) içinde ONNX

Web sayfasıyla (`../web/index.html`) aynı hesaplamayı **cihaz üzerinde** yapar
(`onnxruntime-react-native`) ya da hesaplamayı kendi backend'imize (`../rails-api`) yaptırır.
Üç model kaynağı var:

| Kaynak | Nereden | Ağ | Ne zaman |
|---|---|---|---|
| **Gömülü** | `assets/model/{model.onnx,config.json}` uygulamayla paketlenir | gerekmez | açılışta otomatik |
| **Uzak** | `https://huggingface.co/<repo>/resolve/main/…` → cihazda `Documents/models/<repo>/` önbelleği | ilk indirmede | "Uzak" + "Modeli yükle"; "Yeniden indir" önbelleği tazeler |
| **Sunucu (kendi backend)** | `../rails-api`: form şeması `GET /api/v1/model`, tahmin `POST /api/v1/predictions` | her tahminde | Model cihaza inmez. Varsayılan `http://localhost:3100` (`adb reverse tcp:3100 tcp:3100` ile) |

Uzak modda, uygulamayı güncellemeden yeni bir model (`push-model` ile) kullanılabilir. Form
`config.json`'dan üretildiği için özellik sayısı veya adı değişse de ekran kendini uyarlar.

> Kurulum, kablosuz adb, log okuma ve backend'e bağlanma: [`../docs/ANDROID-DEBUG.md`](../docs/ANDROID-DEBUG.md)

## ⚠️ Expo Go ile ÇALIŞMAZ

`onnxruntime-react-native` native bir modüldür. Expo Go'da bulunmaz, bu yüzden **development
build** ya da APK gerekir.

## Komutlar

```bash
npm install
npm run sync-model                         # gömülü modeli HF'den tazele (varsayılan: src/defaults.json)
npm run sync-model -- kullanici/baska-repo # başka HF reposundan
npm run typecheck

# Yerel Android (ANDROID_HOME + Java 17 gerekir)
npm run android                            # expo run:android → bağlı cihaz/emülatöre dev build
npm run build:apk                          # prebuild + gradlew assembleRelease (yalnız arm64, ~53 MB)
#   → android/app/build/outputs/apk/release/app-release.apk  (debug anahtarla imzalı, yalnız test için)
adb install -r android/app/build/outputs/apk/release/app-release.apk
adb logcat -v brief | grep -E "ReactNativeJS|FATAL|libc\+\+abi"   # crash/JS hatası takibi

# Bulut (Expo hesabı gerekir; iOS için de bu yol)
npx eas-cli@latest build -p android --profile preview
```

`android/` ve `ios/` klasörleri `expo prebuild` ile üretilir (CNG) ve git'e girmez. Native
ayarlar `app.json` ve config plugin'leri üzerinden yapılır.

## onnxruntime-react-native için iki zorunlu düzeltme

1. **`react-native.config.js`:** paket eski bir `unimodule.json` taşıyor. Expo autolinking onu
   Expo modülü sanıyor ve RN autolinking'den düşürüyor, ama paket gerçek bir Expo modülü değil.
   Sonuçta native modül hiç kaydedilmiyor ve uygulama açılışta
   `TypeError: Cannot read property 'install' of null` ile kapanıyor. Bu dosya paketi klasik RN
   modülü olarak linklenmeye zorluyor. Kontrol:
   `npx expo-modules-autolinking react-native-config --platform android --json` çıktısında
   `onnxruntime-react-native` görünmeli.
2. **`patches/onnxruntime-react-native+1.24.3.patch`** (`postinstall: patch-package`):
   - Gradle 9'da kaldırılan `VersionNumber` kullanımını çıkarır.
   - Native ORT'yi `latest.integration` (→ 1.31.1) yerine 1.24.3'e sabitler, böylece JS ile
     native aynı sürümde kalır.

## Dosyalar

- `src/model.ts`: gömülü/uzak/API yükleme, önbellek ve tahmin. ONNX sözleşmesi web ile aynı
  (`input` → `probabilities`).
- `App.tsx`: tek ekran. Kaynak seçimi, repo/API adresi alanı, `config.json`'dan üretilen form ve olasılık
  çubukları.
- `scripts/sync-model.mjs`: gömülü modeli HF'den indirir.
- `metro.config.js`: `.onnx`'i asset olarak paketler.
- `react-native.config.js` + `patches/`: yukarıdaki iki düzeltme.
