"""Download the pinned BGE model without creating Windows symlinks."""

import argparse
import hashlib
import json
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

MODEL = "BAAI/bge-small-zh-v1.5"
REVISION = "7999e1d3359715c523056ef9478215996d62a620"
ALLOWED = {
    "config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "model.safetensors",
    "sentence_bert_config.json",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.txt",
    "1_Pooling/config.json",
}


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/models/bge-small-zh-v1.5"))
    args = parser.parse_args()
    with requests.Session() as client:
        client.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1)))
        response = client.get(
            f"https://huggingface.co/api/models/{MODEL}/tree/{REVISION}?recursive=true", timeout=60
        )
        response.raise_for_status()
        entries = {item["path"]: item for item in response.json() if item["type"] == "file"}
        manifest = {"model": MODEL, "revision": REVISION, "files": {}}
        for name in sorted(ALLOWED & entries.keys()):
            target = args.output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            expected = entries[name].get("lfs", {}).get("oid")
            if not (target.exists() and expected and digest(target) == expected):
                temp = target.with_suffix(target.suffix + ".download")
                with client.get(
                    f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}", stream=True, timeout=120
                ) as r:
                    r.raise_for_status()
                    with temp.open("wb") as output:
                        for block in r.iter_content(1024 * 1024):
                            output.write(block)
                if expected and digest(temp) != expected:
                    raise RuntimeError(f"Weight checksum mismatch: {name}")
                temp.replace(target)
            manifest["files"][name] = digest(target)
            print(name)
        required = {
            "config.json",
            "modules.json",
            "model.safetensors",
            "tokenizer.json",
            "1_Pooling/config.json",
        }
        if not required <= manifest["files"].keys():
            raise RuntimeError("Model snapshot is incomplete")
        (args.output / "download-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Set BUPT_EMBEDDING_MODEL to: {args.output.resolve()}")


if __name__ == "__main__":
    main()
