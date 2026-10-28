"""Compare frozen single-reviewer labels with old/new ranking, not general accuracy."""
import json
import sys
from common import ROOT, BASE, write
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.reference_importance import rank_references

if __name__ == '__main__':
    source=json.loads((BASE/'seed-upload.json').read_text(encoding='utf-8'))
    folder=BASE/'records/papers'/source['paper_id']
    bundle={key:json.loads((folder/file).read_text(encoding='utf-8')) for key,file in
            {'paper_meta':'paper-meta.json','chunks':'chunks.json','reference_entries':'reference-entries.json','citation_links':'citation-links.json'}.items()}
    labels=json.loads((ROOT/'tests/item04/reference_labels.json').read_text(encoding='utf-8'))
    positive=set(labels['positive_numbers']); negative=set(labels['negative_numbers'])
    assert positive.isdisjoint(negative) and positive|negative==set(range(1,41))
    before=json.loads((BASE/'reference-plan-before.json').read_text(encoding='utf-8'))
    after=rank_references(bundle)
    def metrics(rows):
        selected={r['reference']['number'] for r in rows[:10]}
        tp=len(selected&positive);fp=len(selected&negative);fn=len(positive-selected);tn=len(negative-selected)
        return {'top_10':[r['reference']['number'] for r in rows[:10]],'true_positive':tp,'false_positive':fp,'false_negative':fn,'true_negative':tn,
                'precision_at_10':tp/10,'recall_at_10':tp/len(positive),'binary_accuracy_at_top10_threshold':(tp+tn)/40}
    result={'rubric':labels,'before_frequency':metrics(before),'after_context':metrics(after),
            'limits':'One official paper, single agent reviewer, labels fixed before new scoring. Not independent or population accuracy; no inference about citation intent.'}
    write(BASE/'reference-evaluation.json',result);write(BASE/'reference-plan-after-local.json',after)
    print(json.dumps({k:v for k,v in result.items() if k not in ['rubric']},ensure_ascii=False))
