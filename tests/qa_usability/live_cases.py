"""Every result uses real source records and the configured model, never mocked answers."""
import argparse
import json
from common import ROOT,BASE,client,ask,write,ready

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);parser.add_argument('--extended',action='store_true');a=parser.parse_args()
    out=BASE/a.run;out.mkdir(exist_ok=False)
    with client() as c:
        ready(c)
        papers=c.get('/api/v1/papers',params={'page_size':100}).json()['items']
        choose=lambda prefix:next(p['id'] for p in papers if p['title'] and p['title'].startswith(prefix))
        heads=choose('Heads of Security:');inception=choose('Rethinking the Inception');attention=choose('Attention Is All');bert=choose('BERT:')
        cases=[('pair',[heads,inception],'他们有什么关联'),('method',[heads],'它是怎么防止提示注入攻击的？'),
               ('novelty',[inception],'这篇论文的创新点是什么？'),('overview',[inception],'这篇论文讲什么？')]
        if a.extended:
            cases += [('related',[heads,inception],'这两篇研究有哪些共同点和区别？'),('titleless-summary',[heads],'主要讲了啥？'),
                ('mechanism',[heads],'如何避免恶意输入影响模型？'),('different',[attention,bert],'这两篇有什么关系？'),
                ('unrelated',[heads],'论文中火星基地的建造预算是多少？'),('false-number',[attention],'论文是不是说Adam的β1=0.98、β2=0.9？')]
            reader='paper-1cb48e40e523d1994f38211edd30f92b0f01f0a25c2990bc8d84a9b684e95135'
            cases += [('actual-reader',[reader],'这篇论文的创新点是什么？'),('actual-reader-method',[reader],'它是怎么建模结构依赖的？')]
        report=[]
        for name,ids,q in cases:report.append(ask(c,ids,q,out/name));write(out/'results.json',report)
