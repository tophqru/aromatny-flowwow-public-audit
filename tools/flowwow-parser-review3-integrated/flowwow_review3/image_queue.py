"""Bound the browser's actual image requests; no extra workers or retries."""
from collections import deque

class ImageQueue:
    def __init__(self, limit=3, dispatch=None):
        if type(limit) is not int or not 1<=limit<=3:raise ValueError('IMAGE_CONCURRENCY_LIMIT_1_TO_3')
        self.limit=limit
        self.dispatch=dispatch or (lambda route:route.continue_())
        self.active=set();self.pending=deque();self.closed=False
        self.peak=0;self.started=0;self.completed=0;self.errors=0;self._draining=False
        self.cancelled_queued=0
        self.cancelled_active=0;self.owners={}

    def admit(self,route):
        if self.closed:
            route.abort('aborted');return
        try:owner=route.request.frame.page
        except Exception:owner=None
        if owner is not None:
            if owner.is_closed():
                self.cancelled_queued+=1
                try:route.abort('aborted')
                except Exception:pass
                return
            self.owners[route.request]=owner
        self.pending.append(route)
        self._drain()

    def _drain(self):
        if self._draining:return
        self._draining=True
        try:
            while not self.closed and self.pending and len(self.active)<self.limit:
                route=self.pending.popleft();request=route.request
                self.active.add(request);self.started+=1;self.peak=max(self.peak,len(self.active))
                try:self.dispatch(route)
                except Exception:
                    self.errors+=1;self.active.discard(request)
                    self.owners.pop(request,None)
                    try:route.abort('failed')
                    except Exception:pass
        finally:self._draining=False

    def finished(self,request):
        if request not in self.active:
            # A navigation/closed popup can cancel a request while its route is
            # still deferred. Dispatching it later would consume a slot with no
            # future completion event, starving live gallery requests.
            before=len(self.pending)
            self.pending=deque(route for route in self.pending if route.request is not request)
            self.cancelled_queued+=before-len(self.pending)
            self.owners.pop(request,None)
            return
        self.active.remove(request);self.completed+=1
        self.owners.pop(request,None)
        self._drain()

    def cancel_page(self,page):
        if not page.is_closed():raise ValueError('PAGE_MUST_BE_CLOSED_BEFORE_RELEASING_REQUESTS')
        requests={request for request,owner in self.owners.items() if owner is page}
        before=len(self.pending)
        self.pending=deque(route for route in self.pending if route.request not in requests)
        self.cancelled_queued+=before-len(self.pending)
        active=self.active & requests
        self.cancelled_active+=len(active);self.active.difference_update(active)
        for request in requests:self.owners.pop(request,None)
        self._drain()

    def snapshot(self):
        return {'limit':self.limit,'peak_inflight':self.peak,'inflight':len(self.active),
                'queued':len(self.pending),'started':self.started,'completed':self.completed,'dispatch_errors':self.errors,
                'cancelled_queued':self.cancelled_queued,'cancelled_active':self.cancelled_active}

    def close(self,*_):
        self.closed=True;self.pending.clear();self.active.clear();self.owners.clear()
