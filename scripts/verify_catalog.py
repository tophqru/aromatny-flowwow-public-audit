#!/usr/bin/env python3
"""Offline validation: source SKU fields, mirror card equality, real SHA-256/JPEG media."""
import argparse
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
def verify(with_media):
    manifest=json.loads((ROOT/"catalog/public-snapshot.json").read_text(encoding="utf-8"))
    assert manifest["products_count"]==len(manifest["products"])==66
    assert manifest["photos_count"]==435 and manifest["media_expected_bytes"]==49614983
    assert urlsplit(manifest["seller"]).path=="/shop/lyubov-eto-699e0e4519/"
    assert manifest["retail_approved_count"]==0
    assert manifest["inventory_scope"]=="PUBLIC_CONFIRMED_SKU_NOT_COMPLETE_SELLER_INVENTORY"
    total=0; total_bytes=0; slugs=set()
    if with_media:
        from PIL import Image
    for item in manifest["products"]:
        slug=item["slug"]
        assert re.fullmatch(r"[a-z0-9-]{1,100}",slug) and slug not in slugs
        assert slug!=manifest["excluded_owner_sku"]
        slugs.add(slug)
        source=urlsplit(item["flowwow_url"])
        assert source.scheme=="https" and source.hostname=="flowwow.com"
        assert source.path=="/flowers/"+slug+"/"
        assert urlsplit(item["seller_url"]).path=="/shop/lyubov-eto-699e0e4519/"
        assert item["owner_approved"] is False
        assert item["may_order"] is False and item["may_show_publicly"] is False
        detail=ROOT/"catalog/cards"/slug/"product.json"
        assert json.loads(detail.read_text(encoding="utf8"))==item
        assert (detail.parent/"README.md").is_file()
        assert item["gallery"]
        for i,im in enumerate(item["gallery"],1):
            expected=f"data/flowwow/items/{slug}/photos/{i:02d}.jpg"
            assert im["order"]==i and im["path"]==expected
            assert re.fullmatch("[0-9a-f]{64}",im["sha256"])
            assert im["bytes"]>0
            src=urlsplit(im["source_url"])
            assert src.scheme=="https" and re.fullmatch(r"content[1-9]\.flowwow-images\.com",src.hostname or "")
            assert re.fullmatch(r"/data/flowers/1000x1000/[0-9]+/[0-9]+_[0-9]+\.jpg",src.path)
            total+=1
            total_bytes+=im["bytes"]
            if with_media:
                dest=ROOT/expected
                assert dest.is_file(),f"Missing {dest}"
                binary=dest.read_bytes()
                assert len(binary)==im["bytes"],f"Size mismatch {dest}"
                assert hashlib.sha256(binary).hexdigest()==im["sha256"],f"SHA mismatch {dest}"
                with Image.open(io.BytesIO(binary)) as image:
                    assert image.format=="JPEG" and min(image.size)>=320
                    image.verify()
    assert total==435 and total_bytes==49614983
    print(json.dumps({"result":"PASS","phase":"media" if with_media else "metadata","sku":66,"photos":total,"bytes":total_bytes,"public_sale_products":0}))
if __name__=="__main__":
    a=argparse.ArgumentParser()
    m=a.add_mutually_exclusive_group(required=True)
    m.add_argument("--metadata-only",action="store_true")
    m.add_argument("--check-media",action="store_true")
    q=a.parse_args()
    verify(q.check_media)
