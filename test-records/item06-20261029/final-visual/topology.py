import json
import os
import textwrap
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

graph = json.loads('{"nodes":[{"id":"n0","label":"输入符号序列","x":0,"y":0},{"id":"n1","label":"嵌入与位置编码相加","x":4,"y":0},{"id":"n2","label":"编码器自注意力层","x":8,"y":0},{"id":"n3","label":"前馈网络子层","x":12,"y":0},{"id":"n4","label":"编码器堆叠输出","x":16,"y":0},{"id":"n5","label":"解码器掩码自注意力","x":8,"y":-2},{"id":"n6","label":"编码器-解码器注意力","x":12,"y":-2},{"id":"n7","label":"解码器输出表示","x":16,"y":-2},{"id":"n8","label":"线性变换与Softmax预测","x":20,"y":-2},{"id":"n9","label":"自回归输出序列","x":24,"y":-2}],"edges":[{"from_id":"n0","to_id":"n1","label":"嵌入转换"},{"from_id":"n1","to_id":"n2","label":"输入编码器"},{"from_id":"n2","to_id":"n3","label":"子层串联"},{"from_id":"n3","to_id":"n4","label":"堆叠形成记忆"},{"from_id":"n1","to_id":"n5","label":"输出嵌入输入解码器"},{"from_id":"n4","to_id":"n6","label":"提供键值记忆"},{"from_id":"n5","to_id":"n6","label":"查询来自解码器"},{"from_id":"n6","to_id":"n7","label":"解码器层输出"},{"from_id":"n7","to_id":"n8","label":"线性投影"},{"from_id":"n8","to_id":"n9","label":"逐词生成"},{"from_id":"n9","to_id":"n5","label":"自回归反馈"}]}')
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
    ax.text(x,y,"\n".join(textwrap.wrap(node["label"],width=10)),ha="center",va="center",fontproperties=font,fontsize=8.5,color="#183d34")
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
