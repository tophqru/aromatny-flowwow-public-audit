"""Separate media-only proposal. Real execution requires a separate owner gate.

Does not modify the first-pilot manifest, SQLite, product metadata or sale flags.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
from PIL import Image
from media_transport import fetch_image
from parsing import SHOP, canonical_shop, image_url_safe
from pilot_targets import EXACT_SLUGS
from storage import safe_local_path, atomic_bytes, atomic_json

LIMIT=18*1024*1024

def validate_proposal(doc):
    if doc.get('mode')!='PHASE2_EXACT_MEDIA_ONLY' or doc.get('slug')!=EXACT_SLUGS[2]:
        raise ValueError('PHASE2_TARGET_MISMATCH')
    if doc.get('owner_approved') is not False or doc.get('may_order') is not False or doc.get('may_show_publicly') is not False:
        raise ValueError('PHASE2_SALE_FLAGS_UNSAFE')
    seller=doc.get('seller_evidence',{})
    if seller.get('status')!='EXACT_SELLER_CLICK_VERIFIED' or seller.get('clicked') is not True or canonical_shop(seller.get('final_url',''))!=SHOP:
        raise ValueError('PHASE2_SELLER_NOT_PROVEN')
    gallery=doc.get('gallery_evidence',{})
    urls=gallery.get('visited_original_urls',[])
    count=gallery.get('observed_total')
    if (gallery.get('status')!='ALL_GALLERY_FRAMES_OBSERVED' or type(count) is not int or
            not 1<=count<=30 or len(urls)!=count or len(set(urls))!=count or gallery.get('truncated') is not False):
        raise ValueError('PHASE2_GALLERY_NOT_PROVEN')
    if any(image_url_safe(url)!=url for url in urls):raise ValueError('PHASE2_UNSAFE_MEDIA_URL')
    return urls

def run(manifest, approval_file, output):
    raw=safe_local_path(Path(manifest)).read_bytes()
    if len(raw)>64000:raise ValueError('PHASE2_MANIFEST_TOO_LARGE')
    doc=json.loads(raw);urls=validate_proposal(doc)
    if approval_file is None:raise ValueError('PHASE2_EXPLICIT_SAFE_TEST_APPROVAL_REQUIRED')
    gate=json.loads(safe_local_path(Path(approval_file)).read_text(encoding='utf-8'))
    if (gate.get('authorization')!='OWNER_EXPLICIT_MEDIA_ONLY_SAFE_TEST' or
            gate.get('manifest_sha256')!=hashlib.sha256(raw).hexdigest() or
            gate.get('allowed_slug')!=EXACT_SLUGS[2] or gate.get('max_requests')!=len(urls)):
        raise ValueError('PHASE2_APPROVAL_MISMATCH')
    out=safe_local_path(Path(output))
    if any((parent/'.git').exists() for parent in [out,*out.parents]):
        raise ValueError('PHASE2_OUTPUT_MUST_BE_OUTSIDE_GIT')
    out.mkdir(parents=True,exist_ok=True)
    results=[]
    for index,url in enumerate(urls):
        # Existing transport enforces HTTPS/CDN/DNS/TLS/no-redirect/no-proxy,
        # byte caps and access-block stop. No browser cookies are supplied.
        data=fetch_image(url,LIMIT)
        if not 64<=len(data)<=LIMIT:raise ValueError('PHASE2_IMAGE_BYTES_INVALID')
        with Image.open(io.BytesIO(data)) as im:
            width,height=im.size
            if im.format!='JPEG' or getattr(im,'n_frames',1)!=1 or not (480<=width<=6000 and 480<=height<=6000) or width*height>36000000:
                raise ValueError('PHASE2_IMAGE_FORMAT_OR_DIMENSIONS_INVALID')
            im.verify()
        with Image.open(io.BytesIO(data)) as im:im.load()
        sha=hashlib.sha256(data).hexdigest()
        path=safe_local_path(out/f'{index+1:02d}-{sha[:12]}.jpg')
        if path.exists():raise ValueError('PHASE2_EXISTING_FILE_REQUIRES_REVIEW')
        atomic_bytes(path,data)
        results.append({'source_url':url,'sha256':sha,'bytes':len(data),'width':width,'height':height,'file':path.name,'approved_for_sale':False})
        atomic_json(out/'phase2-media-results.json',{'slug':EXACT_SLUGS[2],'files':results,'approved_for_sale':False})
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--approval-file')
    parser.add_argument('--output')
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    if args.verify_only:
        print(json.dumps({'validated_urls':len(validate_proposal(json.loads(Path(args.manifest).read_text(encoding='utf-8')))),'executed':False}))
    elif not args.output:parser.error('--output required for separately authorized execution')
    else:run(args.manifest,args.approval_file,args.output)
