import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG_PATH = ROOT / "config.json"
def load(): return json.loads(CFG_PATH.read_text(encoding="utf-8"))
def save(cfg): CFG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
