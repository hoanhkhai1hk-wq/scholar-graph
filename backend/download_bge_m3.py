"""Download only the pinned public BGE-M3 CPU weights/tokenizer to ignored D-drive data/."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for key in list(os.environ):
    if any(term in key.upper() for term in ("TOKEN", "API_KEY", "SECRET", "PASSWORD")):
        del os.environ[key]
os.environ["HF_HOME"] = str(ROOT / "data" / "module-four-models" / "hf-home")
os.environ["HF_HUB_DISABLE_XET"] = "1"

from huggingface_hub import snapshot_download

if __name__ == "__main__":
    snapshot_download("BAAI/bge-m3", revision="5617a9f61b028005a4858fdac845db406aefb181",
        local_dir=str(ROOT / "data" / "module-four-models" / "bge-m3"), token=False, max_workers=2,
        allow_patterns=["config.json", "tokenizer*", "sentencepiece.bpe.model", "special_tokens_map.json",
                        "pytorch_model.bin", "sparse_linear.pt", "colbert_linear.pt", "modules.json",
                        "sentence_bert_config.json", "1_Pooling/config.json"])
