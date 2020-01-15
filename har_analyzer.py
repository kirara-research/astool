import json
import sys
import os
import re
import base64
from datetime import datetime, timedelta
from dateutil.parser import parse

def name_request(r):
    seqnum = re.search(r"\?.*id=([0-9]+)", r["url"])
    if not seqnum:
        seqnum = 0
    else:
        seqnum = seqnum.group(1)
    path = r["url"].replace("https://", "z").split("/", 1)[-1]
    return f"{seqnum}_{r['method']}_{path.replace('/', '_').split('?', 1)[0]}"

def dump_request(r, s):
    with open(os.path.join("ex_bootstrap_script", f"{name_request(r)}.request.json"), "w") as out1:
        attach = None
        if r["method"] == "POST":
            attach = json.loads(r["postData"]["text"])
        json.dump({
            "url": r["url"],
            "method": r["method"],
            "data": attach,
        }, out1, sort_keys=True, ensure_ascii=False, indent=2)
    
    with open(os.path.join("ex_bootstrap_script", f"{name_request(r)}.response.json"), "w") as out2:
        attach = None
        if "content" in s and "text" in s["content"]:
            data = base64.b64decode(s["content"]["text"]).decode("utf8")
            try:
                attach = json.loads(data)
            except ValueError:
                attach = data
        json.dump({
            "url": r["url"],
            "method": r["method"],
            "data": attach,
        }, out2, sort_keys=True, ensure_ascii=False, indent=2)

def main():
    with open(sys.argv[1], "rb") as har:
        j = json.load(har)["log"]["entries"]
    
    timings = []
    timebase = None
    for ent in sorted(j, key=lambda x: x["startedDateTime"]):
        if ent["request"]["method"] == "GET" and "/static/" in ent["request"]["url"]:
            continue

        if timebase is None:
            timings.append((timedelta(seconds=0), name_request(ent["request"])))
            timebase = parse(ent["startedDateTime"])
        else:
            timings.append((parse(ent["startedDateTime"]) - timebase, name_request(ent["request"])))
            timebase = parse(ent["startedDateTime"])
        
        dump_request(ent["request"], ent["response"])

    with open("ex_bootstrap_script/0000_playlist.json", "w") as outf1:
        json.dump(
            [{"delay": t1.total_seconds(), "src": t2} for t1, t2 in timings], 
            outf1, sort_keys=True, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()