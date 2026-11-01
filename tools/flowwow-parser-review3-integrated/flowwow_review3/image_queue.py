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

    def admit(self,route):
        if self.closed:
            route.abort('aborted');return
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
            return
        self.active.remove(request);self.completed+=1
        self._drain()

    def snapshot(self):
        return {'limit':self.limit,'peak_inflight':self.peak,'inflight':len(self.active),
                'queued':len(self.pending),'started':self.started,'completed':self.completed,'dispatch_errors':self.errors,
                'cancelled_queued':self.cancelled_queued}

    def close(self,*_):
        self.closed=True;self.pending.clear();self.active.clear()
