"""Linux downloader-only memory probe. NO browser, NO network, NOT an ASUS test."""
import gc
import json
from pathlib import Path
import resource
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/flowwow-parser-review3-integrated/flowwow_review3'))
import media_transport
LIMIT=18*1024*1024
resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
class Response:
    status=200
    def __init__(self,size):self.remaining=size;self.max_read=0
    def getheader(self,key):return None
    def read1(self,n):
        assert 0<n<=65536
        self.max_read=max(self.max_read,n)
        take=min(n,self.remaining);self.remaining-=take
        return b'x'*take
    def close(self):pass
class Connection:
    def close(self):pass
for _ in range(30):
    response=Response(LIMIT)
    with patch('media_transport.open_response',return_value=(Connection(),response)):
        value=media_transport.fetch_image('https://content.flowwow-images.com/probe.jpg',LIMIT)
        assert len(value)==LIMIT
    del value
    gc.collect()
response=Response(LIMIT+1024*1024*1024)
with patch('media_transport.open_response',return_value=(Connection(),response)):
    try:media_transport.fetch_image('https://content.flowwow-images.com/probe.jpg',LIMIT)
    except RuntimeError as exc:assert str(exc)=='IMAGE_TOO_LARGE'
    else:raise AssertionError('oversized stream accepted')
assert response.remaining==1024*1024*1024-1
peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
assert peak<128*1024,(peak,'KiB peak exceeded 128 MiB')
print(json.dumps({'status':'PASS','network':'NOT_PERFORMED','browser':'NOT_PERFORMED','linux_address_space_limit_mib':256,
                  'sequential_18mib_streams':30,'oversize_stream_bytes_consumed':LIMIT+1,
                  'max_read_bytes':response.max_read,'process_peak_rss_kib':peak,'asus_8gb_runtime':'NOT_PERFORMED'},indent=2))
