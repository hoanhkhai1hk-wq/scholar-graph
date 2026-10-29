"""Anchored logical graphs -> three real scripts, with a strict generated-subset parser."""
import json
import re
from collections import Counter

from .errors import PipelineError
from .validation import chunk_anchor


def invalid(message):
    raise PipelineError('VALIDATION_ERROR', message)


def latex_escape(text):
    escapes = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}', '$': r'\$', '&': r'\&',
               '#': r'\#', '%': r'\%', '_': r'\_', '^': r'\textasciicircum{}', '~': r'\textasciitilde{}'}
    return ''.join(escapes.get(char, char) for char in text)


def mermaid_escape(text):
    return ''.join('#' + str(ord(c)) + ';' if c in '"[]{}|<>&#\\' else c for c in text)


def balanced(script, *, tex=False):
    stack, quote, index = [], False, 0
    while index < len(script):
        char = script[index]
        if char == '\\':
            # TeX escaped delimiters and JSON escaped quotes are literals.
            if index + 1 < len(script) and script[index + 1] in '{}[]()"\\%':
                index += 2
                continue
        if char == '"' and not tex:
            quote = not quote
        if not quote:
            if char in '([{': stack.append(char)
            elif char in ')]}':
                if not stack or stack.pop() != {')':'(',']':'[','}':'{'}[char]:
                    return False
        index += 1
    return not quote and not stack


def parse_script(script, kind):
    """Reject any line outside the documented, deliberately small output grammar.

    This is format self-check, not a claim to implement arbitrary TeX/DOT/Mermaid.
    Labels and graph equivalence are checked independently after parsing.
    """
    if kind=='matplotlib':
        from .topology_matplotlib import parse
        return parse(script)
    if not isinstance(script, str) or not balanced(script, tex=kind=='tikz'):
        invalid('拓扑脚本括号或引号未配对。')
    lines = script.splitlines()
    nodes, edges = {}, []
    quoted = r'"(?:[^"\\]|\\.)*"'
    if kind == 'dot':
        if lines[:2] != ['digraph ScholarGraph {', '  rankdir=TB;'] or lines[-1:] != ['}']:
            invalid('DOT缺少digraph/rankdir或完整外壳。')
        body = lines[2:-1]
        node_re = re.compile(r'  (n\d+) \[label=(' + quoted + r')\];')
        edge_re = re.compile(r'  (n\d+) -> (n\d+) \[label=(' + quoted + r')\];')
        decode = json.loads
    elif kind == 'mermaid':
        if lines[:1] != ['flowchart TD']:
            invalid('Mermaid缺少flowchart TD。')
        body = lines[1:]
        node_re = re.compile(r'  (n\d+)\["([^"\n]*)"\]')
        edge_re = re.compile(r'  (n\d+) -->\|"([^"\n]*)"\| (n\d+)')
        decode = lambda text: re.sub(r'#(\d+);', lambda m: chr(int(m.group(1))), text)
    elif kind == 'tikz':
        prefix = [r'\documentclass{ctexart}', r'\usepackage{tikz}', r'\begin{document}',
                  r'\begin{tikzpicture}[every node/.style={draw,rounded corners,align=center,text width=42mm}]']
        suffix = [r'\end{tikzpicture}', r'\end{document}']
        if lines[:4] != prefix or lines[-2:] != suffix:
            invalid('TikZ缺少文档、tikzpicture或关键字。')
        body = lines[4:-2]
        node_re = re.compile(r'\\node \((n\d+)\) at \((-?\d+),(-?\d+)\) \{(.*)\};')
        edge_re = re.compile(r'\\draw\[->\] \((n\d+)\) -- node\[above,draw=none\] \{(.*)\} \((n\d+)\);')
        escapes = {latex_escape(c):c for c in '\\{}$&#%_^~'}
        def decode(text):
            pattern = '|'.join(re.escape(s) for s in sorted(escapes, key=len, reverse=True))
            return re.sub(pattern, lambda m: escapes[m.group()], text)
    else:
        invalid('不支持的拓扑脚本格式。')
    for line in body:
        node, edge = node_re.fullmatch(line), edge_re.fullmatch(line)
        if node:
            identity = node.group(1)
            if identity in nodes:
                invalid('脚本重复声明节点。')
            label = node.group(4) if kind == 'tikz' else node.group(2)
            nodes[identity] = decode(label)
        elif edge:
            if kind == 'dot': left, right, label = edge.groups()
            else: left, label, right = edge.groups()
            edges.append((left, right, decode(label)))
        else:
            invalid('脚本含无法解析的语句。')
    if not nodes or any(left not in nodes or right not in nodes for left,right,_ in edges):
        invalid('脚本为空或边引用未声明的节点。')
    return nodes, edges


def scripts_for(nodes, edges):
    aliases = {node['id']:'n'+str(i) for i,node in enumerate(nodes)}
    dot = ['digraph ScholarGraph {', '  rankdir=TB;']
    mermaid = ['flowchart TD']
    tikz = [r'\documentclass{ctexart}', r'\usepackage{tikz}', r'\begin{document}',
            r'\begin{tikzpicture}[every node/.style={draw,rounded corners,align=center,text width=42mm}]']
    for i, node in enumerate(nodes):
        name, label = aliases[node['id']], node['label']
        dot.append(f'  {name} [label={json.dumps(label,ensure_ascii=False)}];')
        mermaid.append(f'  {name}["{mermaid_escape(label)}"]')
        row = node.get('row') if node.get('row') is not None else i
        tikz.append(r'\node (' + name + ') at (' + str(node.get('column',0)*6) + ',' +
                    str(-row*2) + ') {' + latex_escape(label) + '};')
    for edge in edges:
        left,right,label = aliases[edge['from_id']], aliases[edge['to_id']], edge['label']
        dot.append(f'  {left} -> {right} [label={json.dumps(label,ensure_ascii=False)}];')
        mermaid.append(f'  {left} -->|"{mermaid_escape(label)}"| {right}')
        tikz.append(r'\draw[->] (' + left + ') -- node[above,draw=none] {' + latex_escape(label) + '} (' + right + ');')
    dot.append('}')
    tikz += [r'\end{tikzpicture}', r'\end{document}']
    from .topology_matplotlib import script_for
    return {**{k:'\n'.join(v)+'\n' for k,v in [('dot',dot),('mermaid',mermaid),('tikz',tikz)]},
            'matplotlib':script_for(nodes,edges,aliases)}, aliases


def generate_topology(repository, body):
    if len(body.paper_ids) != len(set(body.paper_ids)):
        invalid('论文集合不可重复。')
    bundles = [repository.paper(pid) for pid in body.paper_ids]
    chunks = {c['chunk_id']:c for b in bundles for c in b['chunks']}
    def anchors(ids):
        if any(cid not in chunks for cid in ids):
            invalid('拓扑依据必须指向所选论文的真实Chunk。')
        values = [chunk_anchor(chunks[cid]) for cid in dict.fromkeys(ids)]
        for value in values: repository.gate.anchor(value,bundles)
        return values
    if body.logic:
        nodes = [node.model_dump() for node in body.logic.nodes]
        edges = [edge.model_dump() for edge in body.logic.edges]
        source = 'user_anchored_logic'
    else:
        value = body.framework
        repository.gate.record('FrameworkOutline',value)
        if set(value['paper_ids']) != set(body.paper_ids):
            invalid('框架与所选论文不一致。')
        nodes,edges = [],[]
        for i,chapter in enumerate(value['chapters']):
            for anchor in chapter['anchors']: repository.gate.anchor(anchor,bundles)
            for point in chapter['writing_points']:
                repository.gate.anchor(point['anchor'],bundles,quote=point['text'])
            nodes.append({'id':'chapter'+str(i),'label':chapter['title'], 'column':0,'row':i,
                          'source_chunk_ids':[a['chunk_id'] for a in chapter['anchors']]})
            if i:
                edges.append({'from_id':nodes[i-1]['id'],'to_id':nodes[i]['id'],'label':'chapter order',
                              'source_chunk_ids':nodes[i-1]['source_chunk_ids']+nodes[i]['source_chunk_ids']})
        source = 'framework_chapter_order_not_causality'
    ids = [node['id'] for node in nodes]
    if not nodes or len(set(ids)) != len(ids) or any(e['from_id'] not in ids or e['to_id'] not in ids for e in edges):
        invalid('逻辑节点标识重复或边引用缺失节点。')
    for item in nodes+edges:
        item['anchors'] = anchors(item['source_chunk_ids'])
    scripts, aliases = scripts_for(nodes,edges)
    expected_nodes = {aliases[n['id']]:n['label'] for n in nodes}
    expected_edges = Counter((aliases[e['from_id']],aliases[e['to_id']],e['label']) for e in edges)
    results = []
    for kind in body.formats:
        parsed_nodes, parsed_edges = parse_script(scripts[kind],kind)
        if parsed_nodes != expected_nodes or Counter(parsed_edges) != expected_edges:
            invalid('脚本解析结果与输入拓扑不一致，未发布脚本。')
        results.append({'format':kind,'script':scripts[kind], 'validation':{
            'passed':True,'parser':'generated_subset_v1','balanced':True,
            'node_count':len(parsed_nodes),'edge_count':len(parsed_edges),
            'compiler_executed':False}})
    return {'nodes':nodes,'edges':edges,'scripts':results,
            'metadata':{'generator':'deterministic_renderers','source':source,'script_ids':aliases,
                        'validation_scope':'supported_generated_grammar_not_general_compilation'}}
