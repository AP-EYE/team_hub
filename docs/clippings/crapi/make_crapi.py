import base64, html, os, re, sys

ROOT = sys.argv[1]
LOGO = os.path.join(ROOT, 'clippings', 'logos', 'owasp.svg')
svg = open(LOGO, encoding='utf-8').read()
svg = re.sub(r'<svg ', '<svg fill="#FFFFFF" ', svg, count=1)
owasp = 'data:image/svg+xml,' + base64.b64encode(svg.encode()).decode()

MONO = 'Consolas'
RED_HL = 'background:#4A1D22;color:#FF8A8F;'
cells = []
_id = [0]


def cell(value, style, x, y, w, h):
    _id[0] += 1
    cells.append(
        f'        <mxCell id="c{_id[0]}" value="{html.escape(value, quote=True)}" style="{style}" vertex="1" parent="1">\n'
        f'          <mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry" />\n'
        f'        </mxCell>\n')


TEXT = 'text;html=1;whiteSpace=wrap;verticalAlign=top;align=left;'
cell('', 'rounded=1;arcSize=4;html=1;fillColor=#2A2A2D;strokeColor=none;', 0, 60, 1760, 730)

# header chip
cell('OWASP crAPI', 'shape=label;rounded=1;arcSize=50;html=1;fillColor=#36363A;strokeColor=none;fontColor=#E5E7EB;'
     f'fontSize=16;fontStyle=1;image={owasp};imageWidth=26;imageHeight=26;imageAlign=left;imageVerticalAlign=middle;'
     'spacingLeft=42;align=left;', 40, 88, 190, 40)
cell('로컬 Docker 환경에서 직접 재현 · 2026.09.18', TEXT + 'verticalAlign=middle;fontColor=#A1A1AA;fontSize=16;', 246, 88, 520, 40)

# request box
cell('', 'rounded=1;arcSize=5;html=1;fillColor=#1C1C1F;strokeColor=#4C8DFF;strokeWidth=2;', 40, 150, 1000, 124)
cell('<b>요청</b>&nbsp;&nbsp;<span style="color:#8FB4FF">계정 B (bob@example.com)의 토큰</span>',
     TEXT + 'fontColor=#4C8DFF;fontSize=17;', 64, 164, 900, 30)
req = ('<span style="color:#4C8DFF;font-weight:bold">GET</span> /identity/api/v2/vehicle/'
       f'<span style="{RED_HL}">8b5fc175-1918-4dff-aef2-22edc96b62da</span>/location<br>'
       '<span style="color:#A1A1AA">Authorization:</span> Bearer eyJhbGciOiJSUzI1NiJ9...'
       '&nbsp;&nbsp;<span style="color:#71717A">(sub: bob@example.com)</span>')
cell(req, TEXT + f'fontFamily={MONO};fontColor=#E5E7EB;fontSize=18;', 64, 200, 960, 70)

# status
cell('200 OK', 'rounded=1;arcSize=40;html=1;fillColor=#E5484D;strokeColor=none;fontColor=#FFFFFF;fontSize=16;fontStyle=1;'
     f'fontFamily={MONO};', 64, 290, 100, 34)
cell('계정 A의 차량인데 거절되지 않음', TEXT + 'verticalAlign=middle;fontColor=#A1A1AA;fontSize=16;', 178, 290, 500, 34)

# response box
cell('', 'rounded=1;arcSize=3;html=1;fillColor=#1C1C1F;strokeColor=#E5484D;strokeWidth=2;', 40, 340, 1000, 420)
cell('<b>응답</b>&nbsp;&nbsp;<span style="color:#FF8A8F">계정 A (alice)의 정보가 그대로 반환</span>',
     TEXT + 'fontColor=#E5484D;fontSize=17;', 64, 356, 900, 30)
k = lambda s: f'<span style="color:#8FB4FF">"{s}"</span>'
v = lambda s: f'<span style="color:#D4D4D8">"{s}"</span>'
hl = lambda s: f'<span style="{RED_HL}">{s}</span>'
body = ('{<br>'
        f'&nbsp;&nbsp;{k("carId")}: {v("8b5fc175-1918-4dff-aef2-22edc96b62da")},<br>'
        f'&nbsp;&nbsp;{k("vehicleLocation")}: {{<br>'
        f'&nbsp;&nbsp;&nbsp;&nbsp;{k("id")}: 2,<br>'
        f'&nbsp;&nbsp;&nbsp;&nbsp;{hl(k("latitude") + ": " + chr(34) + "31.284788" + chr(34))},<br>'
        f'&nbsp;&nbsp;&nbsp;&nbsp;{hl(k("longitude") + ": " + chr(34) + "-92.471176" + chr(34))}<br>'
        '&nbsp;&nbsp;},<br>'
        f'&nbsp;&nbsp;{hl(k("fullName") + ": " + chr(34) + "Alice Tester" + chr(34))},<br>'
        f'&nbsp;&nbsp;{hl(k("email") + ": " + chr(34) + "alice@example.com" + chr(34))}<br>'
        '}')
cell(body, TEXT + f'fontFamily={MONO};fontColor=#E5E7EB;fontSize=23;spacing=0;', 64, 400, 960, 350)

# right cards
cards = [
    ('대상', '차량 위치 조회 API', 'crAPI 챌린지 1 · GET /vehicle/{vehicleId}/location', '#3F3F46'),
    ('방법', '계정 B의 토큰으로 계정 A의 차량 조회', '두 계정은 서로 아무 관계가 없음', '#3F3F46'),
    ('결과', '소유자 이름 · 이메일 · 위치 좌표 노출', '위치 조회 API인데 신원 정보까지 실려 나감', '#E5484D'),
    ('분류', 'OWASP API1 BOLA + API3 BOPLA', '인가 실패와 과잉 노출이 동시에 성립', '#4C8DFF'),
]
y = 150
for label, main, sub, accent in cards:
    cell('', f'rounded=1;arcSize=8;html=1;fillColor=#333337;strokeColor={accent};strokeWidth=2;', 1080, y, 640, 140)
    cell(f'<span style="color:#A1A1AA;font-size:14px">{label}</span><br>'
         f'<b style="font-size:22px">{html.escape(main)}</b><br>'
         f'<span style="color:#A1A1AA;font-size:14px">{html.escape(sub)}</span>',
         TEXT + 'fontColor=#FFFFFF;verticalAlign=middle;', 1104, y, 600, 140)
    y += 150

xml = ('<mxfile host="app.diagrams.net">\n  <diagram id="crapi" name="crAPI 재현">\n'
       '    <mxGraphModel grid="0" page="1" pageWidth="1760" pageHeight="800" math="0" shadow="0">\n      <root>\n'
       '        <mxCell id="0" />\n        <mxCell id="1" parent="0" />\n' + ''.join(cells) +
       '      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>\n')
open(os.path.join(ROOT, 'clippings', 'crapi', 'crapi-bola.drawio'), 'w', encoding='utf-8').write(xml)
print('ok')
