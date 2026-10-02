import base64, re, sys

ROOT = sys.argv[1]
L = ROOT + '/자료/clippings/logos/'


def svg(name, color=None, stroke=None):
    s = open(L + name, encoding='utf-8').read()
    if color:
        s = re.sub(r'<svg ', f'<svg fill="{color}" ', s, count=1)
    if stroke:
        s = s.replace('currentColor', stroke)
    return 'data:image/svg+xml,' + base64.b64encode(s.encode()).decode()


def png(name):
    return 'data:image/png,' + base64.b64encode(open(L + name, 'rb').read()).decode()


BLUE = ('#EAF2FF', '#4C8DFF')
GRAY = ('#F4F4F5', '#A1A1AA')
GREEN = ('#E8F8EE', '#22C55E')


def tile(img, pal, w=48):
    return (f'shape=label;rounded=1;arcSize=18;whiteSpace=wrap;html=1;fillColor={pal[0]};'
            f'strokeColor={pal[1]};strokeWidth=3;image={img};imageWidth={w};imageHeight={w};'
            f'imageAlign=center;imageVerticalAlign=middle;')


tiles = {
    'c1': tile(svg('tb-world-www.svg', stroke='#52525B'), GRAY),
    'c2': tile(svg('tb-device-mobile.svg', stroke='#52525B'), GRAY),
    'g1': tile(svg('tb-list-details.svg', stroke='#2563EB'), BLUE),
    'g2': tile(svg('tb-user-shield.svg', stroke='#2563EB'), BLUE),
    'g3': tile(svg('presidio.svg'), BLUE, 54),
    'g4': tile(svg('tb-chart-bar.svg', stroke='#2563EB'), BLUE),
    'db': tile(svg('postgresql.svg', '#4169E1'), GREEN, 50),
    'llm': tile(svg('tb-brain.svg', stroke='#2563EB'), BLUE),
    'dash': tile(svg('nextdotjs.svg', '#000000'), GREEN, 46),
    'a1': tile(svg('tb-server.svg', stroke='#52525B'), GRAY),
    'a2': tile(svg('tb-server.svg', stroke='#52525B'), GRAY),
    'a3': tile(svg('tb-server.svg', stroke='#52525B'), GRAY),
}

p = ROOT + '/2_설계/아키텍처-다크.drawio'
s = open(p, encoding='utf-8').read()

for cid, st in tiles.items():
    s, n = re.subn(r'(<mxCell id="%s" )value="[^"]*" style="[^"]*"' % cid,
                   lambda m, st=st: m.group(1) + 'value="" style="' + st + '"', s)
    assert n == 1, cid

old = '<mxGeometry x="610" y="142" width="440" height="36" as="geometry" />'
assert old in s
s = s.replace(old, '<mxGeometry x="650" y="142" width="420" height="36" as="geometry" />', 1)

mitm = (f'        <mxCell id="mitm" value="" style="shape=image;html=1;image={png("mitmproxy.png")};imageAspect=1;" vertex="1" parent="1">\n'
        f'          <mxGeometry x="612" y="141" width="38" height="38" as="geometry" />\n'
        f'        </mxCell>\n')

chip_style = ('shape=label;rounded=1;arcSize=50;html=1;fillColor=#36363A;strokeColor=none;fontColor=#D4D4D8;'
              'fontSize=15;fontStyle=1;image={img};imageWidth=26;imageHeight=26;imageAlign=left;'
              'imageVerticalAlign=middle;spacingLeft=40;align=left;')
chips = [
    ('mitmproxy', png('mitmproxy.png'), 150),
    ('Presidio', svg('presidio.svg'), 140),
    ('PostgreSQL', svg('postgresql.svg', '#4169E1'), 160),
    ('Next.js', svg('nextdotjs.svg', '#FFFFFF'), 130),
    ('Docker Compose', svg('docker.svg', '#2496ED'), 200),
    ('OWASP crAPI', svg('owasp.svg', '#FFFFFF'), 170),
    ('VAmPI', svg('tb-server.svg', stroke='#D4D4D8'), 120),
]
gap = 16
total = sum(c[2] for c in chips) + gap * (len(chips) - 1)
x = 30 + (1700 - total) // 2
cells = ''
for i, (name, img, w) in enumerate(chips):
    cells += (f'        <mxCell id="chip{i}" value="{name}" style="{chip_style.format(img=img)}" vertex="1" parent="1">\n'
              f'          <mxGeometry x="{x}" y="862" width="{w}" height="40" as="geometry" />\n'
              f'        </mxCell>\n')
    x += w + gap

s, n = re.subn(r'        <mxCell id="stack".*?</mxCell>\n', lambda m: mitm + cells, s, flags=re.S)
assert n == 1, 'stack'
open(p, 'w', encoding='utf-8').write(s)
print('done')
