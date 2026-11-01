"""Conservative visible-browser shop pagination helpers.

Never treat a stable list or absence of a button as proof of complete inventory.
Only acts on visible product-list pagination controls, not review widgets.
"""
from __future__ import annotations

import re
from parsing import canonical_product, shop_item_links, SHOP, same_shop_url

SHOW_MORE = re.compile(r"^(?:показать\s+(?:ещё|еще|больше)(?:\s+товар(?:ов|ы)?)?|загрузить\s+(?:ещё|еще)(?:\s+товар(?:ов|ы)?)?|show\s+more(?:\s+products)?|load\s+more(?:\s+products)?)$",re.I)


def scan_links(page, store, category, found):
    """Retain links seen earlier even if a virtualized list removes DOM nodes."""
    count_before=len(found)
    for url in shop_item_links(page.content(),page.url):
        if (url:=canonical_product(url)) and url not in found:
            found.add(url)
            store.discover(url,category,"LIVE_SHOP_DOM")
    return len(found)-count_before


def sweep_incrementally(page, store, category, found, *, max_steps=80, delay_ms=500):
    """Scroll through intermediate positions (not one jump to bottom).

    Guarded by max_steps for infinite scrolling. Return observations, not proof.
    Nested scroll containers and server-side hidden inventory remain unverified.
    """
    if not 1<=max_steps<=300: raise ValueError("Invalid scroll budget")
    before=len(found)
    scan_links(page,store,category,found)
    # Start at current position to avoid discarding a just-clicked virtualized page.
    state=None; unchanged_at_bottom=0;steps=0
    for _ in range(max_steps):
        state=page.evaluate("""() => {
          const e=document.scrollingElement || document.documentElement;
          const n=Math.max(240, Math.round(window.innerHeight*0.8));
          window.scrollBy(0,n);
          let nested=false;
          const nodes=document.querySelectorAll('*');
          for (let i=0;i<Math.min(nodes.length,2000);i++){
            const el=nodes[i]; const s=getComputedStyle(el);
            if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight>el.clientHeight+4){nested=true;break;}
          }
          return {y:window.scrollY, height:e.scrollHeight, viewport:window.innerHeight, nested};
        }""")
        steps+=1
        page.wait_for_timeout(delay_ms)
        scan_links(page,store,category,found)
        # Require two successive observations at the bottom, to allow async DOM growth.
        at_bottom = (state['y']+state['viewport'] >= state['height']-4)
        if at_bottom: unchanged_at_bottom+=1
        else: unchanged_at_bottom=0
        if unchanged_at_bottom>=2:break
    return {"links_added":len(found)-before,"scroll_steps":steps,
            "observed_document_bottom":unchanged_at_bottom>=2,
            "scroll_budget_hit":steps>=max_steps and unchanged_at_bottom<2,
            "possible_nested_scroll":bool(state and state.get('nested', False))}


def visible_more_controls(page):
    # Use the shop's main content; never click a matching button in header or reviews.
    main=page.locator('main')
    if main.count()!=1: return [],"MAIN_NOT_UNAMBIGUOUS"
    root=main.first
    controls=[]
    for role in ('button','link'):
        for loc in root.get_by_role(role,name=SHOW_MORE).all():
            try:
                if loc.is_visible() and loc.is_enabled(): controls.append(loc)
            except Exception: continue
    return controls,None


def expand_shop_conservatively(page,args,store,category,waiter):
    """One shop/category, bounded scroll and pagination. stop_reason is never COMPLETE."""
    found=set(); cycles=0;clicks=0;stable=0;reason="CYCLE_LIMIT_REACHED"; sweeps=[]
    budget=getattr(args,'max_scroll_steps',80)
    while cycles<args.max_load_cycles:
        cycles+=1
        before=len(found)
        sweep=sweep_incrementally(page,store,category,found,max_steps=budget)
        sweeps.append(sweep)
        if sweep['scroll_budget_hit']:
            reason='SCROLL_STEP_LIMIT_REACHED'; break
        controls,control_error=visible_more_controls(page)
        if control_error:
            reason=control_error;break
        if len(controls)>1:
            reason='AMBIGUOUS_SHOW_MORE_CONTROLS';break
        if len(controls)==1:
            try:
                context=getattr(page,"context",None)
                pages_before=list(context.pages) if context is not None else []
                controls[0].click(timeout=7000)
                clicks+=1
                page.wait_for_timeout(1200)
                if context is not None and any(p not in pages_before for p in context.pages):
                    reason='MORE_CONTROL_OPENED_NEW_TAB';break
                if not same_shop_url(page.url):
                    reason='MORE_CONTROL_NAVIGATED_OUTSIDE_SHOP'
                    break
                scan_links(page,store,category,found)
                store.event('SHOP_SHOW_MORE_CLICK',{'category':category,'click_number':clicks})
                # A server callback may load items on a different viewport or after a delay.
                if len(found)==before:stable+=1
                else:stable=0
                if stable>=3:
                    reason='MORE_CLICKED_WITHOUT_OBSERVABLE_GROWTH';break
            except Exception as e:
                reason='MORE_CONTROL_CLICK_FAILED:'+type(e).__name__;break
        else:
            if len(found)==before:stable+=1
            else:stable=0
            if stable>=2:
                reason='NO_MORE_VISIBLE_CONTROL_STABLE_NOT_PROVEN_COMPLETE';break
        waiter(args)
    out={'category':category,'observed_product_links':len(found),'show_more_clicks':clicks,
         'scroll_steps':sum(x['scroll_steps'] for x in sweeps),
         'document_bottom_observed':bool(sweeps and sweeps[-1]['observed_document_bottom']),
         'possible_nested_scroll':any(x['possible_nested_scroll'] for x in sweeps),
         'stop_reason':reason,'end_of_category_proven':False}
    store.event('CATEGORY_OBSERVATION',out)
    return out
