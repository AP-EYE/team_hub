import re, sys, os

ROOT = sys.argv[1]
src = open(os.path.join(ROOT, '아키텍처-다크.drawio'), encoding='utf-8').read()

ALWAYS = {'0', '1', 'panel', 'zNet', 'zNetl', 'legend', 'zG', 'zGl', 'mitm'} | {f'chip{i}' for i in range(7)}
STEPS = {
    1: {'zC', 'zCl', 'c1', 'c1l', 'c2', 'c2l', 'f1', 'g1', 'g1l'},
    2: {'f2', 'zA', 'zAl', 'a1', 'a1l', 'a2', 'a2l', 'a3', 'a3l'},
    3: {'f3', 'g1', 'g1l', 'zS', 'zSl', 'db', 'dbl'},
    4: {'ge1', 'g1', 'g1l', 'g2', 'g2l', 'f4', 'zA', 'zAl', 'a2', 'a2l'},
    5: {'ge2', 'g2', 'g2l', 'g3', 'g3l', 'f5', 'zS', 'zSl', 'llm', 'llml'},
    6: {'ge3', 'g3', 'g3l', 'g4', 'g4l', 'f6', 'zR', 'zRl', 'dash', 'dashl',
        'lawh', 'law1', 'law2', 'law3', 'mode1', 'mode2', 'h72', 'h72l'},
}
EDGES = {'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'ge1', 'ge2', 'ge3'}

cell_re = re.compile(r'<mxCell id="([^"]+)"([^>]*?)style="([^"]*)"')

out_dir = os.path.join(ROOT, 'clippings', 'arch-steps')
for n, active in STEPS.items():
    def repl(m):
        cid, mid, style = m.group(1), m.group(2), m.group(3)
        if cid in ALWAYS:
            return m.group(0)
        if cid in active:
            if cid in EDGES:
                style = re.sub(r'strokeWidth=\d+', 'strokeWidth=4', style)
            return f'<mxCell id="{cid}"{mid}style="{style}"'
        return f'<mxCell id="{cid}"{mid}style="{style}opacity=15;textOpacity=15;"'
    s = cell_re.sub(repl, src)
    open(os.path.join(out_dir, f'step{n}.drawio'), 'w', encoding='utf-8').write(s)
print('ok')
