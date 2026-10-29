"""huggingface hello Space — Hugging Face Hub'daki model reposundan modeli indirip Gradio ile sunar.

Bu dosya `hf_cli.py push-space` tarafından Space reposuna olduğu gibi kopyalanır.
Hangi model reposunun okunacağı yanına yazılan `space_config.json`'dan gelir.
Yerelde denemek için: MODEL_DIR=<model klasörü> python app.py
"""
import json
import os
from pathlib import Path

import gradio as gr
import joblib
import pandas as pd

BURASI = Path(__file__).resolve().parent


def model_klasoru() -> Path:
    # Yerel deneme: MODEL_DIR verilirse Hub'a hiç gidilmez.
    if os.environ.get("MODEL_DIR"):
        return Path(os.environ["MODEL_DIR"])
    from huggingface_hub import snapshot_download

    ayar = json.loads((BURASI / "space_config.json").read_text(encoding="utf-8"))
    return Path(snapshot_download(repo_id=ayar["model_repo"], allow_patterns=["model.joblib", "config.json"]))


KLASOR = model_klasoru()
MODEL = joblib.load(KLASOR / "model.joblib")
CONFIG = json.loads((KLASOR / "config.json").read_text(encoding="utf-8"))
OZELLIKLER = [o["name"] for o in CONFIG["features"]]


def tahmin(*degerler):
    satir = pd.DataFrame([dict(zip(OZELLIKLER, degerler))])
    olasiliklar = MODEL.predict_proba(satir)[0]
    return {CONFIG["class_labels"][str(c)]: float(p) for c, p in zip(MODEL.classes_, olasiliklar)}


demo = gr.Interface(
    fn=tahmin,
    inputs=[gr.Number(label=o["label"], value=o["example"]) for o in CONFIG["features"]],
    outputs=gr.Label(label=CONFIG["target"]),
    title=CONFIG["title"],
    description=CONFIG["description"],
    examples=[[o["example"] for o in CONFIG["features"]]],
    flagging_mode="never",
    api_name="predict",
)

if __name__ == "__main__":
    demo.launch()
