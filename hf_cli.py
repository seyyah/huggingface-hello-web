"""huggingface hello — tabular model → ONNX → Hugging Face Hub (ücretsiz) CLI'ı.

Ücretsiz yol (2026-10 itibarıyla doğrulandı):
  - Model reposu ücretsiz; dosyaları CORS açık "resolve" URL'leriyle sunulur.
  - HF'nin ücretsiz inference'ı sklearn desteklemiyor ("Model not supported by provider
    hf-inference"); Gradio/Docker Space'ler PRO istiyor (402).
  → Model ONNX'e çevrilir, tarayıcı (web/index.html → ileride GitHub Pages) model.onnx'i
    doğrudan Hub'dan çekip onnxruntime-web ile tahmin yapar. Sunucu yok.

Akış:
    train          → data/pima-diabetes.csv ile hello model + model.onnx (_out/model)
    predict        → yerel tahmin (deploy öncesi duman testi)
    whoami         → HF girişini doğrular
    push-model     → model reposunu oluşturur/günceller
    hub-predict    → Hub'daki model.onnx'i indirip tahmin eder (yüklenen dosyanın testi)
    deploy         → train + push-model (tek komut)
    pages          → web/ → GitHub Pages (bu reponun Actions workflow'u ile; --push ile uçtan uca)
    push-space     → Gradio Space (YALNIZ PRO hesapta çalışır)

Çalıştırma (repo kökünde, .venv ile):
    .venv/bin/python hf_cli.py train
    .venv/bin/hf auth login            # bir kez, "write" yetkili token ile
    .venv/bin/python hf_cli.py deploy
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BURASI = Path(__file__).resolve().parent
CIKTI = BURASI / "_out"  # her şey bu klasörde (paylaşılabilir); .gitignore'da
MODEL_DIR = CIKTI / "model"
SPACE_DIR = CIKTI / "space"
SPACE_TEMPLATE = BURASI / "space_template"

SEED = 13  # proje kuralı: her yerde 13
VARSAYILAN_AD = "hello-diabetes-onnx"

# Pima Indians Diabetes veri seti (NIDDK; UCI ML Repository), kısa kolon adlarıyla repoda.
VERI = BURASI / "data" / "pima-diabetes.csv"
HEDEF = "diabetes"


# --------------------------------------------------------------------------- train
def cmd_train(args):
    veri = pd.read_csv(VERI)
    X, y = veri.drop(columns=HEDEF), veri[HEDEF]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, stratify=y, random_state=SEED)

    # Hello model: ölçekleme + lojistik regresyon. Başka bir sklearn Pipeline da (predict_proba'lı)
    # aynı model.joblib + model.onnx + config.json sözleşmesine oturur.
    model = Pipeline([("scaler", StandardScaler()), ("lr", LogisticRegression(random_state=SEED))])
    model.fit(X_tr, y_tr)
    metrikler = {
        "accuracy": round(accuracy_score(y_te, model.predict(X_te)), 4),
        "auc": round(roc_auc_score(y_te, model.predict_proba(X_te)[:, 1]), 4),
    }

    if MODEL_DIR.exists():
        shutil.rmtree(MODEL_DIR)
    MODEL_DIR.mkdir(parents=True)
    joblib.dump(model, MODEL_DIR / "model.joblib")
    onnx_aktar(model, X_te)

    ornek = X_te.iloc[0]
    config = {
        "title": "huggingface hello — diabetes",
        "description": "Demo model (LogisticRegression, Pima diabetes). "
                       "Yalnız deneme amaçlıdır; klinik karar için KULLANILMAZ.",
        "target": HEDEF,
        "class_labels": {"0": "diabetes yok", "1": "diabetes var"},
        "features": [{"name": c, "label": c, "example": float(ornek[c])} for c in X.columns],
        "classes": [str(c) for c in model.classes_],
        "metrics": metrikler,
        "seed": SEED,
        "sklearn_version": sklearn.__version__,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
    }
    (MODEL_DIR / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    (MODEL_DIR / "README.md").write_text(model_karti(config), encoding="utf-8")
    print(f"✓ model eğitildi → {MODEL_DIR}")
    print(f"  test metrikleri: {metrikler}")


def onnx_aktar(model, X_ornek):
    """Tarayıcıda (onnxruntime-web) çalışacak sürümden bağımsız kopya: model.onnx.

    Girdi: float32 [n, özellik sayısı] tensörü 'input' (sıra config.json'daki features sırası).
    Çıktı: 'label' [n] ve 'probabilities' [n, sınıf] (zipmap kapalı → düz tensör).
    """
    import numpy as np
    import onnxruntime as ort
    from skl2onnx import to_onnx
    from skl2onnx.common.data_types import FloatTensorType

    onx = to_onnx(model, initial_types=[("input", FloatTensorType([None, X_ornek.shape[1]]))],
                  options={id(model): {"zipmap": False}}, target_opset=17)
    yol = MODEL_DIR / "model.onnx"
    yol.write_bytes(onx.SerializeToString())

    # Eşdeğerlik kontrolü: ONNX olasılıkları sklearn'ünkiyle aynı olmalı (float32 toleransı).
    oturum = ort.InferenceSession(str(yol))
    p_onnx = oturum.run(["probabilities"], {"input": X_ornek.to_numpy(np.float32)})[0]
    fark = float(np.abs(p_onnx - model.predict_proba(X_ornek)).max())
    if fark > 1e-4:
        sys.exit(f"✗ ONNX çıktısı sklearn'den sapıyor (maks fark {fark:.2e})")
    print(f"✓ model.onnx üretildi (sklearn ile maks fark {fark:.1e})")


def model_karti(config):
    satirlar = "\n".join(f"| {k} | {v} |" for k, v in config["metrics"].items())
    ornek = json.dumps({o["name"]: o["example"] for o in config["features"]}, ensure_ascii=False)
    return f"""---
library_name: sklearn
tags:
- demo
- onnx
- tabular-classification
- sklearn
pipeline_tag: tabular-classification
---

# {config["title"]}

{config["description"]}

## Model
- sklearn `Pipeline(StandardScaler → LogisticRegression)`, seed={config["seed"]}
- Eğitim ortamı: Python {config["python_version"]}, scikit-learn {config["sklearn_version"]}
  (pickle uyumu için yükleyen ortamda **aynı sklearn sürümü** gerekir)

## Test metrikleri (%30 hold-out)
| metrik | değer |
|---|---|
{satirlar}

## Kullanım
```python
import joblib, pandas as pd
from huggingface_hub import hf_hub_download

model = joblib.load(hf_hub_download("<repo_id>", "model.joblib"))
print(model.predict_proba(pd.DataFrame([{ornek}])))
```

Sürümden bağımsız / tarayıcı: `model.onnx` — girdi `input` float32 `[n, {len(config["features"])}]`
(sıra: `config.json` → `features`), çıktı `probabilities` `[n, sınıf]` (sıra: `config.json` → `classes`).
```
https://huggingface.co/<repo_id>/resolve/main/model.onnx
```

> ⚠️ `model.joblib` bir pickle dosyasıdır; yalnız güvendiğiniz repolardan yükleyin.
"""


# --------------------------------------------------------------------------- predict (yerel)
def cmd_predict(args):
    model = joblib.load(MODEL_DIR / "model.joblib")
    config = json.loads((MODEL_DIR / "config.json").read_text(encoding="utf-8"))
    girdi = json.loads(args.json) if args.json else {o["name"]: o["example"] for o in config["features"]}
    olasilik = model.predict_proba(pd.DataFrame([girdi]))[0]
    print(json.dumps({"input": girdi,
                      "proba": {config["class_labels"][str(c)]: round(float(p), 4)
                                for c, p in zip(model.classes_, olasilik)}},
                     indent=2, ensure_ascii=False))


# --------------------------------------------------------------------------- Hub
def api_ve_kullanici():
    from huggingface_hub import HfApi

    api = HfApi()
    try:
        kullanici = api.whoami()["name"]
    except Exception:
        sys.exit("✗ HF girişi yok. Önce: .venv/bin/hf auth login  (write yetkili token)")
    return api, kullanici


def repo_adi(verilen, kullanici, sonek=""):
    if verilen:
        return verilen if "/" in verilen else f"{kullanici}/{verilen}"
    return f"{kullanici}/{VARSAYILAN_AD}{sonek}"


def cmd_whoami(args):
    _, kullanici = api_ve_kullanici()
    print(f"✓ giriş yapıldı: {kullanici}")


def cmd_push_model(args):
    if not (MODEL_DIR / "model.joblib").exists():
        sys.exit("✗ model yok. Önce: hf_cli.py train")
    api, kullanici = api_ve_kullanici()
    repo = repo_adi(args.repo, kullanici)
    api.create_repo(repo, repo_type="model", private=args.private, exist_ok=True)
    readme = MODEL_DIR / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8").replace("<repo_id>", repo), encoding="utf-8")
    api.upload_folder(repo_id=repo, repo_type="model", folder_path=MODEL_DIR,
                      commit_message="hello model yüklendi")
    print(f"✓ model reposu → https://huggingface.co/{repo}")
    return repo


def cmd_push_space(args, model_repo=None):
    if not (MODEL_DIR / "config.json").exists():
        sys.exit("✗ model yok. Önce: hf_cli.py train")
    api, kullanici = api_ve_kullanici()
    model_repo = model_repo or repo_adi(args.repo, kullanici)
    space = repo_adi(args.space, kullanici, sonek="-space")
    config = json.loads((MODEL_DIR / "config.json").read_text(encoding="utf-8"))

    # Space klasörünü şablondan üret: app.py + hangi modeli okuyacağı + sabit bağımlılıklar.
    if SPACE_DIR.exists():
        shutil.rmtree(SPACE_DIR)
    shutil.copytree(SPACE_TEMPLATE, SPACE_DIR)
    (SPACE_DIR / "space_config.json").write_text(json.dumps({"model_repo": model_repo}, indent=2), encoding="utf-8")
    # sklearn sürümü eğitimdekiyle AYNI olmalı, yoksa pickle yüklenmeyebilir.
    (SPACE_DIR / "requirements.txt").write_text(
        f"scikit-learn=={config['sklearn_version']}\njoblib\npandas\nhuggingface_hub\n", encoding="utf-8")
    import gradio
    (SPACE_DIR / "README.md").write_text(f"""---
title: huggingface hello diabetes
emoji: 🩺
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: {gradio.__version__}
python_version: "{config['python_version']}"
app_file: app.py
pinned: false
---

huggingface hello demosu. Model: [{model_repo}](https://huggingface.co/{model_repo})
""", encoding="utf-8")

    api.create_repo(space, repo_type="space", space_sdk="gradio", private=args.private, exist_ok=True)
    api.upload_folder(repo_id=space, repo_type="space", folder_path=SPACE_DIR,
                      commit_message="hello space güncellendi")
    print(f"✓ Space → https://huggingface.co/spaces/{space}")
    print("  (ilk build birkaç dakika sürer; durum: Space sayfasındaki 'Building' rozeti)")


def cmd_deploy(args):
    cmd_train(args)
    repo = cmd_push_model(args)
    print(f"  tarayıcı testi: web/index.html?repo={repo}")


def cmd_hub_predict(args):
    # Yerel _out'a değil, Hub'daki dosyalara bakar → "yüklenen model çalışıyor mu?" testi.
    import numpy as np
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download

    _, kullanici = api_ve_kullanici()
    repo = repo_adi(args.repo, kullanici)
    config = json.loads(Path(hf_hub_download(repo, "config.json", force_download=True)).read_text(encoding="utf-8"))
    oturum = ort.InferenceSession(hf_hub_download(repo, "model.onnx", force_download=True))
    girdi = json.loads(args.json) if args.json else {o["name"]: o["example"] for o in config["features"]}
    x = np.array([[girdi[o["name"]] for o in config["features"]]], dtype=np.float32)
    olasilik = oturum.run(["probabilities"], {"input": x})[0][0]
    print(json.dumps({"repo": repo, "input": girdi,
                      "proba": {config["class_labels"][c]: round(float(p), 4)
                                for c, p in zip(config["classes"], olasilik)}},
                     indent=2, ensure_ascii=False))


# --------------------------------------------------------------------------- GitHub Pages
def gh(*komut, kontrol=True):
    """gh CLI çağrısı; stdout döner. kontrol=False → hata kodunda None döner."""
    r = subprocess.run(["gh", *komut], capture_output=True, text=True)
    if r.returncode != 0:
        if kontrol:
            sys.exit(f"✗ gh {' '.join(komut)}\n{r.stderr.strip()}")
        return None
    return r.stdout.strip()


def git(*komut, cwd):
    # Kimlik bilgisi gh'den gelir → ayrı git/SSH ayarı gerekmez (CI'da GH_TOKEN yeterli).
    subprocess.run(["git", "-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential",
                    *komut], cwd=cwd, check=True)


def gh_repo_bul(verilen):
    """--gh-repo verilmezse bu klasörün git origin'inden (github.com[:/]sahip/ad[.git]) çıkar."""
    if verilen:
        return verilen
    r = subprocess.run(["git", "remote", "get-url", "origin"], cwd=BURASI, capture_output=True, text=True)
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", r.stdout.strip())
    if not m:
        sys.exit("✗ GitHub reposu bulunamadı: --gh-repo sahip/ad verin ya da bu klasörü bir GitHub reposunda çalıştırın")
    return f"{m.group(1)}/{m.group(2)}"


def cmd_pages(args):
    """web/ → GitHub Pages (bu reponun .github/workflows/pages.yml'i yayınlar). Sayfa modeli HF'den okur.

    1) web/site.json'a hangi HF modelinin okunacağını yazar.
    2) Pages'i "GitHub Actions" kaynağına ayarlar (idempotent).
    3) --push: yalnız web/site.json'u commit'ler, push eder, bizim commit'in Pages çalışmasını bekler.
    4) Yayındaki site.json'u doğrular.
    """
    if args.repo and "/" in args.repo:
        model_repo = args.repo  # tam ad verildiyse HF girişi gerekmez
    else:
        _, hf_kullanici = api_ve_kullanici()
        model_repo = repo_adi(args.repo, hf_kullanici)
    gh_repo = gh_repo_bul(args.gh_repo)
    sahip, ad = gh_repo.split("/")
    site_url = f"https://{sahip.lower()}.github.io/{ad}/"

    site_json = BURASI / "web" / "site.json"
    yeni = json.dumps({"model_repo": model_repo}, indent=2) + "\n"
    degisti = not site_json.exists() or site_json.read_text(encoding="utf-8") != yeni
    print(f"• GitHub: {gh_repo} → {site_url}\n• model: {model_repo} (site.json {'güncellenecek' if degisti else 'aynı'})")
    if args.dry_run:
        print("  [dry-run] hiçbir şey yazılmadı/push edilmedi")
        return
    site_json.write_text(yeni, encoding="utf-8")

    # Pages kaynağı: GitHub Actions (workflow). Kapalıysa aç, dal tabanlıysa çevir.
    mevcut = gh("api", f"repos/{gh_repo}/pages", "-q", ".build_type", kontrol=False)
    if mevcut is None:
        gh("api", "-X", "POST", f"repos/{gh_repo}/pages", "-f", "build_type=workflow")
        print("✓ GitHub Pages açıldı (kaynak: GitHub Actions)")
    elif mevcut != "workflow":
        gh("api", "-X", "PUT", f"repos/{gh_repo}/pages", "-f", "build_type=workflow")
        print(f"✓ Pages kaynağı {mevcut} → workflow")

    if not args.push:
        print("• site.json yazıldı. Yayın için commit + push edin (pages.yml çalışır) ya da --push kullanın.")
        return

    sha = None
    if degisti:
        git("add", "web/site.json", cwd=BURASI)
        git("commit", "-q", "-m", f"site: model={model_repo}", "--", "web/site.json", cwd=BURASI)
        git("push", "-q", "origin", "HEAD", cwd=BURASI)
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=BURASI, capture_output=True, text=True).stdout.strip()
        print(f"✓ push edildi ({sha[:7]})")

    if sha:  # bizim commit'in pages.yml çalışmasını bekle
        for _ in range(60):
            satirlar = gh("run", "list", "-R", gh_repo, "--workflow", "pages.yml", "-L", "10",
                          "--json", "headSha,status,conclusion", kontrol=False)
            calisma = next((c for c in json.loads(satirlar or "[]") if c["headSha"] == sha), None)
            if calisma and calisma["status"] == "completed":
                if calisma["conclusion"] != "success":
                    sys.exit(f"✗ pages.yml başarısız ({calisma['conclusion']}): gh run list -R {gh_repo} --workflow pages.yml")
                print("✓ pages.yml tamamlandı")
                break
            time.sleep(5)
        else:
            sys.exit(f"✗ pages.yml 5 dk içinde bitmedi: gh run list -R {gh_repo} --workflow pages.yml")

    for _ in range(24):  # CDN tazelenmesi birkaç saniye gecikebilir
        try:
            with urllib.request.urlopen(site_url + "site.json", timeout=10) as r:
                if json.loads(r.read()).get("model_repo") == model_repo:
                    break
        except Exception:
            pass
        time.sleep(5)
    else:
        sys.exit(f"✗ {site_url}site.json beklenen modeli göstermiyor (CDN gecikmesi olabilir, tekrar deneyin)")
    print(f"✓ yayında → {site_url}")


# --------------------------------------------------------------------------- argparse
def main():
    p = argparse.ArgumentParser(description="huggingface hello: model → ONNX → Hugging Face / GitHub Pages")
    alt = p.add_subparsers(dest="komut", required=True)

    alt.add_parser("train", help="hello modeli eğit").set_defaults(fn=cmd_train)
    pr = alt.add_parser("predict", help="yerel tahmin")
    pr.add_argument("--json", help='örn. \'{"glucose": 150, ...}\' (boşsa örnek satır)')
    pr.set_defaults(fn=cmd_predict)
    alt.add_parser("whoami", help="HF girişini doğrula").set_defaults(fn=cmd_whoami)

    for ad, fn, yardim in [("push-model", cmd_push_model, "model reposuna yükle"),
                           ("push-space", cmd_push_space, "Gradio Space'e yükle (PRO gerekir)"),
                           ("deploy", cmd_deploy, "train + push-model")]:
        s = alt.add_parser(ad, help=yardim)
        s.add_argument("--repo", help=f"model reposu (varsayılan: <kullanıcı>/{VARSAYILAN_AD})")
        if ad != "push-model":
            s.add_argument("--space", help=f"Space (varsayılan: <kullanıcı>/{VARSAYILAN_AD}-space)")
        s.add_argument("--private", action="store_true",
                       help="özel repo (dikkat: Space özel modeli okuyamaz, HF_TOKEN secret gerekir)")
        s.set_defaults(fn=fn)

    hp = alt.add_parser("hub-predict", help="Hub'daki model.onnx ile tahmin")
    hp.add_argument("--repo", help=f"model reposu (varsayılan: <kullanıcı>/{VARSAYILAN_AD})")
    hp.add_argument("--json")
    hp.set_defaults(fn=cmd_hub_predict)

    pg = alt.add_parser("pages", help="web/ → GitHub Pages (Actions); model HF'den okunur")
    pg.add_argument("--repo", help=f"HF model reposu (varsayılan: <hf-kullanıcı>/{VARSAYILAN_AD})")
    pg.add_argument("--gh-repo", help="GitHub reposu sahip/ad (varsayılan: bu klasörün git origin'i)")
    pg.add_argument("--push", action="store_true", help="web/site.json'u commit+push et, yayını bekle ve doğrula")
    pg.add_argument("--dry-run", action="store_true", help="hiçbir şey yazma/push etme, yalnız planı yaz")
    pg.set_defaults(fn=cmd_pages)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
