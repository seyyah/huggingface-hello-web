# AGENTS.md: katkı kuralları (insan + AI asistan)

Genel tanıtım için [`README.md`](README.md). Bu repoda çalışan her kişi ve asistan aşağıdakilere
uyar.

## 0. Önce oku, sonra değiştir

1. `README.md`: mimari, sözleşme, komutlar.
2. Dokunacağın alt klasörün README'si: `rails-api/README.md`, `mobile/README.md`,
   `docs/ANDROID-DEBUG.md`.
3. Bir şeyi "çalışıyor" demeden önce **§4'teki doğrulamayı** çalıştır. Çıktıyı uydurma.
   Çalıştıramadığın adımı açıkça "doğrulanmadı" diye yaz.

## 1. Değişmezler

- **Sözleşme:** `model.onnx` (girdi `input` float32 `[n,f]` → `probabilities` `[n,c]`) +
  `config.json` (`features` sırası = girdi sırası, `classes` sırası = çıktı sırası). Web, mobil ve
  Rails buna bağlı. Değiştirirsen **üçünü birden** güncelle.
- **Eşdeğerlik:** referans girdi (`config.features[].example`) ile tüm tüketiciler aynı
  olasılığı vermeli (hello model: `diabetes var` = **0.6771**). `train`, ONNX'i sklearn ile
  karşılaştırır (fark > 1e-4 → durur).
- **Seed:** `13` (her yerde aynı).
- **Eğitim yerelde** yapılır. HF yalnız barındırma içindir (ücretsiz inference ve Space yok,
  bkz. README).
- **Gizlilik:** istemcide çalışan model public'tir. Hassas veriyle eğitilmiş model **yalnız**
  `rails-api` + private kaynak (private HF + `MODEL_HTTP_TOKEN`, ya da private S3) ile sunulur.
  `rails-api` `inputs`'u log'larda filtreler; bunu kaldırma.
- **Sürüm sabitleri:**
  - Python: `scikit-learn==1.9.1`, `skl2onnx==1.20.0` (`requirements.txt`).
  - Web: `onnxruntime-web@1.22.0` (CDN).
  - Mobil: `onnxruntime-react-native@1.24.3` (native AAR de 1.24.3'e yamalı).
  - Ruby: `onnxruntime 0.11.8`.
  - Bir sürümü yükseltirsen §4'ü tekrar çalıştır.

## 2. Dokunma / dikkat

- `mobile/android/` ve `mobile/ios/` **üretilir** (`expo prebuild`) ve git'te yoktur; elle
  düzenleme. Native ayarlar `app.json`, config plugin'leri, `react-native.config.js` ve
  `patches/` üzerinden yapılır.
- `mobile/react-native.config.js` **silinmez**: onsuz ONNX native modülü autolink edilmez ve
  uygulama açılışta `Cannot read property 'install' of null` ile çöker.
- `mobile/patches/onnxruntime-react-native+1.24.3.patch` (Gradle 9 uyumu + native sürüm
  sabitleme) `postinstall` ile uygulanır. Paket sürümü değişirse yama yeniden üretilmeli.
- Mobil paket kimliği `io.github.seyyah.huggingfacehello`. Değiştirirsen telefonda ayrı bir
  uygulama olarak kurulur.
- Dışarıya yazan komutlar (`deploy`, `push-model`, `pages --push`, `model:push_s3`) public
  kaynakları değiştirir. Hedef repo/bucket adını teyit et; önce `pages --dry-run` kullan.
- Token, secret, `rails-api/config/master.key`, cihaz IP'leri ve eşleştirme kodları repoya
  girmez. Kimlik bilgileri `hf auth login`, `gh auth login` ve env değişkenlerinden gelir.
  Belgelerde örnek değerler kullan (`192.168.1.50:37123` gibi).
- Port 3000 bazı makinelerde dolu olabiliyor; örneklerde `rails-api` için **3100** kullanılıyor.

## 3. Komutlar (özet)

```bash
# Python (.venv)
.venv/bin/python hf_cli.py train | predict | deploy | hub-predict | pages [--dry-run|--push]
# Rails
cd rails-api && bin/rails test && bin/rails model:check && bin/rails server -b 0.0.0.0 -p 3100
# Mobil
cd mobile && npm install && npm run typecheck && npm run build:apk
adb install -r android/app/build/outputs/apk/release/app-release.apk && adb reverse tcp:3100 tcp:3100
```

## 4. Doğrulama listesi (değişiklikten sonra)

| Alan | Komut | Beklenen |
|---|---|---|
| Model | `.venv/bin/python hf_cli.py train` | `✓ model.onnx üretildi (sklearn ile maks fark ~1e-07)` |
| HF | `.venv/bin/python hf_cli.py hub-predict` | `diabetes var: 0.6771` |
| Rails | `cd rails-api && bin/rails test` | `0 failures, 0 errors` |
| Rails kaynak | `MODEL_SOURCE=http bin/rails model:check` | proba ≈ 0.6771, sha256 = HF'dekiyle aynı |
| Mobil | `cd mobile && npx tsc --noEmit && npx expo-doctor` | hata yok |
| Mobil native | `npx expo-modules-autolinking react-native-config --platform android --json` | `onnxruntime-react-native` listede |
| Android | `npm run build:apk` + `adb logcat` (bkz. docs) | `BUILD SUCCESSFUL`; açılışta FATAL yok |
| Web | `pages --dry-run`; canlı `site.json` | doğru model reposu |
| CI | GitHub Actions: `ci`, `pages` | yeşil |

## 5. Karar günlüğü

- **Ekim 2026**
  - **Web:** HF Gradio Space 402 (PRO) döndü. Bu yüzden ONNX istemcide çalışıyor, sayfa GitHub
    Pages'te (Actions ile `web/`).
  - **Mobil:** Expo SDK 57. ORT RN için iki düzeltme gerekti: autolinking ve Gradle 9 yaması.
    Kaynak seçmek modeli hemen yükler; aksi halde "Sunucu" seçili görünürken gömülü model
    kullanılabiliyordu.
  - **Sunucu:** Rails 8 + `onnxruntime` gem'i. Model kaynağı local/http/s3 olarak soyutlandı;
    S3, `moto` emülatörüyle test edildi.
  - **Veri:** CSV dış bir URL'den indirilmek yerine `data/` altında tutuluyor; eğitim
    çevrimdışı ve deterministik.
