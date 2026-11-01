"""Repeat the source-SHA baseline, adversarial before/after and final offline checks.
Run from repo root using the tested venv. Does not switch branches or open browsers.
"""
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import datetime

REPO=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
SOURCE='6313dcd1efa068c3ee011d8ccead8796dffbf60f'
REL='tools/flowwow-parser-review3-integrated/flowwow_review3'
LOG=OUT/'logs'
LOG.mkdir(exist_ok=True)
results=[]

def run(cmd,name,expected=0,cwd=REPO,header=''):
    start=time.monotonic()
    result=subprocess.run(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
    (LOG/name).write_text(header+result.stdout,encoding='utf8')
    results.append({'command':list(map(str,cmd)),'exit_code':result.returncode,'expected_exit_code':expected,
                    'duration_seconds':round(time.monotonic()-start,3),'log':name})
    print(name,result.returncode,flush=True)
    if result.returncode!=expected:
        print(result.stdout[-4000:]);raise SystemExit('Unexpected audit result')
    return result.stdout

with tempfile.TemporaryDirectory(prefix='review3-pristine-') as folder:
    raw=subprocess.check_output(['git','archive',SOURCE,'tools/flowwow-parser-review3-integrated','catalog/public-snapshot.json'],cwd=REPO)
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        # The tree is a trusted, pinned repository tree, not an arbitrary uploaded tar.
        tar.extractall(folder)
    tests=Path(folder)/REL/'tests'
    text=run([sys.executable,'-m','unittest','discover','-s',str(tests),'-v'],'baseline-tests-deps.log',cwd=folder)
    assert 'Ran 104 tests' in text and '\nOK\n' in text
    shutil.copyfile(REPO/REL/'tests/test_round3_independent.py',tests/'test_round3_independent.py')
    text=run([sys.executable,'-m','unittest','discover','-s',str(tests),'-p','test_round3_independent.py','-v'],
             'final-independent-before.log',expected=1,cwd=folder,
             header='Pristine source: '+SOURCE+'\nOnly final test_round3_independent.py copied; production source untouched.\nExpected exit: 1\n\n')
    assert 'Ran 69 tests' in text and 'FAILED (failures=35, errors=29)' in text

run([sys.executable,'-m','compileall','-q',REL],'compileall.log')
text=run([sys.executable,'-m','unittest','discover','-s',REL+'/tests','-v'],'final-all-tests.log')
assert 'Ran 173 tests' in text and '\nOK\n' in text
text=run([sys.executable,'-m','unittest','discover','-s',REL+'/tests','-p','test_round3_independent.py','-v'],'final-independent-after.log')
assert 'Ran 69 tests' in text and '\nOK\n' in text
run([sys.executable,'-S',REL+'/capture.py','doctor'],'doctor-no-deps.json')
run(['git','diff','--check',SOURCE],'diff-check.log')
(LOG/'final-command-results.json').write_text(json.dumps({'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':results},indent=2)+'\n')
print('PASS: exact 104 baseline, 69 independent before/after, 173 final; browser NOT_PERFORMED')
