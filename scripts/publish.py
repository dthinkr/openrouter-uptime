#!/usr/bin/env python3
"""Push the exported dataset/ to HuggingFace and/or Kaggle.

Runs export first, then publishes wherever credentials are present:
  - HuggingFace: env HF_TOKEN (or a cached login) -> dataset repo HF_DATASET
  - Kaggle:      ~/.kaggle/kaggle.json or env KAGGLE_USERNAME/KAGGLE_KEY
                 -> dataset KAGGLE_DATASET

Env overrides:
  HF_DATASET      default "venvoo/openrouter-uptime"
  KAGGLE_DATASET  default "spicycorn/openrouter-uptime"

    python3 scripts/publish.py            # both, if creds present
    python3 scripts/publish.py --hf       # only HF
    python3 scripts/publish.py --kaggle   # only Kaggle
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build"
HF_DATASET = os.environ.get("HF_DATASET", "venvoo/openrouter-uptime")
KAGGLE_DATASET = os.environ.get("KAGGLE_DATASET", "spicycorn/openrouter-uptime")


def publish_hf() -> None:
    from huggingface_hub import HfApi
    token = os.environ.get("HF_TOKEN")
    api = HfApi(token=token)
    api.create_repo(HF_DATASET, repo_type="dataset", exist_ok=True,
                    private=False)
    api.upload_folder(folder_path=str(OUT), repo_id=HF_DATASET,
                      repo_type="dataset",
                      commit_message="daily dataset refresh")
    print(f"HF: pushed -> https://huggingface.co/datasets/{HF_DATASET}")


def publish_kaggle() -> None:
    owner, slug = KAGGLE_DATASET.split("/")
    meta = {
        "title": "OpenRouter Uptime",
        "id": KAGGLE_DATASET,
        "licenses": [{"name": "MIT"}],
    }
    (OUT / "dataset-metadata.json").write_text(json.dumps(meta, indent=1))
    # create on first run, version thereafter
    exists = subprocess.run(
        ["kaggle", "datasets", "status", KAGGLE_DATASET],
        capture_output=True, text=True).returncode == 0
    cmd = (["kaggle", "datasets", "version", "-p", str(OUT),
            "-m", "daily refresh", "--dir-mode", "zip"] if exists else
           ["kaggle", "datasets", "create", "-p", str(OUT), "--dir-mode",
            "zip"])
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    print(f"Kaggle: https://www.kaggle.com/datasets/{KAGGLE_DATASET}")


def main() -> None:
    do_hf = "--kaggle" not in sys.argv
    do_kaggle = "--hf" not in sys.argv
    subprocess.run([sys.executable, str(ROOT / "scripts" / "export.py")],
                   check=True)
    if do_hf:
        try:
            publish_hf()
        except Exception as e:  # noqa: BLE001
            print(f"HF skipped: {e}")
    if do_kaggle:
        try:
            publish_kaggle()
        except Exception as e:  # noqa: BLE001
            print(f"Kaggle skipped: {e}")


if __name__ == "__main__":
    main()
