"""Three-target acceptance is distinct from batch completion and publication."""
import json
from pilot_targets import EXACT_SLUGS, SHOP

def pilot_acceptance(store, out):
    rows = {row[0]: row for row in store.page_rows()}
    targets = []
    blocked = False
    for slug in EXACT_SLUGS:
        url = f'https://flowwow.com/flowers/{slug}/'
        row = rows.get(url)
        missing = []
        if row is None:
            missing.append('NOT_ATTEMPTED')
        elif row[3] != 'CAPTURED':
            missing.append(row[3]); blocked = True
        else:
            p = json.loads(row[5])
            seller = p.get('seller', {})
            if (seller.get('status') != 'EXACT_SELLER_CLICK_VERIFIED' or
                    seller.get('clicked') is not True or seller.get('final_url') != SHOP):
                missing.append('SELLER_NOT_PROVEN')
            if p.get('url') != url or p.get('slug') != slug or p.get('page',{}).get('final_url') != url:
                missing.append('PRODUCT_IDENTITY_NOT_PROVEN')
            if not str(p.get('product_h1') or '').strip():
                missing.append('TITLE_NOT_OBSERVED')
            if any(p.get(k) is not False for k in ('owner_approved','may_order','may_show_publicly')):
                missing.append('SALE_FLAGS_UNSAFE_OR_MISSING')
            for section in ('composition','dimensions','description'):
                value = p.get('source_sections',{}).get(section,{})
                if value.get('status') != 'SOURCE_SECTION_TEXT_CAPTURED' or not value.get('text'):
                    missing.append(section.upper()+'_NOT_OBSERVED')
            for field in ('composition','dimensions'):
                if p.get(field,{}).get('status') != 'PARSED_NEEDS_SELLER_CONFIRMATION':
                    missing.append(field.upper()+'_NOT_PARSED')
            # There is intentionally no producer of this evidence until DOM capabilities
            # are proven on an authorized visible browser. Mock reports cannot certify live UI.
            ui = p.get('ui_evidence',{})
            if ui.get('sections_expanded') is not True:
                missing.append('SECTION_EXPANSION_NOT_PROVEN')
            g = p.get('gallery',{})
            count = g.get('observed_total')
            frames = g.get('visited_original_urls',[])
            if (g.get('status') != 'ALL_GALLERY_FRAMES_OBSERVED' or type(count) is not int or
                    not 1 <= count <= 60 or len(frames) != count or len(set(frames)) != count or
                    g.get('truncated') is not False):
                missing.append('ALL_GALLERY_FRAMES_NOT_PROVEN')
            if slug != EXACT_SLUGS[2]:
                downloads = {d.get('source_url') for d in p.get('image_downloads',[]) if d.get('status') in
                             ('NEW_ORIGINAL_FILE','ALREADY_CAPTURED','ALREADY_IN_PUBLIC_BASELINE','ALREADY_IN_PUBLIC_BASELINE_SHA256')}
                if not frames or not set(frames).issubset(downloads):
                    missing.append('PHOTO_FILES_NOT_VERIFIED')
        targets.append({'slug':slug,'url':url,'status':'BLOCKED' if row and row[3]!='CAPTURED' else ('PARTIAL' if missing else 'PASS'),
                        'missing_evidence':missing})
    return {'schema_version':1,'status':'BLOCKED' if blocked else ('PASS' if all(t['status']=='PASS' for t in targets) else 'PARTIAL'),
            'targets':targets,'automatically_approved_products':0,'gallery_completeness_claim':False,
            'live_browser_run':'NOT_PERFORMED_UNLESS_SEPARATELY_ATTESTED'}
