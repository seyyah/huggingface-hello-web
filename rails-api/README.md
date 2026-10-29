# `rails-api/` — ONNX modelini sunucuda çalıştıran Rails 8 API

İstemci (web / mobil) yalnız **form değerlerini JSON** olarak gönderir. Hesaplama sunucuda
yapılır, cevap olarak olasılıklar döner. **Model cihaza inmez**, bu yüzden gizli kalabilir.
Hasta verisiyle eğitilmiş modeller için doğru mimari budur.

- Rails 8.1 (API-only, veritabanı yok), Ruby 3.3
- [`onnxruntime`](https://github.com/ankane/onnxruntime-ruby) gem'i (native ORT gem içinde gelir)
- Model **nereden okunacak** env ile seçilir: yerel klasör, HTTP (Hugging Face) ya da S3 / S3 uyumlu
- **Auth yok (şimdilik)**. Üretime çıkmadan önce eklenmeli (bkz. "Üretime doğru")

## Hızlı başlangıç

```bash
cd rails-api
bundle install
bin/rails test                                    # 4 test, ağ gerektirmez (fixture model)
bin/rails server -b 0.0.0.0 -p 3100               # varsayılan kaynak: Hugging Face (http)
```

```bash
curl -s http://localhost:3100/up
curl -s http://localhost:3100/api/v1/model
curl -s -X POST http://localhost:3100/api/v1/predictions \
  -H 'Content-Type: application/json' \
  -d '{"inputs":{"pregnancies":1,"glucose":193,"blood_pressure":50,"skin_thickness":16,"insulin":375,"bmi":25.9,"pedigree":0.655,"age":24}}'
# → {"proba":{"diabetes yok":0.3229,"diabetes var":0.6771},"label":"diabetes var","model":{"source":"http:…","sha256":"8deb5e…"}}
```

## API

| Metot | Yol | Açıklama |
|---|---|---|
| GET | `/up` | Sağlık kontrolü (Rails) |
| GET | `/api/v1/model` | `config` (özellikler, sınıflar, metrikler), `source`, `sha256`, `loaded_at`. İstemci formu bundan üretir |
| POST | `/api/v1/predictions` | Girdi `{"inputs": {<özellik>: <sayı>, …}}`. Çıktı `{"proba": {…}, "label": "…", "model": {…}}` |
| POST | `/api/v1/model/reload` | Modeli kaynaktan yeniden çeker (yeni sürüm yayınlayınca). ⚠️ auth yok |

Hatalar:
- `422 {"error":"geçersiz girdi","missing":[…],"invalid":[…]}`: eksik ya da sayı olmayan alan.
- `400`: `inputs` yok.

## Model kaynağı (env)

Model dosyaları (`config.json` + `model.onnx`, `../hf_cli.py train` çıktısı) üç yerden
okunabilir. Açılışta bir kez çekilir, `tmp/model_cache/<sha256>.onnx`'e yazılır ve oradan
yüklenir.

| `MODEL_SOURCE` | Gerekli env | Örnek |
|---|---|---|
| `http` *(varsayılan)* | `MODEL_HTTP_BASE`, ops. `MODEL_HTTP_TOKEN` | `https://huggingface.co/5eyyah/hello-diabetes-onnx/resolve/main/`. Private HF repo için `MODEL_HTTP_TOKEN=hf_…` (token yalnız ilk host'a gider, CDN yönlendirmesine sızmaz) |
| `local` | `MODEL_LOCAL_DIR` | `storage/models/hello` (varsayılan) ya da `../_out/model` |
| `s3` | `MODEL_S3_BUCKET`, `MODEL_S3_PREFIX`, ops. `MODEL_S3_REGION`, `MODEL_S3_ENDPOINT` + `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | AWS S3: endpoint vermeyin. **Hetzner Object Storage / MinIO / Cloudflare R2**: `MODEL_S3_ENDPOINT=https://fsn1.your-objectstorage.com` gibi (path-style kullanılır) |

Diğer:
- `MODEL_EAGER_LOAD=0`: açılışta yükleme (ilk istekte yüklenir).
- `CORS_ORIGINS=https://a.com,https://b.com`: CORS'u daralt (varsayılan `*`).

```bash
# Kaynağı dene (sunucu açmadan): kaynak + sha256 + örnek tahmin
MODEL_SOURCE=local MODEL_LOCAL_DIR=../_out/model bin/rails model:check
MODEL_SOURCE=http bin/rails model:check

# Modeli S3'e yükle, sonra S3'ten çalıştır
export MODEL_S3_BUCKET=hello-models MODEL_S3_PREFIX=hello/ MODEL_S3_ENDPOINT=https://… AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=…
bin/rails model:push_s3 DIR=../_out/model
MODEL_SOURCE=s3 bin/rails model:check
MODEL_SOURCE=s3 bin/rails server -b 0.0.0.0 -p 3100
```

Test edildi (2026-10-29): `local`, `http` (Hugging Face) ve `s3` (yerel `moto` S3 emülatörü ile:
`uvx --from "moto[server]==5.1.4" moto_server -p 5055`). Üçü de aynı dosyayı (aynı sha256) yükleyip
**0.6771** verdi. Bu sonuç Python sklearn, web (onnxruntime-web) ve mobil ile aynı.

## Dosyalar

- `app/services/model_source.rb`: `Local` / `Http` / `S3` kaynakları (`#fetch(ad)` → bayt).
- `app/services/model_registry.rb`: yükleme, önbellek, girdi doğrulama, tahmin, `reload!`
  (işlem başına tek kopya, thread-safe).
- `app/controllers/api/v1/{models,predictions}_controller.rb`
- `config/initializers/model.rb`: açılışta ön-yükleme. `cors.rb`: CORS.
- `lib/tasks/model.rake`: `model:check`, `model:push_s3`.
- `test/integration/predictions_test.rb` + `test/fixtures/files/model/`: ağsız testler.

## Üretime doğru (Ubuntu VPS, örn. Hetzner)

1. **Auth:** API anahtarı / JWT (Rails 8 `authentication` generator ya da basit
   `Authorization: Bearer` kontrolü). `/model/reload` mutlaka korunmalı.
2. **HTTPS:** Caddy/nginx reverse proxy (Let's Encrypt). Mobilde `usesCleartextTraffic`'i kapatın.
3. **Çalıştırma:** `RAILS_ENV=production SECRET_KEY_BASE=… bin/rails server -b 127.0.0.1 -p 3100`
   + systemd unit (ya da Kamal/Docker).
4. **Model gizliliği:** private HF repo (`MODEL_HTTP_TOKEN`) ya da private S3 bucket. Model
   istemciye hiç gitmez.
5. **KVKK:** girdi değerleri sunucuya gelir. `inputs` log'larda zaten `[FILTERED]`
   (`config/initializers/filter_parameter_logging.rb`); saklama/erişim politikası ayrıca belirlenmeli.
