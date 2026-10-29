import os
import sys
from pathlib import Path

REQUIRED = {
    "senses": ("BAAI/bge-base-en-v1.5",),
    "sentences": ("BAAI/bge-base-en-v1.5", "BAAI/bge-reranker-large", "cross-encoder/nli-deberta-v3-base", "facebook/bart-large-mnli"),
    "audio": ("hexgrad/Kokoro-82M",),
    "deck": (),
}
WEIGHTS = ("*.safetensors", "*.bin", "*.pth")
UNUSED_FORMATS = ["*.onnx", "onnx/*", "openvino/*", "*.h5", "*.msgpack", "*.ot", "*.tflite", "coreml/*"]


def hub_cache() -> Path:
    if "HF_HUB_CACHE" in os.environ:
        return Path(os.environ["HF_HUB_CACHE"])
    return Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"


def is_cached(repo: str) -> bool:
    snapshots = hub_cache() / f"models--{repo.replace('/', '--')}" / "snapshots"
    return any(list(snapshot.glob(pattern)) for snapshot in snapshots.glob("*") for pattern in WEIGHTS)


def download(repo: str) -> None:
    from huggingface_hub import list_repo_files, snapshot_download

    unused = UNUSED_FORMATS + (["*.bin"] if any(name.endswith(".safetensors") for name in list_repo_files(repo)) else [])
    print(f"Downloading {repo} (first run only)", file=sys.stderr)
    snapshot_download(repo, ignore_patterns=unused)


def prepare(steps: list[str]) -> None:
    for repo in dict.fromkeys(repo for step in steps for repo in REQUIRED[step]):
        if not is_cached(repo):
            try:
                download(repo)
            except Exception as error:
                raise SystemExit(f"Could not download {repo}: {error}")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    if "huggingface_hub" in sys.modules:
        sys.modules["huggingface_hub"].constants.HF_HUB_OFFLINE = True
