"""Narrow adapter observed on the permitted desktop product on 2026-11-01.

No hidden APIs, application-state objects or invented CDN URLs are used.
"""
from pathlib import Path
import re
import time
from bs4 import BeautifulSoup
from parsing import canonical_product, detect_challenge, image_url_safe
from storage import atomic_json

ROOT = '.product-detail'
MAIN = ROOT + ' .product-detail-slider [id^=mainslider_]'
THUMBS = ROOT + ' .product-detail-slider [id^=thumbslider_]'
ACTIVE = MAIN + ' .swiper-slide-active:not(.swiper-slide-duplicate) img'

class GalleryObservationError(RuntimeError):
    def __init__(self, reason, partial):
        super().__init__(reason)
        self.partial=partial

def frame_wait_budget(started, now):
    remaining=180000-int((now-started)*1000)
    if remaining<=0:raise TimeoutError('GALLERY_TOTAL_WAIT_BUDGET_EXHAUSTED')
    return min(90000,remaining)

def layout_present(html):
    soup=BeautifulSoup(html,'html.parser')
    roots=soup.select(ROOT)
    return len(roots)==1 and len(roots[0].select('h1'))==1

def observed_sections(html):
    soup=BeautifulSoup(html,'html.parser')
    roots=soup.select(ROOT)
    absent=lambda reason: {'status':'SOURCE_NOT_VISIBLE','text':None,'reason':reason}
    result={k:absent('OBSERVED_PRODUCT_ROOT_NOT_UNIQUE') for k in ('composition','dimensions','description')}
    if len(roots)!=1 or len(roots[0].select('h1'))!=1:return result
    root=roots[0]
    result['description']=absent('MISSING_OR_AMBIGUOUS_DESKTOP_DESCRIPTION')
    for field,label,selector in [('composition','Состав','.pre-line'),('dimensions','Размер','.size-text')]:
        blocks=[b for b in root.select('.right-content > .properties > .property-item')
                if b.select_one('h3.property-name') and b.select_one('h3.property-name').get_text(' ',strip=True)==label]
        if len(blocks)==1:
            values=[x.get_text('\n',strip=True) for x in blocks[0].select(selector)]
            text='\n'.join(values).strip()
            result[field]={'status':'SOURCE_SECTION_TEXT_CAPTURED' if text else 'NOT_PRESENT_IN_SOURCE','text':text or None,'reason':None,'selector':'.right-content > .properties > .property-item: '+label}
            if field=='dimensions' and text:
                # In these observed size rows '-' is a label separator.
                # Preserve source text and normalize only this exact UI form.
                result[field]['parser_text']='\n'.join(re.sub(r'^(Ширина|Высота)\s+-\s+(\d+)\s+см$',r'\1: \2 см',v) for v in values)
        else:result[field]=absent('MISSING_OR_AMBIGUOUS_OBSERVED_BLOCK')
    blocks=root.select('.product-properties-general-desktop > .property-item')
    if not blocks:
        result['description']={'status':'NOT_PRESENT_IN_SOURCE','text':None,'reason':'NO_DESKTOP_DESCRIPTION_BLOCK_IN_OBSERVED_LAYOUT'}
    if len(blocks)==1 and not blocks[0].select('h1,h2,h3'):
        values=blocks[0].select('.pre-line')
        if len(values)==1:
            text=values[0].get_text('\n',strip=True)
            result['description']={'status':'SOURCE_SECTION_TEXT_CAPTURED' if text else 'NOT_PRESENT_IN_SOURCE','text':text or None,'reason':None,'selector':'.product-properties-general-desktop > .property-item .pre-line'}
    return result

def navigation_allowed(url, allowed, shop):
    # This exact query was observed on the real seller widget. Do not admit
    # arbitrary queries, other sellers, shop subpaths or product redirects.
    return url in set(allowed) | {shop,shop+'?from=product'}

def wait_layout_ready(page):
    page.bring_to_front()
    page.wait_for_selector(MAIN+'.swiper-initialized',state='visible',timeout=60000)

def observe_ui(page,url,out,blocked,identity=canonical_product):
    def guard():
        if identity(page.url)!=url:raise blocked('OBSERVED_ADAPTER_EXACT_SKU_CHANGED')
        if detect_challenge(page.title(),'',page.content()):raise blocked('OBSERVED_ADAPTER_SOURCE_CHALLENGE')
    guard()
    wait_layout_ready(page)
    root=page.locator(ROOT)
    if root.count()!=1 or root.locator('h1').count()!=1:raise blocked('OBSERVED_ADAPTER_ROOT_AMBIGUOUS')
    clicks=[]
    expand=root.locator('.right-content > .properties > .property-item a.show-more, .product-properties-general-desktop > .property-item a.show-more')
    if expand.count()>4:raise blocked('OBSERVED_ADAPTER_EXPANSION_AMBIGUOUS')
    for button in expand.all():
        if button.is_visible() and re.fullmatch(r'Показать\s+ещ[её]',button.inner_text().strip(),re.I):
            button.click(timeout=7000);page.wait_for_timeout(350);guard()
            clicks.append('VISIBLE_SHOW_MORE_CLICKED')
    remaining=[b.inner_text().strip() for b in expand.all() if b.is_visible() and re.match(r'Показать',b.inner_text().strip())]
    sections=observed_sections(page.content())
    main=page.locator(MAIN);thumbs=page.locator(THUMBS)
    if main.count()!=1 or thumbs.count()!=1:raise blocked('OBSERVED_ADAPTER_GALLERY_ROOT_AMBIGUOUS')
    indices=thumbs.locator('img.thumb[data-index-slide]').evaluate_all('els=>els.map(e=>e.getAttribute("data-index-slide"))')
    if not indices or len(indices)>30 or len(set(indices))!=len(indices) or set(indices)!={str(i) for i in range(len(indices))}:
        raise blocked('OBSERVED_ADAPTER_THUMBNAIL_INDEX_AMBIGUOUS')
    frames=[]
    started=time.monotonic()
    evidence=Path(out)/'local-evidence'/url.rstrip('/').split('/')[-1]
    evidence.mkdir(parents=True,exist_ok=True)
    progress={'source_sections':sections,'gallery':{'status':'PARTIAL_GALLERY_OBSERVATION','observed_total':len(indices),'frames':frames,'visited_original_urls':[],'truncated':False},
              'ui_evidence':{'sections_expanded':not remaining,'expansion_click_count':len(clicks),'gallery_frame_clicks':0}}
    atomic_json(evidence/'partial-observation.json',progress)
    for index in range(len(indices)):
        thumb=thumbs.locator(f'img.thumb[data-index-slide="{index}"]')
        if thumb.count()!=1:raise blocked('OBSERVED_ADAPTER_THUMBNAIL_NOT_UNIQUE')
        thumb.click(timeout=7000)
        try:
            # Lazy images must be in the actual viewport. A CSS-visible
            # carousel may still be below the seller/expanded sections.
            main.scroll_into_view_if_needed(timeout=7000)
            page.wait_for_function('''({selector,index})=>{
              const img=document.querySelector(selector);
              return img && img.closest('.swiper-slide').getAttribute('data-swiper-slide-index')===String(index)
                && img.complete && img.naturalWidth>=480 && img.naturalHeight>=480;
            }''',arg={'selector':ACTIVE,'index':index},polling=250,timeout=frame_wait_budget(started,time.monotonic()))
        except Exception as exc:
            guard()
            progress['failure']={'stage':'IMAGE_DECODE_WAIT','index':index,'error_type':type(exc).__name__}
            atomic_json(evidence/'partial-observation.json',progress)
            raise GalleryObservationError('IMAGE_DECODE_WAIT_FAILED_INDEX_'+str(index),progress) from exc
        guard()
        active=page.locator(ACTIVE)
        if active.count()!=1:raise blocked('OBSERVED_ADAPTER_ACTIVE_FRAME_AMBIGUOUS')
        data=active.evaluate('(e)=>({url:e.currentSrc,src:e.getAttribute("src"),width:e.naturalWidth,height:e.naturalHeight})')
        safe=image_url_safe(data['url'])
        if not safe:raise blocked('OBSERVED_ADAPTER_UNSAFE_IMAGE_SOURCE')
        frames.append({'index':index,'source_url':safe,'current_src':safe,'width':data['width'],'height':data['height'],'thumbnail_clicked':True})
        progress['gallery']['visited_original_urls']=[f['source_url'] for f in frames]
        progress['ui_evidence']['gallery_frame_clicks']=len(frames)
        atomic_json(evidence/'partial-observation.json',progress)
        if index in (0,len(indices)-1):page.screenshot(path=str(evidence/f'gallery-{index}.png'))
    urls=[f['source_url'] for f in frames]
    complete=len(urls)==len(set(urls))==len(indices)
    gallery={'status':'ALL_GALLERY_FRAMES_OBSERVED' if complete else 'GALLERY_DUPLICATE_SOURCES_UNVERIFIED',
             'observed_total':len(indices),'visited_original_urls':urls,'items':urls,'frames':frames,
             'truncated':False,'selector':MAIN,'source_resolution_note':'Actual displayed currentSrc; highest source beyond displayed UI is not independently proven.'}
    city=page.locator('.label-address')
    cities=[x.inner_text().strip() for x in city.all() if x.is_visible()]
    ui={'sections_expanded':not remaining,'expansion_click_count':len(clicks),'description_clicks':'VISIBLE_SHOW_MORE_IF_PRESENT',
        'composition_clicks':'VISIBLE_SHOW_MORE_IF_PRESENT','gallery_frame_clicks':len(frames),'delayed_spa_ready':True,
        'observed_city':cities[0] if len(cities)==1 else None,'locale':page.locator('html').get_attribute('lang'),
        'original_beyond_displayed_resolution':'NOT_PROVEN','fullscreen':'NOT_PRESENT_INLINE_ZOOM_OBSERVED_ON_DIAGNOSTIC'}
    return sections,gallery,ui
