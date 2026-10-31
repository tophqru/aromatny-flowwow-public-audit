#!/usr/bin/env python3
"""Download one public shard, checking the exact original bytes against trusted snapshot."""
import argparse
import hashlib
import io
import json
import re
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
def main(shard,parts):
    snap=json.loads((ROOT/"catalog/public-snapshot.json").read_text(encoding="utf8"))
    assert parts==4 and 0<=shard<parts
    files=[x for p in snap["products"] for x in p["gallery"]]
    assert len(files)==435
    selected=[(i,im) for i,im in enumerate(files) if i%parts==shard]
    for index,im in selected:
        u=urlsplit(im["source_url"])
        assert u.scheme=="https" and re.fullmatch(r"content[1-9]\.flowwow-images\.com",u.hostname or "")
        assert re.fullmatch(r"/data/flowers/1000x1000/[0-9]+/[0-9]+_[0-9]+\.jpg",u.path)
        rel=Path(im["path"])
        assert not rel.is_absolute() and ".." not in rel.parts
        target=ROOT/"artifact"/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        req=urllib.request.Request(im["source_url"],headers={"User-Agent":"Mozilla/5.0","Accept":"image/jpeg"})
        with urllib.request.urlopen(req,timeout=40) as response:
            final=urlsplit(response.geturl())
            if response.status!=200 or final.hostname!=u.hostname or final.path!=u.path:
                raise ValueError(f"unexpected redirect {index}")
            if not response.headers.get("Content-Type","").lower().startswith("image/"):
                raise ValueError(f"non-image content {index}")
            data=response.read(15*1024*1024+1)
        if len(data)>15*1024*1024 or len(data)!=im["bytes"]:
            raise ValueError(f"size mismatch {rel}")
        if hashlib.sha256(data).hexdigest()!=im["sha256"]:
            raise ValueError(f"hash mismatch {rel}")
        with Image.open(io.BytesIO(data)) as picture:
            assert picture.format=="JPEG" and min(picture.size)>=320
            picture.verify()
        target.write_bytes(data)
        time.sleep(1.1)
    print(json.dumps({"shard":shard,"verified":len(selected),"total":len(files)}))
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--shard",type=int,required=True)
    p.add_argument("--parts",type=int,required=True)
    opts=p.parse_args()
    main(opts.shard,opts.parts)
