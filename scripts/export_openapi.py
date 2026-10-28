import json
from pathlib import Path

from bupt_rag.api import create_app

target = Path(__file__).resolve().parents[1] / "docs/openapi.json"
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(target)
