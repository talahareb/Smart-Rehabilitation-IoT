import json
from pathlib import Path
from typing import Dict


def load_json(path: str) -> Dict:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh) # JSON -> Dict