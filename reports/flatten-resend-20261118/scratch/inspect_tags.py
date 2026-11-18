"""Read-only: list every tag value (and state) recorded in the protection-check evidence files."""
import json, glob, sys
def walk(o, path=""):
    if isinstance(o, dict):
        if "tag" in o:
            print(" ", path, "tag=", repr(o["tag"]), "state=", o.get("state"), "ordType=", o.get("ordType", o.get("ord_type")))
        for k, v in o.items():
            walk(v, path + "/" + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, path + f"[{i}]")
for f in sorted(glob.glob(sys.argv[1] + "/*.json")):
    print("==", f)
    d = json.load(open(f, encoding="utf-8"))
    walk(d)
    if isinstance(d, dict):
        for k in d:
            if "history" in k:
                print("  HIST", k, "=", json.dumps(d[k], ensure_ascii=False)[:400])
