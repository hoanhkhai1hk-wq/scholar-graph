"""Optional one-time public download; inference remains local/offline and key-free."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for key in list(os.environ):
    if any(word in key.upper() for word in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")):
        del os.environ[key]
os.environ["HF_HOME"] = str(ROOT / "data/module-four-models/hf-home")
os.environ["HF_HUB_DISABLE_XET"] = "1"
from huggingface_hub import snapshot_download

if __name__ == "__main__":
    snapshot_download("BAAI/bge-reranker-large", revision="55611d7bca2a7133960a6d3b71e083071bbfc312",
        local_dir=str(ROOT / "data/module-four-models/bge-reranker-large"), token=False, max_workers=2,
        allow_patterns=["config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
                        "special_tokens_map.json", "sentencepiece.bpe.model"])
