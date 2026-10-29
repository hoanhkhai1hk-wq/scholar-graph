"""A deterministic, inspectable Python renderer; never execute model-supplied code."""
import ast,json
from .errors import PipelineError

BODY='''import json
import os
import textwrap
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

graph = json.loads(__PAYLOAD__)
font_path = os.environ.get("SCHOLAR_GRAPH_FONT", "")
if not font_path:
    for candidate in ["C:/Windows/Fonts/msyh.ttc", "/app/fonts/cjk.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:
        if os.path.isfile(candidate):
            font_path = candidate
            break
font = FontProperties(fname=font_path) if font_path else FontProperties(family="DejaVu Sans")
positions = {n["id"]: (n["x"], n["y"]) for n in graph["nodes"]}
xs,ys = zip(*positions.values())
fig = Figure(figsize=(min(24,max(10,(max(xs)-min(xs))/2+2)),min(24,max(5,(max(ys)-min(ys))*1.25+2.5))), dpi=150, layout="constrained")
canvas = FigureCanvasAgg(fig)
ax = fig.subplots()
patches = {}
for node in graph["nodes"]:
    x, y = positions[node["id"]]
    patch = FancyBboxPatch((x-1.4,y-0.32),2.8,0.64,boxstyle="round,pad=0.05",facecolor="#e4eeea",edgecolor="#14544b")
    patches[node["id"]] = patch
    ax.add_patch(patch)
    ax.text(x,y,"\\n".join(textwrap.wrap(node["label"],width=10)),ha="center",va="center",fontproperties=font,fontsize=8.5,color="#183d34")
for edge in graph["edges"]:
    a, b = positions[edge["from_id"]], positions[edge["to_id"]]
    feedback = a[1]==b[1] and b[0]<a[0]
    ax.add_patch(FancyArrowPatch(a,b,patchA=patches[edge["from_id"]],patchB=patches[edge["to_id"]],connectionstyle="arc3,rad=0.15" if feedback else "arc3,rad=0",arrowstyle="-|>",mutation_scale=15,color="#718b7e",shrinkA=4,shrinkB=5))
    offset = (abs(a[0]-b[0])*0.15/2+0.1) if feedback else (0.55 if a[1]==b[1] else 0.1)
    ax.text((a[0]+b[0])/2,(a[1]+b[1])/2+offset,edge["label"],ha="center",fontproperties=font,fontsize=8,color="#41584d",bbox={"facecolor":"white","edgecolor":"none","alpha":0.9,"pad":1})
ax.set_xlim(min(xs)-2,max(xs)+2)
ax.set_ylim(min(ys)-0.9,max(ys)+0.9)
ax.axis("off")
canvas.print_png("topology.png")
print("Rendered topology.png:",len(graph["nodes"]),"nodes,",len(graph["edges"]),"edges")
'''

def render_payload(payload):
    return BODY.replace('__PAYLOAD__',repr(json.dumps(payload,ensure_ascii=False,separators=(',',':'))))

def script_for(nodes,edges,aliases):
    data={'nodes':[{'id':aliases[n['id']],'label':n['label'],'x':n.get('column',0)*4,
                   'y':-2*(n.get('row') if n.get('row') is not None else i)} for i,n in enumerate(nodes)],
          'edges':[{'from_id':aliases[e['from_id']],'to_id':aliases[e['to_id']],'label':e['label']} for e in edges]}
    return render_payload(data)

def parse(script):
    try:
        tree=ast.parse(script)
        assignments=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='graph' for t in n.targets)]
        if len(assignments)!=1:raise ValueError()
        value=assignments[0].value
        if (not isinstance(value,ast.Call) or ast.unparse(value.func)!='json.loads' or len(value.args)!=1 or value.keywords):raise ValueError()
        payload=json.loads(ast.literal_eval(value.args[0]))
        if script!=render_payload(payload) or set(payload)!={'nodes','edges'}:raise ValueError()
        nodes={n['id']:n['label'] for n in payload['nodes']}
        if len(nodes)!=len(payload['nodes']) or not nodes:raise ValueError()
        edges=[(e['from_id'],e['to_id'],e['label']) for e in payload['edges']]
        if any(a not in nodes or b not in nodes for a,b,_ in edges):raise ValueError()
        return nodes,edges
    except (SyntaxError,ValueError,TypeError,KeyError,AttributeError):
        raise PipelineError('VALIDATION_ERROR','Matplotlib代码不符合固定绘图模板或图结构，未发布。') from None
