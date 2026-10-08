#!/usr/bin/env python3
"""
Finmatec — SVG-kuvitusten generaattori.

Ajo:  python3 svg/generate.py
  -> kirjoittaa svg/out/*.svg (erilliset tiedostot, fallback-värit)
  -> kirjoittaa finmatec-premium-v2_7.html (v2_6 + uudet SVG:t + .ill-tyylit)

Viivakieli on sivun nykyinen: ink-1000-ääriviiva, ohut detaljiviiva, paperisävyt
pinnoilla ja YKSI sininen korostus per kuva (toiminnallinen osa: leikkuuakseli,
sekoitinakselit, kylmäaineputket). Kaikki värit tulevat tokeneista; sivulla
voittaa token, erillisessä tiedostossa fallback.

PROJEKTIO — dimetria 7°/42° (pituus 1:1, syvyys 1:2), pystymitat 1:1.
  Valittu koska etupinta pysyy lähes vääristymättömänä (7°) — koneet tunnistetaan
  etunäkymästä (ikkuna, suppilo, levypakka) — ja yläpinta + oikea pääty näkyvät
  silti. Kokeiltu isometriaa (30/30): kone näytti leluautolta ja etupinnan
  yksityiskohdat vinoutuivat lukukelvottomiksi 260 px:n kortissa.
  Näkyvät pinnat: etu (y=0), yläpinta (+z), oikea pääty (+x).
  Valo vasemmalta ylhäältä: yläpinta kirkkain, etu keskisävy, pääty varjossa.

MITAT — Finmatecin julkista mittataulukkoa ei ole. Kaikki mittasuhteet ovat
TULKINTOJA valmistajan tuotekuvista (finmatec.fi, CombiBreaker Mini Titan) ja
sivun hero-kuvasta (pystylevypakastin). Yksikkö ~ 1 dm. Ks. VARMISTETTAVAT alla.
"""
import math, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "finmatec-premium-v2_6.html"
DST = ROOT / "finmatec-premium-v2_7.html"
OUT = ROOT / "svg" / "out"

# ---------------------------------------------------------------- projektio
AX = (math.cos(math.radians(7)), math.sin(math.radians(7)))              # pituus
AY = (0.5 * math.cos(math.radians(42)), -0.5 * math.sin(math.radians(42)))  # syvyys
def P(x, y, z):
    return (x * AX[0] + y * AY[0], x * AX[1] + y * AY[1] - z)

class Scene:
    """Kerää elementit maalarin järjestyksessä ja pitää kirjaa rajauslaatikosta."""
    def __init__(self, uid):
        self.uid, self.els, self.defs, self.pts = uid, [], [], []
    def _fmt(self, pts):
        self.pts += pts
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    def poly(self, pts3, cls):
        self.els.append(f'<polygon class="{cls}" points="{self._fmt([P(*p) for p in pts3])}"/>')
    def poly2(self, pts2, cls):
        self.els.append(f'<polygon class="{cls}" points="{self._fmt(pts2)}"/>')
    def line(self, a, b, cls="d"):
        self.els.append(f'<polyline class="{cls}" points="{self._fmt([P(*a), P(*b)])}"/>')
    def path3(self, pts3, cls="d"):
        self.els.append(f'<polyline class="{cls}" points="{self._fmt([P(*p) for p in pts3])}"/>')
    def raw(self, s):
        self.els.append(s)

    def box(self, x, y, z, w, d, h, faces="ftr", top="t", front="f", right="r"):
        if "r" in faces:
            self.poly([(x+w, y, z), (x+w, y+d, z), (x+w, y+d, z+h), (x+w, y, z+h)], right)
        if "f" in faces:
            self.poly([(x, y, z), (x+w, y, z), (x+w, y, z+h), (x, y, z+h)], front)
        if "t" in faces:
            self.poly([(x, y, z+h), (x+w, y, z+h), (x+w, y+d, z+h), (x, y+d, z+h)], top)

    def ring_x(self, x, cy, cz, r, n=40):
        """Ympyrä y-z-tasossa (x = vakio), projisoituna."""
        return [P(x, cy + r * math.cos(t), cz + r * math.sin(t))
                for t in (2 * math.pi * i / n for i in range(n))]

    def cyl_x(self, x0, x1, cy, cz, r, cls="r", end="f", fins=0):
        """Vaakasylinteri x-akselin suuntaan. Vasen pääty piilossa, oikea näkyy."""
        hull = convex_hull(self.ring_x(x0, cy, cz, r) + self.ring_x(x1, cy, cz, r))
        self.poly2(hull, cls)
        for i in range(fins):  # moottorin pitkittäisrivat näkyvällä puolella
            t = math.radians(105 + 110 * (i + .5) / fins)
            yy, zz = cy + r * math.cos(t), cz + r * math.sin(t)
            self.line((x0, yy, zz), (x1, yy, zz), "d")
        if end:
            self.poly2(self.ring_x(x1, cy, cz, r), end)

    def dim_x(self, x0, x1, y, z):
        """Mittaviiva pituussuunnassa: ohut sininen viiva päätemerkein."""
        a, b = P(x0, y, z), P(x1, y, z)
        self.pts += [a, b]
        tk = .45
        self.els.append(
            f'<g class="dm"><polyline points="{a[0]:.2f},{a[1]:.2f} {b[0]:.2f},{b[1]:.2f}"/>'
            f'<polyline points="{a[0]:.2f},{a[1]-tk:.2f} {a[0]:.2f},{a[1]+tk:.2f}"/>'
            f'<polyline points="{b[0]:.2f},{b[1]-tk:.2f} {b[0]:.2f},{b[1]+tk:.2f}"/></g>')

    def svg(self, label, pad=2.5, aspect=None):
        xs = [p[0] for p in self.pts]; ys = [p[1] for p in self.pts]
        x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
        if aspect:  # keskitetään korttiin, jonka kuvasuhde tunnetaan
            w, h = x1 - x0, y1 - y0
            if w / h < aspect:
                dx = (h * aspect - w) / 2; x0 -= dx; x1 += dx
            else:
                dy = (w / aspect - h) / 2; y0 -= dy; y1 += dy
        defs = f"<defs>{''.join(self.defs)}</defs>" if self.defs else ""
        return (f'<svg class="ill" viewBox="{x0:.1f} {y0:.1f} {x1-x0:.1f} {y1-y0:.1f}" '
                f'fill="none" aria-hidden="true" data-label="{label}">{defs}{"".join(self.els)}</svg>')

def convex_hull(pts):
    pts = sorted(set((round(x, 3), round(y, 3)) for x, y in pts))
    def cross(o, a, b): return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0: hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]

# ======================================================= TUOTE 1 · CombiBreaker
def grinder():
    """CombiBreaker Mini Titan -tyyppinen murskain.
    Rakenne tuotekuvasta: jalkojen päällä suorakulmainen runko, kapeneva kaula,
    ritiläseinäinen syöttösuppilo, vasemmalla SEW-vaihdemoottori.
    TULKINTA: kaikki mitat; tarkastusikkuna (oikeassa koneessa luukku) on lisätty,
    jotta leikkuuakseli — koneen ydin — voidaan näyttää korostusvärillä."""
    s = Scene("gr")
    L0, L, D, ZB, H = 1.5, 10, 6, 4.5, 5          # runko
    for (x, y) in [(L0+.3, D-.9), (L0+L-.9, D-.9)]:  # takajalat
        s.box(x, y, 0, .6, .6, ZB)
    s.box(L0+4.5, 1.6, 2.4, 3.6, 2.8, ZB-2.4)        # poistokouru rungon alla
    for (x, y) in [(L0+.3, .3), (L0+L-.9, .3)]:      # etujalat
        s.box(x, y, 0, .6, .6, ZB)
    s.line((L0+.3, .3, 1.2), (L0+L-.3, .3, 1.2), "d")  # jalkojen poikittaistuki
    # vaihdemoottori vasemmalla: moottorisylinteri + vaihdelaatikko
    s.cyl_x(-6.2, -2.4, 3.2, ZB+2.4, 1.45, cls="r", end=None, fins=5)
    s.box(-2.6, 1.2, ZB+.6, 4.2, 4, 3.6)
    s.line((-2.6, 1.2, ZB+3.2), (1.6, 1.2, ZB+3.2), "d")
    # runko
    s.box(L0, 0, ZB, L, D, H)
    s.line((L0, 0, ZB+H-.7), (L0+L, 0, ZB+H-.7), "d")   # kansilaipan sauma
    # tarkastusikkuna + leikkuuakseli (sininen)
    wx0, wx1, wz0, wz1 = L0+3.2, L0+L-1.2, ZB+1.0, ZB+H-1.6
    s.poly([(wx0, 0, wz0), (wx1, 0, wz0), (wx1, 0, wz1), (wx0, 0, wz1)], "c")
    zc = (wz0 + wz1) / 2
    s.line((wx0+.2, 0, zc), (wx1-.2, 0, zc), "a2")
    n = 7
    for i in range(n):                                   # leikkuuterät akselilla
        x = wx0 + .7 + i * (wx1 - wx0 - 1.4) / (n - 1)
        up = 1 if i % 2 == 0 else -1
        s.poly([(x-.35, 0, zc), (x+.35, 0, zc), (x+.05, 0, zc + up * 1.05)], "af")
    for (x, z) in [(wx0-.45, wz0-.4), (wx1+.45, wz0-.4), (wx0-.45, wz1+.4), (wx1+.45, wz1+.4)]:
        s.raw(f'<circle class="bt" cx="{P(x,0,z)[0]:.2f}" cy="{P(x,0,z)[1]:.2f}" r=".32"/>')
    # kaula ja ritiläsuppilo
    ZN = ZB + H
    s.poly([(L0+2.6, .8, ZN), (L0+7.4, .8, ZN), (L0+8.4, 0, ZN+2), (L0+1.6, 0, ZN+2)], "f")
    s.poly([(L0+7.4, .8, ZN), (L0+7.4, 5.2, ZN), (L0+8.4, 6, ZN+2), (L0+8.4, 0, ZN+2)], "r")
    HX0, HX1, HZ0, HZ1 = L0+1.6, L0+8.4, ZN+2, ZN+6.2
    s.box(HX0, 0, HZ0, HX1-HX0, D, HZ1-HZ0, top="c")
    for i in range(1, 9):                                # ritilä etupinnassa
        x = HX0 + i * (HX1 - HX0) / 9
        s.line((x, 0, HZ0+.35), (x, 0, HZ1-.35), "m")
    for k in range(1, 5):
        z = HZ0 + k * (HZ1 - HZ0) / 5
        s.line((HX0+.35, 0, z), (HX1-.35, 0, z), "m")
        s.line((HX1, .35, z), (HX1, D-.35, z), "m")
    for i in range(1, 6):
        y = i * D / 6
        s.line((HX1, y, HZ0+.35), (HX1, y, HZ1-.35), "m")
    # suppilon reunalista (avoin yläpinta)
    s.path3([(HX0+.35, .35, HZ1), (HX1-.35, .35, HZ1), (HX1-.35, D-.35, HZ1)], "d")
    s.dim_x(L0, L0+L, 0, -1.4)
    return s.svg("CombiBreaker", aspect=1.25)

# ======================================================= TUOTE 2 · Twin-shaft mixer
def mixer():
    """Kaksiakselinen sekoitin. U-kaukalo jaloilla, kaksiosainen kansi (vasen puoli
    auki -> sekoitinakselit lapoineen näkyvät sinisellä), pohjaluukku, vaihdemoottori
    oikeassa päädyssä.
    TULKINTA: mittasuhteet ja kannen jako; lapojen lukumäärä ja kulma."""
    s = Scene("mx")
    L, D, ZB, H = 14, 6.4, 4, 5.4
    ZT = ZB + H
    for (x, y) in [(.6, D-1), (L-1.4, D-1)]:
        s.box(x, y, 0, .7, .7, ZB)
    s.box(5.2, 1.6, 2.2, 3.8, 3.2, ZB-2.2)           # pohjaluukku
    s.line((5.2, 1.6, 2.9), (9.0, 1.6, 2.9), "d")
    for (x, y) in [(.6, .3), (L-1.4, .3)]:
        s.box(x, y, 0, .7, .7, ZB)
    s.line((.6, .3, 1.1), (L-.7, .3, 1.1), "d")
    # avattu kansi (seisoo takareunalla, vasen puolisko)
    s.box(0, D, ZT, 6.9, .25, 4.2, faces="fr", front="t")
    s.line((.4, D, ZT+3.4), (6.5, D, ZT+3.4), "d")
    # kaukalo
    s.box(0, 0, ZB, L, D, H, top="t")
    s.line((0, 0, ZT-.6), (L, 0, ZT-.6), "d")
    # U-pohjan profiili päädyssä (kaksi kaarta)
    for cy in (D*.27, D*.73):
        r = D*.23
        arc = [(L, cy + r*math.cos(t), ZB + 2.2 + r*math.sin(t))
               for t in (math.pi + math.pi*i/16 for i in range(17))]
        s.path3(arc, "m")
    # avoin vasen puolisko: kaukalon sisäpuoli
    ox0, ox1 = .35, 6.9
    cav = [(ox0, .35, ZT), (ox1, .35, ZT), (ox1, D-.35, ZT), (ox0, D-.35, ZT)]
    s.defs.append(f'<clipPath id="mx-cav"><polygon points="{" ".join(f"{a:.2f},{b:.2f}" for a,b in (P(*p) for p in cav))}"/></clipPath>')
    s.poly(cav, "c")
    g = []
    for k, cy in enumerate((D*.3, D*.7)):
        zc = ZT - .55
        a, b = P(ox0-1, cy, zc), P(ox1+1, cy, zc)
        g.append(f'<polyline class="a2" points="{a[0]:.2f},{a[1]:.2f} {b[0]:.2f},{b[1]:.2f}"/>')
        for i in range(6):
            x = 1.0 + i * 1.1 + k * .55
            t = math.radians(40 + 70 * ((i + k) % 2))
            p0 = P(x, cy - 1.1*math.cos(t), zc + 1.1*math.sin(t))
            p1 = P(x, cy + 1.1*math.cos(t), zc - 1.1*math.sin(t))
            g.append(f'<polyline class="a" points="{p0[0]:.2f},{p0[1]:.2f} {p1[0]:.2f},{p1[1]:.2f}"/>')
            g.append(f'<circle class="af" cx="{p0[0]:.2f}" cy="{p0[1]:.2f}" r=".22"/>')
    s.raw(f'<g clip-path="url(#mx-cav)">{"".join(g)}</g>')
    # suljettu oikea kansi
    s.box(6.9, 0, ZT, L-6.9, D, .3)
    s.line((10.4, 0, ZT+.3), (10.4, D, ZT+.3), "d")
    s.box(8.4, 0, ZT+.3, 1.2, .5, .25)                 # kahva
    # vaihdemoottori oikeassa päädyssä
    s.box(L, 1.0, ZB+.8, 2.4, 4.4, 3.4)
    s.cyl_x(L+2.4, L+6.2, 3.2, ZB+2.5, 1.35, cls="r", end="t", fins=4)
    s.dim_x(0, L, 0, -1.4)
    return s.svg("Mixer", aspect=1.25)

# ======================================================= TUOTE 3 · Plate freezer
def freezer():
    """Pystylevypakastin (vrt. hero-kuva): runkokehä, pystylevyjen pakka,
    yläkehä hydrauliikalla, kylmäainejakotukit sinisellä — korostus on kylmäketju.
    TULKINTA: levyjen määrä (oikeassa koneessa tyypillisesti 15–20 asemaa),
    jakotukkien sijainti, hydrauliikkasylinterien määrä."""
    s = Scene("pf")
    L, D, HP = 16, 6.4, 9.2
    s.box(0, 0, 0, L, D, 1)                          # pohjakehä
    for x in (0, L-.8):                              # takapylväät
        s.box(x, D-.8, 1, .8, .8, 11.4)
    n = 14
    for i in range(n):                               # levypakka, edestä taakse x-järjestyksessä
        x = 1.3 + i * (L - 2.8) / (n - 1)
        s.box(x, .9, 1.5, .18, D-1.8, HP, front="f", right="t" if i == n-1 else "r")
    # kylmäainejakotukki + letkut jokaiselle levylle
    zc = 1.5 + HP + .9
    for i in range(n):
        x = 1.3 + i * (L - 2.8) / (n - 1) + .09
        s.path3([(x, 1.6, 1.5+HP), (x, 1.6, zc-.2), (x, .45, zc)], "a")
    s.line((.8, .45, zc), (L-.8, .45, zc), "a2")
    s.line((.8, .45, 1.1), (L-.8, .45, 1.1), "a2")   # paluukokooja alhaalla
    # yläkehä ja hydrauliikka
    s.box(0, 0, 12.4, L, D, 1)
    s.box(.9, .9, 13.4, L-1.8, D-1.8, .35, faces="ftr")
    for x0 in (2.2, 9.2):
        s.cyl_x(x0, x0+4.6, D/2, 14.5, .75, cls="r", end="t")
        s.box(x0+4.6, D/2-.35, 14.15, .9, .7, .7)
    for x in (0, L-.8):                              # etupylväät viimeisenä
        s.box(x, 0, 1, .8, .8, 11.4)
    s.dim_x(0, L, 0, -1.4)
    return s.svg("Plate freezer", aspect=1.25)

# ======================================================= USP-ikonit (36×36, currentColor)
ICON36 = '<svg width="36" height="36" viewBox="0 0 36 36" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">{}</svg>'
USP = [
  # 01 Engineering — mittapiirros: osa, porattu reikä, mittaviivat. Ei luettelotuote vaan mitoitettu.
  ICON36.format(
    '<rect x="5" y="11" width="20" height="20"/>'
    '<circle cx="15" cy="21" r="4.5"/>'
    '<path d="M15 15v-1.5M15 28.5V27M9 21h-1.5M22.5 21H21" stroke-width="1"/>'
    '<path d="M5 6h20M5 4v4M25 4v4" stroke-width="1"/>'
    '<path d="M30 11v20M28 11h4M28 31h4" stroke-width="1"/>'
    '<circle cx="15" cy="21" r="1.6" fill="#0027FF" stroke="none"/>'),
  # 02 Delivery — yksi sopimus (sulku) kattaa koko ketjun: suunnittelu → valmistus → asennus → tuki.
  ICON36.format(
    '<path d="M4 13V9h28v4" stroke-width="1"/>'
    '<path d="M8 23h7M19 23h7" />'
    '<circle cx="5" cy="23" r="2.5"/>'
    '<rect x="14.5" y="20.5" width="5" height="5"/>'
    '<path d="M26 23l3-3 3 3-3 3z" fill="none"/>'
    '<path d="M4 30h28" stroke-width="1" stroke-dasharray="1.5 2.5"/>'
    '<circle cx="29" cy="23" r="1.5" fill="#0027FF" stroke="none"/>'),
  # 03 Origin — tehdas sahahammaskatolla + sijaintimerkki: rakennettu siellä missä se suunnitellaan.
  ICON36.format(
    '<path d="M4 32V18l7 4v-4l7 4v-4l7 4V12h5v20z"/>'
    '<path d="M2 32h32"/>'
    '<path d="M9 27h4M17 27h4" stroke-width="1"/>'
    '<path d="M30 3.5a3.5 3.5 0 0 0-3.5 3.5c0 2.6 3.5 5.5 3.5 5.5s3.5-2.9 3.5-5.5A3.5 3.5 0 0 0 30 3.5z" stroke="#0027FF" stroke-width="1.25"/>'
    '<circle cx="30" cy="7" r="1.1" fill="#0027FF" stroke="none"/>'),
]

# ======================================================= Toimiala-ikonit (60×60, tumma pohja)
IND = '<svg viewBox="0 0 60 60" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>'
ACC = 'stroke="#7B95FF"'
INDUSTRY = [
  # 01 Meat — kiskorata, telivaunu, koukku ja riippuva kinkku luunpää ylöspäin
  IND.format(
    '<path d="M6 9h48" />'
    '<circle cx="30" cy="9" r="2.4"/>'
    f'<path d="M30 11.5v6.5" {ACC}/>'
    f'<path d="M30 18a2.5 2.5 0 1 1-2.5 2.5" {ACC}/>'
    '<circle cx="30" cy="22.5" r="2.4" stroke-width="1.25"/>'
    '<path d="M28.5 24.6l-.8 3.6M31.5 24.6l.8 3.6" stroke-width="1.25"/>'
    '<path d="M27.5 28c-6 1.5-11 7-11 13.5 0 6.5 6 11 13.5 11s13.5-4.5 13.5-11c0-6.5-5-12-11.5-13.5z"/>'
    '<path d="M19.5 44c5 4 16 4 21 0" stroke-width="1"/>'
    '<path d="M24 36c3-2 9-2 12 0" stroke-width="1" stroke-dasharray="1.5 2.5"/>'),
  # 02 Poultry — kahleketju: rata, kolme kahletta, keskimmäisessä koipi (korostus)
  IND.format(
    '<path d="M4 10h52" />'
    '<path d="M4 14h52" stroke-width="1" stroke-dasharray="2 3"/>'
    + ''.join(f'<path d="M{x} 14v6M{x-4} 20h8M{x-4} 20l1.5 12M{x+4} 20l-1.5 12"/>' for x in (13, 47))
    + f'<path d="M30 14v6M26 20h8M26 20l1.5 12M34 20l-1.5 12" {ACC}/>'
    '<path d="M28 32c-4 1-6 6-5 11 1 5 5 8 7 8s6-3 7-8c1-5-1-10-5-11" />'
    '<path d="M27.5 32h5" stroke-width="1"/>'),
  # 03 Pet food — levypakastettu raaka-ainelohko + kuppi; lohkon kerrokset = levyt
  IND.format(
    '<path d="M14 8h24l6 5H20z" stroke-width="1"/>'
    '<path d="M14 8v14l6 5V13M44 13v14H20" />'
    '<path d="M14 15l6 5M20 20h24" stroke-width="1"/>'
    '<path d="M8 38h44l-4 13H12z"/>'
    '<path d="M8 38c2-4 6-5 10-5" stroke-width="1"/>'
    '<path d="M52 38c-2-4-6-5-10-5" stroke-width="1"/>'
    f'<path d="M30 30v5" {ACC}/><path d="M27 33l3 3 3-3" {ACC}/>'
    '<circle cx="22" cy="44" r="1.4" fill="currentColor" stroke="none"/>'
    '<circle cx="30" cy="45" r="1.4" fill="currentColor" stroke="none"/>'
    '<circle cx="38" cy="44" r="1.4" fill="currentColor" stroke="none"/>'),
  # 04 Water — lietesiilo: sylinteri, kartiopohja, jalat, pinnankorkeus, poisto (korostus)
  IND.format(
    '<ellipse cx="30" cy="9" rx="13" ry="3.5"/>'
    '<path d="M17 9v26l10 9h6l10-9V9" />'
    '<path d="M17 35h26" stroke-width="1"/>'
    '<path d="M17 20c3-1.6 6.5-1.6 9.5 0s6.5 1.6 9.5 0 4.5-1.2 7 0" stroke-width="1"/>'
    '<path d="M20 26h20M22 30h16" stroke-width="1" stroke-dasharray="1.5 2.5"/>'
    '<path d="M19 37l-3 15M41 37l3 15M13 52h34" />'
    f'<path d="M30 44v5" {ACC}/>'
    f'<path d="M30 52.5c-1.6 0-2.6-1-2.6-2.4 0-1.6 2.6-4.1 2.6-4.1s2.6 2.5 2.6 4.1c0 1.4-1 2.4-2.6 2.4z" {ACC} fill="#7B95FF" stroke-width="1"/>'),
]

# ======================================================= Case-kaavio (200×200, tumma)
def case_flow():
    """Prosessivirta: raaka-aine → murskaus/jauhatus (15 t/h) → ekstruusio, liikkuvat
    kappaleet kuljettimella ja 14 viikon aikajana. Aikajanan vaiheita EI ole jaettu
    viikoille, koska jakoa ei tiedetä — vain alku ja loppu."""
    mono = 'font-family="JetBrains Mono, monospace"'
    t = []
    t.append(f'<text x="20" y="34" {mono} font-size="6.5" letter-spacing="1" fill="#7A7F88">PRODUCTION FLOW</text>')
    t.append('<circle cx="174" cy="32" r="3" fill="#0027FF"><animate attributeName="opacity" values="1;.3;1" dur="1.6s" repeatCount="indefinite"/></circle>')
    t.append(f'<text x="166" y="34.5" {mono} font-size="6" fill="#FBFAF7" text-anchor="end">RUNNING</text>')
    t.append('<path d="M20 42h160" stroke="#2E3239" stroke-width=".75"/>')
    # asemat
    st = [(20, "01", "RAW", "FROZEN BLOCKS"), (80, "02", "BREAK", "15 T/H"), (140, "03", "EXTRUDE", "EXISTING LINE")]
    for x, n, name, sub in st:
        hot = n == "02"
        t.append(f'<rect x="{x}" y="66" width="40" height="44" stroke="{"#7B95FF" if hot else "#FBFAF7"}" stroke-width="1.25" fill="{"#0027FF" if hot else "none"}" fill-opacity=".18"/>')
        t.append(f'<text x="{x}" y="60" {mono} font-size="5.5" fill="#7A7F88">{n}</text>')
        t.append(f'<text x="{x}" y="122" {mono} font-size="6.5" fill="#FBFAF7">{name}</text>')
        t.append(f'<text x="{x}" y="131" {mono} font-size="5" fill="{"#7B95FF" if hot else "#7A7F88"}">{sub}</text>')
    # glyfit asemien sisällä
    t.append('<g stroke="#FBFAF7" stroke-width="1" fill="none">'
             '<rect x="27" y="90" width="12" height="9"/><rect x="41" y="90" width="12" height="9"/><rect x="34" y="80" width="12" height="9"/>'
             '<path d="M29 94.5h8M43 94.5h8M36 84.5h8" stroke-width=".6"/></g>')
    t.append('<g stroke="#7B95FF" stroke-width="1.1" fill="none">'
             '<circle cx="93" cy="88" r="6"/><circle cx="107" cy="88" r="6"/>'
             + ''.join(f'<path d="M{93+6*math.cos(a):.1f} {88+6*math.sin(a):.1f}L{93+8.5*math.cos(a):.1f} {88+8.5*math.sin(a):.1f}"/>' for a in [i*math.pi/3 for i in range(6)])
             + ''.join(f'<path d="M{107+6*math.cos(a):.1f} {88+6*math.sin(a):.1f}L{107+8.5*math.cos(a):.1f} {88+8.5*math.sin(a):.1f}"/>' for a in [i*math.pi/3+math.pi/6 for i in range(6)])
             + '<circle cx="93" cy="88" r="1.2" fill="#7B95FF"/><circle cx="107" cy="88" r="1.2" fill="#7B95FF"/></g>')
    t.append('<g stroke="#FBFAF7" stroke-width="1" fill="none"><rect x="146" y="82" width="28" height="12"/>'
             '<path d="M150 82l3 12M155 82l3 12M160 82l3 12M165 82l3 12" stroke-width=".7"/><path d="M174 88h4"/></g>')
    # kuljettimet ja liikkuvat kappaleet
    for x0, x1 in [(60, 80), (120, 140)]:
        t.append(f'<path d="M{x0} 88H{x1}" stroke="#0027FF" stroke-width="1.25" stroke-dasharray="3 2"><animate attributeName="stroke-dashoffset" from="10" to="0" dur=".8s" repeatCount="indefinite"/></path>')
        t.append(f'<polygon points="{x1-4},85 {x1},88 {x1-4},91" fill="#0027FF"/>')
    # aikajana
    t.append(f'<text x="20" y="156" {mono} font-size="5.5" fill="#7A7F88">DESIGN → BUILD → INSTALL → COMMISSION</text>')
    t.append('<path d="M20 166H180" stroke="#2E3239" stroke-width="1"/>')
    t.append('<path d="M20 166H180" stroke="#0027FF" stroke-width="1.5" stroke-dasharray="160" stroke-dashoffset="160"><animate attributeName="stroke-dashoffset" from="160" to="0" dur="2.4s" fill="freeze" begin="0s"/></path>')
    for i in range(15):
        x = 20 + i * 160 / 14
        t.append(f'<path d="M{x:.1f} {163 if i in (0,14) else 164.5}V{169 if i in (0,14) else 167.5}" stroke="#7A7F88" stroke-width=".75"/>')
    t.append(f'<text x="20" y="178" {mono} font-size="5.5" fill="#FBFAF7">WK 01</text>')
    t.append(f'<text x="180" y="178" {mono} font-size="5.5" fill="#7B95FF" text-anchor="end">WK 14 · LIVE</text>')
    return '<svg viewBox="0 0 200 200" fill="none" aria-hidden="true">\n          ' + "\n          ".join(t) + '\n        </svg>'

# ======================================================= tyylit sivulle
ILL_CSS = """
/* Illustrations (svg/generate.py) — tokenit: pinnat paperia, viiva ink, korostus brand */
:root{--ill-top:#FFFFFF;--ill-lit:var(--paper-100);--ill-shade:var(--paper-300);--ill-cavity:var(--ink-200);--ill-line:var(--ink-1000);--ill-detail:var(--ink-500)}
.ill *{vector-effect:non-scaling-stroke;stroke-linejoin:round;stroke-linecap:round}
.ill .t,.ill .f,.ill .r,.ill .c{stroke:var(--ill-line,#0A0B0D);stroke-width:1.25}
.ill .t{fill:var(--ill-top,#FFFFFF)}
.ill .f{fill:var(--ill-lit,#FBFAF7)}
.ill .r{fill:var(--ill-shade,#E8E5DD);stroke-width:1.5}
.ill .c{fill:var(--ill-cavity,#DEE0E3)}
.ill .d{stroke:var(--ill-line,#0A0B0D);stroke-width:.75}
.ill .m{stroke:var(--ill-detail,#5A5F68);stroke-width:.6}
.ill .a{stroke:var(--brand,#0027FF);stroke-width:1}
.ill .a2{stroke:var(--brand,#0027FF);stroke-width:1.75}
.ill .af{fill:var(--brand,#0027FF)}
.ill .bt{fill:var(--ill-line,#0A0B0D)}
.ill .dm polyline{stroke:var(--brand,#0027FF);stroke-width:.75}
.pv svg.ill{width:84%;height:84%}
.pc:hover .ill .a2{stroke-width:2.25}
"""
STANDALONE = ILL_CSS.split(".pv svg.ill")[0]

# ======================================================= kokoaminen
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    prods = [grinder(), mixer(), freezer()]
    case = case_flow()
    for name, svg in zip(["product-grinder", "product-mixer", "product-freezer"], prods):
        (OUT / f"{name}.svg").write_text(re.sub(r"^<svg ([^>]*)>", lambda m: f'<svg xmlns="http://www.w3.org/2000/svg" {m.group(1)}><style>{STANDALONE}</style>', svg))
    for i, svg in enumerate(USP, 1):
        (OUT / f"usp-{i:02d}.svg").write_text(svg.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ', 1))
    for i, svg in enumerate(INDUSTRY, 1):
        (OUT / f"industry-{i:02d}.svg").write_text(svg.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" color="#0A0B0D" ', 1))
    (OUT / "case-flow.svg").write_text(case.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" style="background:#0A0B0D" ', 1))

    html = SRC.read_text()
    new = USP + INDUSTRY + prods + [case]
    it = iter(new)
    html, n = re.subn(r"<svg\b.*?</svg>", lambda m: next(it), html, flags=re.S)
    assert n == 11, n
    html = html.replace("</style>", ILL_CSS + "</style>", 1)
    DST.write_text(html)
    print(f"ok: {n} svg -> {DST.name}, erilliset -> svg/out/")

if __name__ == "__main__":
    main()

# VARMISTETTAVAT (tulkinnat — korjaa generaattoriin, ei käsin SVG:hen)
# - CombiBreaker: rungon/suppilon/moottorin mittasuhteet; tarkastusikkuna on
#   kuvituksellinen (oikeassa koneessa huoltoluukku). Terien määrä 7 on kuvitusta.
# - Sekoitin: kaukalon pituus/korkeus, kannen jako 50/50, lapojen kulmat ja määrä.
# - Levypakastin: 14 levyä (oikeassa 15–20+), jakotukin paikka edessä, 2 hydraulisylinteriä.
# - Case: aikajanan vaiheita ei jaettu viikoille (tieto puuttuu); "EXISTING LINE" tulee lainauksesta.
# - Tuotekortit eivät ole samassa mittakaavassa keskenään (kukin täyttää korttinsa) —
#   ei saa käyttää vertailukuvana.
