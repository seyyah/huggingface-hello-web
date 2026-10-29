# huggingface hello

**Canlı demo:** <https://seyyah.github.io/huggingface-hello-web/> ·
**Model:** <https://huggingface.co/5eyyah/hello-diabetes-onnx>

> *English summary:* A minimal, fully CLI-driven demo. It trains a small tabular model locally,
> exports it to **ONNX**, hosts it on the **Hugging Face Hub** for free, and runs the same model
> in three places:
> - in the **browser** (GitHub Pages + onnxruntime-web);
> - in an **Android app** (Expo + onnxruntime-react-native, model embedded or downloaded);
> - on your own **Rails 8 server** (onnxruntime gem, model read from local disk, HTTP or S3).
>
> For the same input, every consumer returns the same probability. Docs are in Turkish.

Bir tabular modeli **ücretsiz** yayınlayıp web, mobil ve sunucuda kullanmanın uçtan uca, CLI
ile otomatize edilebilir bir örneği. Model bilerek basit tutuldu (lojistik regresyon, Pima
diabetes verisi). Asıl gösterilen şey model değil, **boru hattı**.

> ⚠️ Model yalnız demo amaçlıdır; **klinik karar için kullanılmaz.**

| Tüketici | Hesaplama nerede | Model gizli mi? | Klasör |
|---|---|---|---|
| Web demo (GitHub Pages) | Tarayıcıda (`onnxruntime-web`) | Hayır | [`web/`](web/) |
| Android uygulaması "huggingface hello" | Cihazda (`onnxruntime-react-native`) ya da sunucuda | Hayır / Evet | [`mobile/`](mobile/) |
| Kendi backend'iniz (Rails 8) | Sunucuda (`onnxruntime` gem) | **Evet** | [`rails-api/`](rails-api/) |

Hepsi aynı `model.onnx` + `config.json` sözleşmesini kullanır. Referans girdiyle **hepsi
0.6771** verir: Python sklearn, ONNX/Python, tarayıcı, Android ve Ruby.

## Mimari

```
                    yerelde (ücretsiz)                         barındırma
hf_cli.py train ──► _out/model/{model.joblib, model.onnx, config.json, README.md}
                         │ deploy / push-model                ┌─ Hugging Face model reposu (public)
                         ├──────────────────────────────────► │
                         │ rails model:push_s3                └─ S3 / Hetzner / MinIO (private olabilir)
                         ▼
  ┌──────────────────────┬────────────────────────────┬──────────────────────────────┐
  │ web/ → GitHub Pages  │ mobile/ (Expo, Android)    │ rails-api/ (Rails 8)         │
  │ HF'den model.onnx'i  │  • Gömülü (çevrimdışı)     │  MODEL_SOURCE=local|http|s3  │
  │ çeker, tarayıcıda    │  • Uzak (HF'den indir)     │  POST /api/v1/predictions    │
  │ hesaplar             │  • Sunucu (JSON gönderir)─►│  {"inputs":{…}} → {"proba"}  │
  └──────────────────────┴────────────────────────────┴──────────────────────────────┘
```

**Neden böyle?** (Ekim 2026'da denendi)

| Hugging Face seçeneği | Sonuç |
|---|---|
| Model reposu | ✅ ücretsiz; dosyalar CORS açık `resolve` URL'leriyle sunulur |
| Serverless Inference | ❌ `Model not supported by provider hf-inference` (sklearn desteklenmiyor) |
| Gradio / Docker Space | ❌ `402 Payment Required` (PRO gerekiyor) |
| HF'de eğitim (Jobs) | ücretli (denenmedi) |

Sonuç: eğitim ve ONNX'e çevirme **yerelde** yapılıyor, HF yalnızca dosyaları barındırıyor.
Gizli kalması gereken modeller için kendi sunucunuz (`rails-api/`) kullanılıyor.

## Hızlı başlangıç

### 1) Python CLI: eğit → ONNX → Hugging Face → GitHub Pages

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
.venv/bin/hf auth login              # bir kez; "Write" token: https://huggingface.co/settings/tokens
gh auth login                        # bir kez (yalnız `pages` için)

.venv/bin/python hf_cli.py train         # data/pima-diabetes.csv → _out/model/ (ONNX↔sklearn eşdeğerlik kontrollü)
.venv/bin/python hf_cli.py predict       # yerel duman testi
.venv/bin/python hf_cli.py deploy        # train + HF'ye push (<hf-kullanıcı>/hello-diabetes-onnx)
.venv/bin/python hf_cli.py hub-predict   # HF'deki dosyayla tahmin
.venv/bin/python hf_cli.py pages --dry-run
.venv/bin/python hf_cli.py pages --push  # web/site.json → commit+push → Actions yayınlar → canlıda doğrular
```

`pages` şunları yapar:
- Demo sayfasının okuyacağı modeli `web/site.json`'a yazar.
- GitHub Pages kaynağını "GitHub Actions" olarak ayarlar.
- `--push` verilirse yalnız bu dosyayı commit'leyip push eder, [`pages.yml`](.github/workflows/pages.yml)
  çalışmasını bekler ve canlı sitedeki `site.json`'u kontrol eder.

Başka bir model göstermek için `pages --repo <kullanıcı/repo> --push` kullanın ya da sayfayı
`?repo=<kullanıcı/repo>` ile açın.

### 2) Rails API: sunucu tarafı tahmin

```bash
cd rails-api && bundle install && bin/rails test
bin/rails server -b 0.0.0.0 -p 3100               # varsayılan model kaynağı: Hugging Face
curl -s -X POST localhost:3100/api/v1/predictions -H 'Content-Type: application/json' \
  -d '{"inputs":{"pregnancies":1,"glucose":193,"blood_pressure":50,"skin_thickness":16,"insulin":375,"bmi":25.9,"pedigree":0.655,"age":24}}'
```
Yerel klasör ve S3 / Hetzner Object Storage seçenekleri: [`rails-api/README.md`](rails-api/README.md).

### 3) Android uygulaması

```bash
cd mobile && npm install && npm run build:apk
adb install -r android/app/build/outputs/apk/release/app-release.apk
adb reverse tcp:3100 tcp:3100                     # "Sunucu" modu: telefondaki localhost → bilgisayar
```
Kablosuz adb, log okuma ve çökme teşhisi: [`docs/ANDROID-DEBUG.md`](docs/ANDROID-DEBUG.md).

## Klasör haritası

| Yol | Ne |
|---|---|
| [`AGENTS.md`](AGENTS.md) / `CLAUDE.md` | Katkıda bulunan insan ve AI asistanlar için kurallar, değişmezler, tuzaklar |
| `hf_cli.py`, `requirements.txt` | Python CLI: `train`, `predict`, `deploy`, `hub-predict`, `pages`, `whoami`, `push-model`, (`push-space`: PRO) |
| `data/pima-diabetes.csv` | Eğitim verisi: Pima Indians Diabetes (NIDDK; UCI ML Repository), 768 satır |
| `web/` | Demo sayfası (`index.html`, `site.json`). GitHub Pages olarak yayınlanır |
| `mobile/` | Expo SDK 57 / React Native 0.86 uygulaması → [`mobile/README.md`](mobile/README.md) |
| `rails-api/` | Rails 8.1 API → [`rails-api/README.md`](rails-api/README.md) |
| `docs/ANDROID-DEBUG.md` | adb, kablosuz hata ayıklama, kurulum, logcat, backend'e bağlama |
| `space_template/` | Gradio Space (yalnız HF PRO hesapta çalışır; saklandı) |
| `.github/workflows/` | `pages.yml` (demo yayını), `ci.yml` (Rails testleri + mobil typecheck) |
| `_out/` | `hf_cli.py` çıktıları. Git'e girmez |

## Sözleşme

- `model.onnx`: girdi `input` float32 `[n, özellik]` (sıra = `config.features`), çıktı
  `probabilities` float32 `[n, sınıf]` (sıra = `config.classes`) ve `label`.
- `config.json`: `title`, `description`, `target`, `classes`, `class_labels`,
  `features[{name,label,example}]`, `metrics`, `seed`, `sklearn_version`, `python_version`.
- Formlar `config.features`'tan üretilir. Yeni bir model yayınlamak için kod değişikliği
  gerekmez. `predict_proba`'sı olan ve skl2onnx'in çevirebildiği herhangi bir sklearn
  Pipeline bu sözleşmeye oturur.

## Bilinen kısıtlar

- **İstemcide tahmin (web, mobil gömülü/uzak):** model dosyası herkese açıktır. Hassas veriyle
  (ör. hasta verisi) eğitilmiş modeller bu yolla **yayınlanmaz**; onlar için `rails-api/` ve
  private bir kaynak kullanılır.
- **ONNX kapsamı:** skl2onnx çoğu sklearn modelini çevirir. LightGBM/XGBoost için ek converter,
  özel transformer'lar için özel converter gerekebilir. Model bazında doğrulanmalı (`train`
  eşdeğerliği kontrol eder).
- `rails-api/`'de **auth yok**, düz HTTP. Mobilde `usesCleartextTraffic` test için açık. Üretimden
  önce auth ve HTTPS ekleyin.

## Sonraki adımlar

1. `rails-api/`: auth (API key / JWT), HTTPS, Ubuntu VPS'te systemd veya Kamal ile deploy.
2. CI: APK build ve `hub-predict` doğrulaması.
3. Tek sayfada birden çok model seçimi.
