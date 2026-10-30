"""Copy explicit non-private evidence; fail closed on configured credentials."""
import hashlib
import shutil
from common import ROOT, BASE, configured_environment, write

if __name__=='__main__':
    out=ROOT/'test-records/item08-20261030';out.mkdir(parents=True,exist_ok=True)
    names=['samples.json','reading-comparison.json','scan-mapping.json','ocr-independent.json',
           'ocr-mapping-review.json','default-stack.json','release-audit.json','cli-warm-final.json',
           'deployment-browser-final.json','fast-baseline.log','fast-final.log','fast-final.xml',
           'related-final.log','related-resumed.log','related-resumed.xml','targeted-final.log',
           'targeted-final.xml','build07.log','default-compose-up.log','fresh-default-up.log',
           'default-stack-dns-first.log','ocr-independent.log','failures-before.log',
           'vector-tests.log','vector-tests-fixed.log','vector-tests-fixed.xml',
           'failure-browser-after.log','browser-reading-before.log','browser-reading-before-ready.log',
           'browser-reading-after.log','browser-reading-after-matched.log']
    for folder in ['reading-before','reading-after','browser-reading-before-final','browser-reading-final',
                   'scan-browser-after','stream-cold','stream-warmup','stream-warm',
                   'resident-warmup','resident-warm','failures-seeded','failure-browser-before',
                   'failure-browser-final','failure-browser-release','translation-browser']:
        names.append(folder+'/report.json')
        names.extend(str(p.relative_to(BASE)).replace('\\','/') for p in (BASE/folder).glob('*.png'))
    names.extend(str(p.relative_to(BASE)).replace('\\','/') for p in (BASE/'deployed').glob('*.png'))
    key=configured_environment().get('DEEPSEEK_API_KEY','').encode()
    manifest={}
    for name in names:
        src=BASE/name;raw=src.read_bytes()
        assert not key or key not in raw, 'Credential found: '+name
        dst=out/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        manifest[name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    write(out/'evidence-manifest.json',manifest)
    print({'copied':len(manifest),'configured_key_matches':0})
