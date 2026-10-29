"""Copy the proven corpus into a separate acceptance library; source remains intact."""
import json,shutil,sqlite3
from common import ROOT,BASE,write,digest
if __name__=='__main__':
    source=ROOT/'data/item05-20261029/records20';target=BASE/'records';target.mkdir(exist_ok=False)
    for folder in ['papers','original-pdfs']:shutil.copytree(source/folder,target/folder)
    with sqlite3.connect(source/'workspace.sqlite3') as a,sqlite3.connect(target/'workspace.sqlite3') as b:a.backup(b)
    write(BASE/'frozen-before.json',{str(p.relative_to(target)).replace('\\','/'):digest(p) for folder in ['papers','original-pdfs'] for p in (target/folder).rglob('*') if p.is_file()})
    papers=json.loads((ROOT/'data/item05-20261029/graph-delivery/summary.json').read_text(encoding='utf8'))['papers']
    selected=[p for p in papers if p['filename'] in ['1706.03762v7.pdf','2106.09685v2.pdf','2203.02155v1.pdf']]
    write(BASE/'selected-papers.json',selected);print('Copied 20-paper test corpus; writing scope is three actual papers')
