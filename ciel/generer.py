import random, urllib.parse
random.seed(7)
W,H=400,170
def clouds(id_, freq, octaves, seed, slope, intercept, color, opacity=1, fy=None, extra=''):
    fy = fy or freq
    # nuages : bruit fractal -> alpha seuillé, teinte + ombrage par un 2e bruit
    return f'''<filter id="{id_}" x="0" y="0" width="100%" height="100%">
<feTurbulence type="fractalNoise" baseFrequency="{freq} {fy}" numOctaves="{octaves}" seed="{seed}" result="n"/>
<feColorMatrix in="n" type="matrix" values="0 0 0 0 {color[0]}  0 0 0 0 {color[1]}  0 0 0 0 {color[2]}  {slope} 0 0 0 {intercept}" result="c"/>
<feTurbulence type="fractalNoise" baseFrequency="{freq*2.2} {fy*2.2}" numOctaves="3" seed="{seed+3}" result="n2"/>
<feColorMatrix in="n2" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.6 1.0" result="sh"/>
<feComposite in="sh" in2="c" operator="in" result="sh2"/>
<feMerge><feMergeNode in="c"/><feMergeNode in="sh2"/></feMerge>{extra}
</filter><rect width="{W}" height="{H}" filter="url(#{id_})" opacity="{opacity}"/>'''
def sky(top,bot,id_='s'):
    return f'<linearGradient id="{id_}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bot}"/></linearGradient>'
def svg(defs, body):
    s=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice"><defs>{defs}</defs>{body}</svg>'
    return s
def sun(cx,cy,r=18,glow=110,op=1):
    return (f'<radialGradient id="g" cx="{cx}" cy="{cy}" r="{glow}" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#fffbe6" stop-opacity="{op}"/><stop offset=".12" stop-color="#fff4c2" stop-opacity="{.9*op}"/><stop offset=".35" stop-color="#ffe08a" stop-opacity="{.35*op}"/><stop offset="1" stop-color="#ffd36b" stop-opacity="0"/></radialGradient>',
            f'<rect width="{W}" height="{H}" fill="url(#g)"/><circle cx="{cx}" cy="{cy}" r="{r*.75:.0f}" fill="#fffdf2" opacity="{op}"/>')
def rain(n, dark=False, ang=-0.25):
    out=[]
    for _ in range(n):
        x=random.uniform(-20,W+20); y=random.uniform(-20,H); L=random.uniform(10,26); o=random.uniform(.18,.45)
        out.append(f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{x+L*ang:.1f}" y2="{y+L:.0f}" stroke="#dfe8f0" stroke-opacity="{o:.2f}" stroke-width="{random.uniform(.6,1.2):.1f}" stroke-linecap="round"/>')
    return ''.join(out)
def stars(n):
    out=[]
    for _ in range(n):
        x=random.uniform(0,W); y=random.uniform(0,H*.85); r=random.choice([.4,.5,.6,.7,.9,1.2]); o=random.uniform(.35,1)
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="#fff" opacity="{o:.2f}"/>')
    return ''.join(out)
def flakes(n):
    out=[]
    for _ in range(n):
        x=random.uniform(0,W); y=random.uniform(0,H); r=random.uniform(.8,2.6); o=random.uniform(.5,.95)
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="#fff" opacity="{o:.2f}" filter="url(#b)"/>')
    return ''.join(out)
BL='<filter id="b"><feGaussianBlur stdDeviation=".5"/></filter>'
S={}
gd,gb=sun(330,40)
S['soleil']=svg(sky('#2b74c7','#8cc4ee')+gd+clouds('c',.012,4,11,1.6,-1.05,(1,1,1)), f'<rect width="{W}" height="{H}" fill="url(#s)"/>'+gb+f'<rect width="{W}" height="{H}" filter="url(#c)" opacity=".5"/>')
S['soleil']=S['soleil'].replace(f'<rect width="{W}" height="{H}" filter="url(#c)" opacity="1"/>','')
gd,gb=sun(320,35,glow=90,op=.85)
S['eclaircies']=svg(sky('#3a80c4','#a3cbe8')+gd+clouds('c',.009,5,4,4.5,-2.0,(.99,.99,1)), f'<rect width="{W}" height="{H}" fill="url(#s)"/>'+gb)
S['couvert']=svg(sky('#7d8994','#b5bec6')+clouds('c',.008,5,8,3.0,-0.6,(.88,.9,.92)), f'<rect width="{W}" height="{H}" fill="url(#s)"/>')
S['pluie']=svg(sky('#3f4b57','#6e7c88')+clouds('c',.008,5,2,2.0,-0.3,(.42,.47,.52)), f'<rect width="{W}" height="{H}" fill="url(#s)"/>'+'@@'+rain(110))
S['orage']=svg(sky('#22232f','#4a4b5e')+clouds('c',.008,5,5,2.2,-0.25,(.3,.3,.38))+'<radialGradient id="l" cx=".7" cy=".3" r=".45"><stop offset="0" stop-color="#cfd3ff" stop-opacity=".45"/><stop offset="1" stop-color="#cfd3ff" stop-opacity="0"/></radialGradient>',
    f'<rect width="{W}" height="{H}" fill="url(#s)"/>'+f'<rect width="{W}" height="{H}" fill="url(#l)"/>'+'@@'+rain(90))
S['neige']=svg(sky('#8796a6','#c9d3dc')+clouds('c',.009,5,9,2.0,-0.3,(.9,.92,.95))+BL, f'<rect width="{W}" height="{H}" fill="url(#s)"/>'+'@@'+flakes(90))
S['brouillard']=svg(sky('#a4acb3','#d3d8dc')+clouds('c',.004,4,6,1.6,-0.2,(.95,.96,.97),fy=.03), f'<rect width="{W}" height="{H}" fill="url(#s)"/>')
S['nuit']=svg(sky('#081227','#1f3763')+'<radialGradient id="m" cx=".86" cy=".22" r=".22"><stop offset="0" stop-color="#fff8dc" stop-opacity=".9"/><stop offset=".12" stop-color="#fff2c4" stop-opacity=".55"/><stop offset="1" stop-color="#9fb6e0" stop-opacity="0"/></radialGradient>',
    f'<rect width="{W}" height="{H}" fill="url(#s)"/>'+stars(140)+f'<rect width="{W}" height="{H}" fill="url(#m)"/><circle cx="{W*.86:.0f}" cy="{H*.22:.0f}" r="10" fill="#fff6d6"/>')
S['nuitcouv']=svg(sky('#141b26','#2f3a48')+clouds('c',.009,5,3,2.0,-0.3,(.33,.37,.43)), f'<rect width="{W}" height="{H}" fill="url(#s)"/>')
# insérer les nuages (filtre) au bon endroit : après le ciel, avant la pluie/neige
for k,v in S.items():
    if 'id="c"' in v:
        layer=f'<rect width="{W}" height="{H}" filter="url(#c)"/>'
        if k=='soleil': layer=f'<rect width="{W}" height="{H}" filter="url(#c)" opacity=".55"/>'
        v = v.replace('@@', layer) if '@@' in v else v.replace('</svg>', layer+'</svg>')
    S[k]=v.replace('@@','')
css=[]
for k,v in S.items():
    uri="data:image/svg+xml,"+urllib.parse.quote(v, safe=":/=,;()' ")
    css.append(f'  .nowhead.a-{k} {{ background:linear-gradient(100deg,rgba(0,0,0,.32),rgba(0,0,0,.08) 70%),#5a6b7b url("{uri}") center/cover; }}')
open('/dev/null','w').write('\n'.join(css)+'\n')
for k,v in S.items(): open(f'{k}.svg','w').write(v)
print(sum(len(c) for c in css))
