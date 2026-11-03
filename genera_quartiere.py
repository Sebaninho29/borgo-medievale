# -*- coding: utf-8 -*-
"""
genera_quartiere.py  -  Quartiere medievale con piazza del mercato
Blender 5.x  -  Cycles  -  texture Poly Haven (CC0)

USO DAL PROMPT DEI COMANDI:
    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" --python "D:\\Quartiere_Mercato\\genera_quartiere.py"

Oppure in Blender: Scripting > Apri > genera_quartiere.py > Esegui (Alt+P).
Modifica i PARAMETRI qui sotto e rilancia: la scena viene ricostruita da zero.
"""
import bpy, bmesh, math, random, os, time
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

# ============================== PARAMETRI ==============================
SEED          = 11            # cambia per ottenere un quartiere diverso
CARTELLA      = r"D:\Quartiere_Mercato\Blender"   # scena .blend, textures/ e modelli/ insieme (//textures relativo)
TEXTURE       = os.path.join(CARTELLA, "textures")
MODELLI       = os.path.join(CARTELLA, "modelli")    # modelli Poly Haven (glTF) di alberi e cespugli
PIAZZA_X      = 17.0          # mezza larghezza della piazza (m)
PIAZZA_Y      = 13.0          # mezza profondita' della piazza (m)
CASE_STRADE   = True          # case lungo le strade del borgo (oltre la prima fila sulla piazza)
MARGINE_MURA  = 4.5           # distanza minima (m) delle case dall'asse delle mura
RIEMPI_ISOLATI = True         # case sul retro, cortili, rimesse e vicoli dentro gli isolati
FILE_INTERNE  = 3             # file di case sul retro, parallele a ogni strada
MURA_ALTEZZA  = 7.4           # quota del camminamento (con parapetto e merli le mura arrivano a ~9 m)
FOSSATO       = True          # fossato asciutto fuori dalle mura, con ponti di legno davanti alle porte
N_BANCARELLE  = 10
FESTONI       = True          # bandierine sopra il mercato
# insegna della Locanda del Cinghiale: scritta pirografata (primo carattere che esiste; se nessuno, quello di Blender)
INSEGNA_SCRITTA = ("LOCANDA DEL", "CINGHIALE")
INSEGNA_RUGGINE = 0.22       # saturazione della texture rusty_metal nel ferro dell'insegna (1 = ruggine piena)
INSEGNA_FONT  = [r"C:\Windows\Fonts\PERTIBD.TTF", r"C:\Windows\Fonts\CENTAUR.TTF", r"C:\Windows\Fonts\georgiab.ttf"]
SOLE_AZIMUT   = -15.0         # gradi: da dove arriva il sole (0=est, 90=nord, -90=sud); -15 = mattino, entra in Via Maestra
SOLE_EXTRA    = 1.4           # forza del sole aggiuntivo (ombre nette)
CIELO_FORZA   = 1.8           # forza dell'HDRI: luce diffusa che schiarisce le ombre
ESPOSIZIONE   = -0.3
FOSCHIA       = 0.0012        # foschia atmosferica (0 = disattivata)
CAMPIONI      = 160
RISOLUZIONE   = (1920, 1080)
SMUSSO        = True          # bordi leggermente arrotondati
CONTROLLA_APERTURE = True     # toglie finestre e porte oltre lo spigolo o contro un'altra casa
SALVA         = True
RENDER        = False         # True = renderizza subito tutte le CAMERE_FINALI in CARTELLA_RENDER
try:
    CARTELLA_RENDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render")   # accanto allo script
except NameError:
    CARTELLA_RENDER = os.path.join(CARTELLA, "render")
CAMERE_FINALI = ["Camera_Piazza", "Camera_Via_Maestra", "Camera_Chiesa", "Camera_Artigiani", "Camera_Nobili",
                 "Camera_Campagna", "Camera_Aerea"]
# =======================================================================

# ----------------------------------------------------------------------
#  PIANTA DEL BORGO (metri, ricavati da pianta_quartiere.png: origine nella fontana, nord = +Y)
# ----------------------------------------------------------------------
# vertici delle mura (torri rotonde)
MURA = [(-60.4, 82.9), (-10.1, 87.0), (40.4, 82.9), (85.8, 62.7), (109.1, 30.3), (111.1, -10.1),
        (101.0, -45.4), (70.7, -72.6), (20.2, -84.9), (-40.2, -80.6), (-75.7, -55.5), (-88.7, -10.1),
        (-85.8, 60.6)]
# strade: nome, larghezza, asse (polilinea), parametri delle case che vi si affacciano
STRADE = [
    ('Via_Maestra',     7.0, [(16.0, 0.0), (32.0, 0.6), (118.0, 16.6)],                 # verso Porta Est
     dict(piani=(2, 4), botteghe=0.5)),
    ('Via_Artigiani',   5.0, [(7.75, -12.0), (8.5, -26.0), (11.0, -40.0), (12.5, -55.0), (8.5, -92.0)],   # Porta Sud
     dict(piani=(2, 3), botteghe=0.3)),
    ('Vicolo_Chiesa',   4.0, [(-10.0, 12.0), (-10.0, 29.0)],
     dict(piani=(2, 3))),
    ('Via_Nobili',      5.0, [(-16.0, 10.5), (-27.8, 10.5), (-39.4, 13.2), (-61.7, 20.0), (-83.0, 22.9)],
     dict(piani=(2, 3), prof=(9.0, 11.0))),
    ('Via_Borgo',       4.5, [(46.0, 3.0), (49.9, -12.0), (51.8, -21.7), (61.6, -39.2), (79.0, -56.5)],
     dict(piani=(2, 2), prof=(6.0, 8.0))),
    ('Via_Sagrato',     4.0, [(7.0, 37.9), (61.6, 60.8)],
     dict(piani=(2, 3))),
    ('Stradella_Mura',  3.5, [(14.0, -53.0), (40.0, -61.0), (68.0, -67.5), (79.0, -56.5)],
     dict(piani=(2, 2), prof=(6.0, 8.0))),
]
# strade che escono dalle mura: nome della porta e stile (grande = merlata con beccatelli, sobria = a falde)
PORTE = {'Via_Maestra': ('Porta_Est', 'grande'), 'Via_Artigiani': ('Porta_Sud', 'sobria')}
SAGRATO          = (-22.1, 28.3, 8.2, 46.4)     # (x0, y0, x1, y1)
PIAZZETTA_POZZO  = (4.3, -46.4, 20.4, -36.5)
LOTTO_CHIESA      = (-18.1, 46.4, -1.9, 76.7)     # 3 Chiesa di San Michele
LOTTO_PALAZZETTO  = (-60.4, 22.5, -44.3, 36.8)    # 13 Palazzetto nobile (affacciato su Via dei Nobili)
LOTTO_TORRE_NOBILI = (-48.2, -6.0, -42.3, 3.5)    # 14 Torre dei Nobili (con la scala di legno a nord)
GIARDINI = [(-60.4, 36.8, -44.3, 60.6),           # giardino del palazzetto, dietro di esso
            (-78.6, 8.2, -62.5, 17.5), (-74.8, -16.1, -60.6, -4.1)]
ORTI = [(55.7, -52.4, 68.7, -40.4), (74.8, -46.4, 88.7, -36.5), (91.0, -38.4, 99.0, -28.3),
        (60.8, -66.4, 74.8, -58.6)]
# edifici con un ruolo (passo 4)
LOTTO_LOCANDA  = (28.5, 5.0, 42.5, 26.2)     # 5-6 Locanda del Cinghiale, cortile e stalle
LOTTO_MERCANTE = (55.7, 12.2, 68.7, 22.1)    # 7 Casa del mercante
LOTTO_FABBRO   = (14.4, -30.3, 24.3, -22.3)  # 8 Fabbro
LOTTO_FALEGNAME = (-3.9, -34.4, 6.2, -26.2)  # 9 Falegname
LOTTO_FORNO    = (-6.0, -50.5, 8.6, -42.3)   # 11 Forno e panetteria (fino al bordo di Via degli Artigiani)
LOTTO_CONCERIA = (16.3, -76.7, 28.3, -66.6)  # 12 Conceria
POZZO          = (17.0, -41.5)               # 10 Pozzo degli artigiani, nella piazzetta
# lotti da lasciare liberi per gli edifici con un ruolo, i giardini e gli orti
RISERVATI = [
    SAGRATO, PIAZZETTA_POZZO, LOTTO_CHIESA, LOTTO_PALAZZETTO, LOTTO_TORRE_NOBILI,
    LOTTO_LOCANDA, LOTTO_MERCANTE, LOTTO_FABBRO, LOTTO_FALEGNAME, LOTTO_FORNO, LOTTO_CONCERIA,
] + GIARDINI + ORTI
# zone della pianta: la prima che contiene il punto vince; fuori da tutte = stile misto (come la piazza)
ZONE = [
    ('chiesa',    [(-55.3, 80.8), (20.4, 80.8), (14.0, 24.3), (-45.2, 24.3)]),
    ('mercanti',  [(28.5, 29.7), (41.2, 40.4), (85.8, 62.7), (109.1, 30.3), (111.1, -10.1), (110.1, -21.7),
                   (40.2, -24.1), (28.5, -15.9)]),
    ('artigiani', [(-25.2, -26.0), (35.5, -26.0), (35.5, -84.9), (-40.2, -80.6), (-30.1, -55.7)]),
    ('borgo',     [(40.2, -24.1), (110.1, -21.7), (101.0, -45.4), (70.7, -72.6), (35.5, -84.0), (35.5, -26.0)]),
    ('nobili',    [(-85.8, 60.6), (-55.3, 80.8), (-45.2, 24.3), (-30.1, 24.3), (-30.1, -21.7), (-25.8, -26.0),
                   (-30.1, -55.7), (-40.2, -80.6), (-75.7, -55.5), (-88.7, -10.1)]),
]
# stile delle case per zona: stili (peso), tetto dominante (~80%), piani sul fronte e all'interno,
# botteghe, larghezza e profondita' dei lotti sul fronte, probabilita' di cortili/tettoie/orti all'interno
STILI_ZONA = {
    'mercanti':  dict(stili=(('intonaco', 0.5), ('graticcio', 0.35), ('pietra', 0.15)), tetto='coppi',
                      piani=(3, 4), piani_int=(2, 3), botteghe=0.75, larg=(5.2, 7.2), prof=(9.0, 11.0),
                      cortili=0.12),
    'artigiani': dict(stili=(('pietra', 0.5), ('graticcio', 0.5)), tetto='coppi_vecchi',
                      piani=(2, 2), piani_int=(1, 2), botteghe=0.35, larg=(5.0, 7.0), prof=(7.0, 9.0),
                      cortili=0.2, tettoie=0.45, rimesse=0.3),
    'borgo':     dict(stili=(('legno', 0.75), ('graticcio', 0.25)), tetto='paglia',
                      piani=(1, 2), piani_int=(1, 2), botteghe=0.0, larg=(4.4, 6.0), prof=(5.5, 7.0),
                      cortili=0.08, orti=0.3),
    'nobili':    dict(stili=(('pietra', 0.75), ('intonaco', 0.25)), tetto='ardesia',
                      piani=(3, 3), piani_int=(2, 3), botteghe=0.0, larg=(8.0, 11.0), prof=(10.0, 12.0),
                      cortili=0.4, palazzo=True),
    'chiesa':    dict(stili=(('intonaco', 0.55), ('pietra', 0.45)), tetto='coppi',
                      piani=(2, 3), piani_int=(2, 2), botteghe=0.1, larg=(5.5, 7.5), prof=(8.0, 10.0),
                      cortili=0.2),
}

RNG = random.Random(SEED)
RNG_D = random.Random(SEED + 1)   # solo per dettagli aggiunti dopo: non sposta la sequenza (e il borgo) di RNG
def rr(a, b): return RNG.uniform(a, b)
def rc(s): return RNG.choice(s)

def T(x, y, z): return Matrix.Translation((x, y, z))
def RZ(a): return Matrix.Rotation(a, 4, 'Z')
def RX(a): return Matrix.Rotation(a, 4, 'X')
def RY(a): return Matrix.Rotation(a, 4, 'Y')

# ----------------------------------------------------------------------
#  SCENA E COLLEZIONI
# ----------------------------------------------------------------------
def svuota_scena():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for blk in (bpy.data.meshes, bpy.data.curves, bpy.data.lights, bpy.data.cameras, bpy.data.materials):
        for b in list(blk):
            if b.users == 0:
                blk.remove(b)

def collezione(nome):
    c = bpy.data.collections.get(nome)
    if c is None:
        c = bpy.data.collections.new(nome)
        bpy.context.scene.collection.children.link(c)
    return c

# ----------------------------------------------------------------------
#  MATERIALI
# ----------------------------------------------------------------------
MAT = {}

def _n(nt, t, x, y):
    n = nt.nodes.new(t); n.location = (x, y); return n

def _in(node, name, kind=None):
    for s in node.inputs:
        if s.name == name and (kind is None or s.type == kind):
            return s
    raise KeyError(name)

def _out(node, name, kind=None):
    for s in node.outputs:
        if s.name == name and (kind is None or s.type == kind):
            return s
    raise KeyError(name)

def _mix(nt, x, y, blend='MULTIPLY'):
    m = _n(nt, 'ShaderNodeMix', x, y)
    m.data_type = 'RGBA'; m.blend_type = blend
    return m

def _tex(tex_id, chiave):
    if not tex_id or not os.path.isdir(TEXTURE):
        return None
    pref = tex_id + "_" + chiave + "_"
    for f in sorted(os.listdir(TEXTURE)):
        if f.startswith(pref):
            return os.path.join(TEXTURE, f)
    return None

def _img(nt, path, x, y, colore=True):
    n = _n(nt, 'ShaderNodeTexImage', x, y)
    n.image = bpy.data.images.load(path, check_existing=True)
    if not colore:
        n.image.colorspace_settings.name = 'Non-Color'
    return n

def nuovo_mat(nome):
    m = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    out = _n(nt, 'ShaderNodeOutputMaterial', 1500, 0)
    b = _n(nt, 'ShaderNodeBsdfPrincipled', 1150, 0)
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    MAT[nome] = m
    return m, nt, b, out

def variazione(nt, col, var, isola, x=-650, y=300):
    """Leggera variazione di tono/luminosita' per oggetto o per isola."""
    L = nt.links
    if isola:
        g = _n(nt, 'ShaderNodeNewGeometry', x - 500, y + 300); rnd = _out(g, 'Random Per Island')
    else:
        g = _n(nt, 'ShaderNodeObjectInfo', x - 500, y + 300); rnd = _out(g, 'Random')
    mv = _n(nt, 'ShaderNodeMapRange', x - 250, y + 350)
    _in(mv, 'To Min', 'VALUE').default_value = 1 - var
    _in(mv, 'To Max', 'VALUE').default_value = 1 + var
    L.new(rnd, _in(mv, 'Value', 'VALUE'))
    mh = _n(nt, 'ShaderNodeMapRange', x - 250, y + 150)
    _in(mh, 'To Min', 'VALUE').default_value = 0.5 - var * 0.2
    _in(mh, 'To Max', 'VALUE').default_value = 0.5 + var * 0.2
    L.new(rnd, _in(mh, 'Value', 'VALUE'))
    hs = _n(nt, 'ShaderNodeHueSaturation', x, y)
    L.new(_out(mv, 'Result', 'VALUE'), hs.inputs['Value'])
    L.new(_out(mh, 'Result', 'VALUE'), hs.inputs['Hue'])
    L.new(col, hs.inputs['Color'])
    return hs.outputs['Color']

def pbr(nome, tex_id, tile=2.0, tinta=(1, 1, 1), var=0.08, sporco=0.35, rugo=0.0,
        metallo=0.0, normale=1.0, colore=(0.5, 0.5, 0.5), isola=False, rilievo=0.0):
    m, nt, b, out = nuovo_mat(nome)
    L = nt.links
    tc = _n(nt, 'ShaderNodeTexCoord', -1700, 0)
    mp = _n(nt, 'ShaderNodeMapping', -1500, 0)
    mp.inputs['Scale'].default_value = (1 / tile, 1 / tile, 1 / tile)
    L.new(tc.outputs['UV'], mp.inputs['Vector'])
    fd = _tex(tex_id, 'diff')
    if fd:
        d = _img(nt, fd, -1200, 300); L.new(mp.outputs[0], d.inputs['Vector']); col = d.outputs['Color']
    else:
        rgb = _n(nt, 'ShaderNodeRGB', -1200, 300); rgb.outputs[0].default_value = (*colore, 1); col = rgb.outputs[0]
    col = variazione(nt, col, var, isola)
    mt = _mix(nt, -400, 300); _in(mt, 'Factor', 'VALUE').default_value = 1.0
    L.new(col, _in(mt, 'A', 'RGBA')); _in(mt, 'B', 'RGBA').default_value = (*tinta, 1)
    col = _out(mt, 'Result', 'RGBA')
    # sporco a macchie larghe
    no = _n(nt, 'ShaderNodeTexNoise', -700, -350)
    _in(no, 'Scale').default_value = 0.35; _in(no, 'Detail').default_value = 6
    L.new(tc.outputs['Object'], no.inputs['Vector'])
    mg = _n(nt, 'ShaderNodeMapRange', -500, -350)
    _in(mg, 'From Min', 'VALUE').default_value = 0.45; _in(mg, 'From Max', 'VALUE').default_value = 0.7
    _in(mg, 'To Max', 'VALUE').default_value = 0.22
    L.new(no.outputs['Fac'], _in(mg, 'Value', 'VALUE'))
    m1 = _mix(nt, -200, 300)
    L.new(_out(mg, 'Result', 'VALUE'), _in(m1, 'Factor', 'VALUE'))
    L.new(col, _in(m1, 'A', 'RGBA')); _in(m1, 'B', 'RGBA').default_value = (0.55, 0.5, 0.42, 1)
    col = _out(m1, 'Result', 'RGBA')
    # sporco alla base dei muri
    if sporco > 0:
        ge = _n(nt, 'ShaderNodeNewGeometry', -900, -650)
        sx = _n(nt, 'ShaderNodeSeparateXYZ', -700, -650)
        L.new(ge.outputs['Position'], sx.inputs[0])
        mz = _n(nt, 'ShaderNodeMapRange', -500, -650)
        _in(mz, 'From Min', 'VALUE').default_value = 0.0; _in(mz, 'From Max', 'VALUE').default_value = 1.4
        _in(mz, 'To Min', 'VALUE').default_value = sporco; _in(mz, 'To Max', 'VALUE').default_value = 0.0
        L.new(sx.outputs['Z'], _in(mz, 'Value', 'VALUE'))
        m2 = _mix(nt, 0, 300)
        L.new(_out(mz, 'Result', 'VALUE'), _in(m2, 'Factor', 'VALUE'))
        L.new(col, _in(m2, 'A', 'RGBA')); _in(m2, 'B', 'RGBA').default_value = (0.3, 0.27, 0.22, 1)
        col = _out(m2, 'Result', 'RGBA')
    L.new(col, b.inputs['Base Color'])
    fr = _tex(tex_id, 'rough')
    if fr:
        r = _img(nt, fr, -1200, 0, False); L.new(mp.outputs[0], r.inputs['Vector'])
        ma = _n(nt, 'ShaderNodeMath', -400, 0); ma.operation = 'ADD'; ma.use_clamp = True
        L.new(r.outputs['Color'], ma.inputs[0]); ma.inputs[1].default_value = rugo
        L.new(ma.outputs[0], b.inputs['Roughness'])
    else:
        b.inputs['Roughness'].default_value = min(1.0, 0.75 + rugo)
    b.inputs['Metallic'].default_value = metallo
    fn = _tex(tex_id, 'nor_gl')
    nrm = None
    if fn:
        ni = _img(nt, fn, -1200, -300, False); L.new(mp.outputs[0], ni.inputs['Vector'])
        nm = _n(nt, 'ShaderNodeNormalMap', -400, -300); nm.inputs['Strength'].default_value = normale
        L.new(ni.outputs['Color'], nm.inputs['Color']); nrm = nm.outputs['Normal']
    fdp = _tex(tex_id, 'disp') if rilievo > 0 else None
    if fdp:
        di = _img(nt, fdp, -1200, -600, False); L.new(mp.outputs[0], di.inputs['Vector'])
        bu = _n(nt, 'ShaderNodeBump', -150, -450)
        bu.inputs['Strength'].default_value = rilievo; bu.inputs['Distance'].default_value = 0.06
        L.new(di.outputs['Color'], bu.inputs['Height'])
        if nrm is not None:
            L.new(nrm, bu.inputs['Normal'])
        nrm = bu.outputs['Normal']
    if nrm is not None:
        L.new(nrm, b.inputs['Normal'])
    return m

def semplice(nome, colore, rugo=0.5, isola=True, var=0.15, metallo=0.0):
    m, nt, b, out = nuovo_mat(nome)
    rgb = _n(nt, 'ShaderNodeRGB', -900, 300); rgb.outputs[0].default_value = (*colore, 1)
    col = variazione(nt, rgb.outputs[0], var, isola)
    nt.links.new(col, b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rugo
    b.inputs['Metallic'].default_value = metallo
    return m

def tessuto(nome, c1, c2=None, righe=0.22):
    m, nt, b, out = nuovo_mat(nome)
    L = nt.links
    if c2 is None:
        rgb = _n(nt, 'ShaderNodeRGB', -700, 300); rgb.outputs[0].default_value = (*c1, 1); col = rgb.outputs[0]
    else:
        tc = _n(nt, 'ShaderNodeTexCoord', -1500, 300)
        sx = _n(nt, 'ShaderNodeSeparateXYZ', -1300, 300); L.new(tc.outputs['Object'], sx.inputs[0])
        a = _n(nt, 'ShaderNodeMath', -1100, 300); a.operation = 'MULTIPLY'; a.inputs[1].default_value = 1.0 / righe
        L.new(sx.outputs['X'], a.inputs[0])
        bmod = _n(nt, 'ShaderNodeMath', -900, 300); bmod.operation = 'FLOORED_MODULO'; bmod.inputs[1].default_value = 2.0
        L.new(a.outputs[0], bmod.inputs[0])
        g = _n(nt, 'ShaderNodeMath', -700, 300); g.operation = 'GREATER_THAN'; g.inputs[1].default_value = 0.999
        L.new(bmod.outputs[0], g.inputs[0])
        mx = _mix(nt, -500, 300, 'MIX')
        L.new(g.outputs[0], _in(mx, 'Factor', 'VALUE'))
        _in(mx, 'A', 'RGBA').default_value = (*c1, 1); _in(mx, 'B', 'RGBA').default_value = (*c2, 1)
        col = _out(mx, 'Result', 'RGBA')
    col = variazione(nt, col, 0.06, False, -300, 300)
    L.new(col, b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.85
    try:
        b.inputs['Sheen Weight'].default_value = 0.5
    except KeyError:
        pass
    fn = _tex('fabric_pattern_05', 'nor_gl')
    if fn:
        tc2 = _n(nt, 'ShaderNodeTexCoord', -1500, -300)
        mp = _n(nt, 'ShaderNodeMapping', -1300, -300); mp.inputs['Scale'].default_value = (4, 4, 4)
        L.new(tc2.outputs['UV'], mp.inputs['Vector'])
        ni = _img(nt, fn, -1100, -300, False); L.new(mp.outputs[0], ni.inputs['Vector'])
        nm = _n(nt, 'ShaderNodeNormalMap', -800, -300); nm.inputs['Strength'].default_value = 0.6
        L.new(ni.outputs['Color'], nm.inputs['Color']); L.new(nm.outputs['Normal'], b.inputs['Normal'])
    # tessuto sottile: un po' di luce passa attraverso
    tr = _n(nt, 'ShaderNodeBsdfTranslucent', 1150, -300); L.new(col, tr.inputs['Color'])
    ms = _n(nt, 'ShaderNodeMixShader', 1350, 0); ms.inputs[0].default_value = 0.3
    L.new(b.outputs[0], ms.inputs[1]); L.new(tr.outputs[0], ms.inputs[2])
    L.new(ms.outputs[0], out.inputs['Surface'])
    return m

def vetro():
    m, nt, b, out = nuovo_mat('vetro')
    b.inputs['Base Color'].default_value = (0.015, 0.02, 0.022, 1)
    b.inputs['Roughness'].default_value = 0.1
    no = _n(nt, 'ShaderNodeTexNoise', 500, -300); _in(no, 'Scale').default_value = 9
    bu = _n(nt, 'ShaderNodeBump', 800, -300); bu.inputs['Strength'].default_value = 0.12
    nt.links.new(no.outputs['Fac'], bu.inputs['Height']); nt.links.new(bu.outputs['Normal'], b.inputs['Normal'])

def acqua():
    m, nt, b, out = nuovo_mat('acqua')
    b.inputs['Base Color'].default_value = (0.05, 0.1, 0.09, 1)
    b.inputs['Roughness'].default_value = 0.02
    b.inputs['IOR'].default_value = 1.33
    try:
        b.inputs['Transmission Weight'].default_value = 0.85
    except KeyError:
        pass
    no = _n(nt, 'ShaderNodeTexNoise', 500, -300); _in(no, 'Scale').default_value = 4; _in(no, 'Detail').default_value = 3
    bu = _n(nt, 'ShaderNodeBump', 800, -300); bu.inputs['Strength'].default_value = 0.08
    nt.links.new(no.outputs['Fac'], bu.inputs['Height']); nt.links.new(bu.outputs['Normal'], b.inputs['Normal'])

def acqua_getto():
    m, nt, b, out = nuovo_mat('acqua_getto')
    b.inputs['Base Color'].default_value = (0.8, 0.88, 0.9, 1)
    b.inputs['Roughness'].default_value = 0.05
    b.inputs['Alpha'].default_value = 0.55
    try:
        b.inputs['Transmission Weight'].default_value = 0.3
    except KeyError:
        pass

def con_erba(m, quota=0.48):
    """Aggiunge chiazze d'erba (tinta verde sulla stessa texture) a un materiale fatto con pbr()."""
    nt = m.node_tree; L = nt.links
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    src = b.inputs['Base Color'].links[0].from_socket
    tc = _n(nt, 'ShaderNodeTexCoord', -900, -900)
    no = _n(nt, 'ShaderNodeTexNoise', -700, -900)
    _in(no, 'Scale').default_value = 0.22; _in(no, 'Detail').default_value = 6
    L.new(tc.outputs['Object'], no.inputs['Vector'])
    mr = _n(nt, 'ShaderNodeMapRange', -500, -900)
    _in(mr, 'From Min', 'VALUE').default_value = quota - 0.04; _in(mr, 'From Max', 'VALUE').default_value = quota + 0.04
    L.new(no.outputs['Fac'], _in(mr, 'Value', 'VALUE'))
    verde = _mix(nt, 300, 500); _in(verde, 'Factor', 'VALUE').default_value = 1.0
    L.new(src, _in(verde, 'A', 'RGBA')); _in(verde, 'B', 'RGBA').default_value = (0.38, 0.62, 0.2, 1)
    mx = _mix(nt, 600, 400, 'MIX')
    L.new(_out(mr, 'Result', 'VALUE'), _in(mx, 'Factor', 'VALUE'))
    L.new(src, _in(mx, 'A', 'RGBA')); L.new(_out(verde, 'Result', 'RGBA'), _in(mx, 'B', 'RGBA'))
    L.new(_out(mx, 'Result', 'RGBA'), b.inputs['Base Color'])

def _base(m):
    """Albero dei nodi, BSDF e presa che oggi arriva al Base Color di un materiale fatto con pbr()."""
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    return nt, b, b.inputs['Base Color'].links[0].from_socket

def _intervallo(nt, val, a, b, c=0.0, d=1.0, x=0, y=0):
    mr = _n(nt, 'ShaderNodeMapRange', x, y)
    _in(mr, 'From Min', 'VALUE').default_value = a; _in(mr, 'From Max', 'VALUE').default_value = b
    _in(mr, 'To Min', 'VALUE').default_value = c; _in(mr, 'To Max', 'VALUE').default_value = d
    nt.links.new(val, _in(mr, 'Value', 'VALUE'))
    return _out(mr, 'Result', 'VALUE')

def macchie(m, scala, ca, cb):
    """Variazione di tono a grande scala: spezza la ripetizione della texture sulle superfici ampie."""
    nt, b, src = _base(m); L = nt.links
    tc = _n(nt, 'ShaderNodeTexCoord', -900, 900); no = _n(nt, 'ShaderNodeTexNoise', -700, 900)
    _in(no, 'Scale').default_value = scala; _in(no, 'Detail').default_value = 4
    L.new(tc.outputs['Object'], no.inputs['Vector'])
    cr = _n(nt, 'ShaderNodeValToRGB', -500, 900); el = cr.color_ramp.elements
    el[0].position = 0.35; el[0].color = (*ca, 1); el[1].position = 0.65; el[1].color = (*cb, 1)
    L.new(no.outputs['Fac'], cr.inputs['Fac'])
    mx = _mix(nt, 700, 600); _in(mx, 'Factor', 'VALUE').default_value = 1.0
    L.new(src, _in(mx, 'A', 'RGBA')); L.new(cr.outputs['Color'], _in(mx, 'B', 'RGBA'))
    L.new(_out(mx, 'Result', 'RGBA'), b.inputs['Base Color'])

def intonaco_vecchio(m):
    """Intonaco vissuto, in coordinate di mondo (il web fa lo stesso in citta.js): tono a grandi macchie,
    sporco e umidita' alla base con il bordo irregolare, qualche crepa sottile."""
    nt, b, col = _base(m); L = nt.links
    pos = _n(nt, 'ShaderNodeNewGeometry', -1300, 2600).outputs['Position']
    def rumore(scala, det, x, y):
        no = _n(nt, 'ShaderNodeTexNoise', x, y)
        _in(no, 'Scale').default_value = scala; _in(no, 'Detail').default_value = det
        L.new(pos, no.inputs['Vector'])
        return no.outputs['Fac']
    def calcolo(op, a, bv, x, y):
        mt = _n(nt, 'ShaderNodeMath', x, y); mt.operation = op
        for i, v in enumerate((a, bv)):
            if isinstance(v, float): mt.inputs[i].default_value = v
            elif v is not None: L.new(v, mt.inputs[i])
        return mt.outputs[0]
    # tono: luminosita' e una punta di caldo/freddo a macchie di qualche metro
    hs = _n(nt, 'ShaderNodeHueSaturation', 300, 2600)
    L.new(_intervallo(nt, rumore(0.22, 3, -700, 2600), 0.35, 0.65, 0.82, 1.12, 0, 2600), hs.inputs['Value'])
    L.new(_intervallo(nt, rumore(0.11, 2, -700, 2800), 0.35, 0.65, 0.485, 0.515, 0, 2800), hs.inputs['Hue'])
    L.new(col, hs.inputs['Color']); col = hs.outputs['Color']
    # sporco alla base: fino a 0,8-1,5 m, piu' scuro in basso
    sx = _n(nt, 'ShaderNodeSeparateXYZ', -700, 3000); L.new(pos, sx.inputs[0])
    lim = calcolo('ADD', calcolo('MULTIPLY', rumore(1.3, 3, -700, 3200), 0.7, -500, 3200), 0.8, -300, 3200)
    sp = _intervallo(nt, calcolo('DIVIDE', sx.outputs['Z'], lim, -100, 3000), 0.25, 1.0, 0.6, 0.0, 100, 3000)
    mx = _mix(nt, 500, 2600, 'MIX'); L.new(sp, _in(mx, 'Factor', 'VALUE'))
    L.new(col, _in(mx, 'A', 'RGBA')); _in(mx, 'B', 'RGBA').default_value = (0.16, 0.135, 0.1, 1)
    col = _out(mx, 'Result', 'RGBA')
    # crepe: linee di livello di un rumore, solo dove un secondo rumore lo permette
    linea = _intervallo(nt, calcolo('ABSOLUTE', calcolo('SUBTRACT', rumore(1.4, 2, -700, 3500), 0.5, -500, 3500),
                                    None, -300, 3500), 0.0, 0.012, 1.0, 0.0, -100, 3500)
    dove = _intervallo(nt, rumore(0.3, 2, -700, 3800), 0.6, 0.68, 0.0, 0.6, -100, 3800)
    mx = _mix(nt, 700, 2600); L.new(calcolo('MULTIPLY', linea, dove, 100, 3600), _in(mx, 'Factor', 'VALUE'))
    L.new(col, _in(mx, 'A', 'RGBA')); _in(mx, 'B', 'RGBA').default_value = (0.25, 0.22, 0.19, 1)
    L.new(_out(mx, 'Result', 'RGBA'), b.inputs['Base Color'])

def sporco_base(m):
    """Muri di pietra delle case: sporco e umidita' alla base fino a 0,8-1,5 m con il bordo irregolare (come
    l'intonaco; il web fa lo stesso in citta.js)."""
    nt, b, col = _base(m); L = nt.links
    pos = _n(nt, 'ShaderNodeNewGeometry', -1300, 3000).outputs['Position']
    no = _n(nt, 'ShaderNodeTexNoise', -700, 3200)
    _in(no, 'Scale').default_value = 1.3; _in(no, 'Detail').default_value = 3
    L.new(pos, no.inputs['Vector'])
    mu = _n(nt, 'ShaderNodeMath', -500, 3200); mu.operation = 'MULTIPLY'; mu.inputs[1].default_value = 0.7
    L.new(no.outputs['Fac'], mu.inputs[0])
    ad = _n(nt, 'ShaderNodeMath', -300, 3200); ad.operation = 'ADD'; ad.inputs[1].default_value = 0.8
    L.new(mu.outputs[0], ad.inputs[0])
    sx = _n(nt, 'ShaderNodeSeparateXYZ', -700, 3000); L.new(pos, sx.inputs[0])
    dv = _n(nt, 'ShaderNodeMath', -100, 3000); dv.operation = 'DIVIDE'
    L.new(sx.outputs['Z'], dv.inputs[0]); L.new(ad.outputs[0], dv.inputs[1])
    mx = _mix(nt, 500, 3000, 'MIX')
    L.new(_intervallo(nt, dv.outputs[0], 0.25, 1.0, 0.5, 0.0, 100, 3000), _in(mx, 'Factor', 'VALUE'))
    L.new(col, _in(mx, 'A', 'RGBA')); _in(mx, 'B', 'RGBA').default_value = (0.12, 0.105, 0.08, 1)
    L.new(_out(mx, 'Result', 'RGBA'), b.inputs['Base Color'])

def desatura(m, sat):
    """Riduce la saturazione del colore di base (es. mattoni troppo rossi)."""
    nt, b, src = _base(m)
    hs = _n(nt, 'ShaderNodeHueSaturation', 700, 800); hs.inputs['Saturation'].default_value = sat
    nt.links.new(src, hs.inputs['Color']); nt.links.new(hs.outputs['Color'], b.inputs['Base Color'])

def invecchia(m, fasce=True):
    """Pietra delle mura: fasce di tono orizzontali, colature verticali di pioggia, base scura e umida
    con muschio (coordinate di mondo: vale per mura, torri e porte)."""
    nt, b, col = _base(m); L = nt.links
    ge = _n(nt, 'ShaderNodeNewGeometry', -900, 1500)
    pos = ge.outputs['Position']
    def rumore(sc, scala, det, x, y):
        mp = _n(nt, 'ShaderNodeMapping', x - 200, y); mp.inputs['Scale'].default_value = sc
        L.new(pos, mp.inputs['Vector'])
        no = _n(nt, 'ShaderNodeTexNoise', x, y)
        _in(no, 'Scale').default_value = scala; _in(no, 'Detail').default_value = det
        L.new(mp.outputs[0], no.inputs['Vector'])
        return no.outputs['Fac']
    # fasce di tono: corsi di pietra di cava diversa
    if fasce:
        hs = _n(nt, 'ShaderNodeHueSaturation', 300, 1500)
        L.new(_intervallo(nt, rumore((0.03, 0.03, 0.6), 1.0, 2, -500, 1500), 0.3, 0.7, 0.72, 1.2, 0, 1500), hs.inputs['Value'])
        L.new(_intervallo(nt, rumore((0.05, 0.05, 0.35), 1.0, 2, -500, 1700), 0.3, 0.7, 0.85, 1.1, 0, 1700), hs.inputs['Saturation'])
        L.new(col, hs.inputs['Color']); col = hs.outputs['Color']
    # colature di pioggia: rumore molto allungato in verticale
    f = _intervallo(nt, rumore((1.2, 1.2, 0.05), 2.0, 4, -500, 1900), 0.5, 0.72, 0.0, 0.8, 0, 1900)
    mx = _mix(nt, 500, 1500); L.new(f, _in(mx, 'Factor', 'VALUE'))
    L.new(col, _in(mx, 'A', 'RGBA')); _in(mx, 'B', 'RGBA').default_value = (0.3, 0.28, 0.25, 1)
    col = _out(mx, 'Result', 'RGBA')
    # base umida e muschio
    sx = _n(nt, 'ShaderNodeSeparateXYZ', -500, 2100); L.new(pos, sx.inputs[0])
    umido = _intervallo(nt, sx.outputs['Z'], 0.2, 2.4, 1.0, 0.0, 0, 2100)
    mx = _mix(nt, 700, 1500, 'MIX'); fu = _n(nt, 'ShaderNodeMath', 300, 2100); fu.operation = 'MULTIPLY'
    L.new(umido, fu.inputs[0]); fu.inputs[1].default_value = 0.6
    L.new(fu.outputs[0], _in(mx, 'Factor', 'VALUE'))
    L.new(col, _in(mx, 'A', 'RGBA')); _in(mx, 'B', 'RGBA').default_value = (0.13, 0.12, 0.1, 1)
    col = _out(mx, 'Result', 'RGBA')
    mu = _n(nt, 'ShaderNodeMath', 300, 2300); mu.operation = 'MULTIPLY'
    L.new(umido, mu.inputs[0])
    L.new(_intervallo(nt, rumore((1, 1, 1), 1.6, 6, -500, 2300), 0.42, 0.62, 0.0, 0.9, 0, 2300), mu.inputs[1])
    mx = _mix(nt, 900, 1500, 'MIX'); L.new(mu.outputs[0], _in(mx, 'Factor', 'VALUE'))
    L.new(col, _in(mx, 'A', 'RGBA')); _in(mx, 'B', 'RGBA').default_value = (0.07, 0.1, 0.025, 1)
    L.new(_out(mx, 'Result', 'RGBA'), b.inputs['Base Color'])
    # la base umida e' un po' meno ruvida
    if b.inputs['Roughness'].links:
        r = b.inputs['Roughness'].links[0].from_socket
        sub = _n(nt, 'ShaderNodeMath', 900, 0); sub.operation = 'SUBTRACT'; sub.use_clamp = True
        L.new(r, sub.inputs[0]); L.new(fu.outputs[0], sub.inputs[1])
        L.new(sub.outputs[0], b.inputs['Roughness'])

def crea_materiali():
    pbr('selciato', 'cobblestone_floor_04', tile=2.6, var=0.0, sporco=0.0, rilievo=0.5, normale=1.3)
    # terra battuta: la texture ha albedo ~0,05; la tinta la porta a ~0,2 (ronda, fuori dalle mura)
    # e a ~0,28 per il suolo erboso dentro le mura
    pbr('terra', 'stony_dirt_path', tile=3.0, tinta=(4.3, 4.0, 3.6), var=0.0, sporco=0.0, rilievo=0.4)
    con_erba(pbr('terra_erbosa', 'stony_dirt_path', tile=3.0, tinta=(5.6, 5.6, 5.0), var=0.0, sporco=0.0, rilievo=0.3))
    con_erba(pbr('terra_fossato', 'stony_dirt_path', tile=3.0, tinta=(4.0, 4.0, 3.6), var=0.0, sporco=0.0, rilievo=0.3),
             0.42)
    m = semplice('fieno', (0.8, 0.64, 0.3), 0.9, True, 0.1)      # fieno: giallo paglia chiaro, fibroso
    nt = m.node_tree; b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tc = _n(nt, 'ShaderNodeTexCoord', 300, -400); mp = _n(nt, 'ShaderNodeMapping', 450, -400)
    mp.inputs['Scale'].default_value = (1.0, 1.0, 6.0); nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    no = _n(nt, 'ShaderNodeTexNoise', 600, -400); _in(no, 'Scale').default_value = 30.0
    _in(no, 'Detail').default_value = 10; nt.links.new(mp.outputs[0], no.inputs['Vector'])
    bu = _n(nt, 'ShaderNodeBump', 800, -400); bu.inputs['Strength'].default_value = 0.7
    nt.links.new(no.outputs['Fac'], bu.inputs['Height']); nt.links.new(bu.outputs['Normal'], b.inputs['Normal'])
    macchie(pbr('prato', 'sparse_grass', tile=2.0, tinta=(0.62, 1.0, 0.4), var=0.0, sporco=0.0, rilievo=0.3),
            0.015, (0.85, 0.85, 0.6), (1.1, 1.25, 0.9))
    invecchia(pbr('pietra_mura', 'stone_wall', tile=2.2, var=0.0, sporco=0.0))
    pbr('coppi_vecchi', 'clay_roof_tiles_02', tile=2.0, tinta=(0.6, 0.48, 0.4), var=0.12, sporco=0.0)
    # pietra rosata: sassi della stessa taglia di stone_wall (~20 cm: 1,4 m per ripetizione) e meno satura
    m = pbr('pietra_blocchi', 'medieval_blocks_02', tile=1.4, tinta=(1.0, 0.95, 0.85))
    desatura(m, 0.62); sporco_base(m)
    sporco_base(pbr('pietra_muro', 'stone_wall', tile=2.2))
    pbr('pietra_cornici', 'white_plaster_rough_01', tile=3.0, tinta=(0.78, 0.74, 0.66), var=0.05, normale=0.7)
    m = pbr('mattoni', 'castle_brick_07', tile=1.8, tinta=(0.92, 0.8, 0.7), sporco=0.5)   # bruni, sporchi
    desatura(m, 0.5); invecchia(m, fasce=False)
    invecchia(pbr('pietra_chiesa', 'large_sandstone_blocks', tile=4.0, tinta=(1.45, 1.35, 1.12), var=0.0,
                  sporco=0.0, rilievo=0.4, normale=1.2), fasce=False)
    intonaco_vecchio(pbr('intonaco_bianco', 'white_plaster_rough_01', tile=2.0, tinta=(0.95, 0.9, 0.8)))
    # giallo e rosa: intonaco liscio tinto (yellow_plaster_02 ha due travi dipinte ogni 2,5 m: ora sono vere)
    intonaco_vecchio(pbr('intonaco_giallo', 'white_plaster_rough_01', tile=2.0, tinta=(0.95, 0.74, 0.45)))
    intonaco_vecchio(pbr('intonaco_rosa', 'white_plaster_rough_01', tile=2.0, tinta=(0.95, 0.66, 0.54)))
    pbr('legno_travi', 'medieval_wood', tile=1.2, tinta=(0.42, 0.33, 0.27), var=0.12)
    pbr('legno_grezzo', 'rough_wood', tile=1.0, var=0.12)
    # insegna della locanda: stesso legno delle travi ma piallato e schiarito dal sole, pirografia scura e opaca;
    # ferro battuto dell'insegna (braccio, catene, bandelle): grigio scuro con la ruggine appena accennata (la texture
    # rusty_metal desaturata; il 'ferro' del borgo, piu' rugginoso, non cambia). Materiali propri: nel web oscilla
    pbr('insegna_legno', 'medieval_wood', tile=1.2, tinta=(0.95, 0.8, 0.62), var=0.04, sporco=0.0)
    m = pbr('insegna_ferro', 'rusty_metal', tile=1.0, tinta=(0.24, 0.24, 0.25), metallo=0.75, sporco=0.0, var=0.03)
    next(n for n in m.node_tree.nodes if n.type == 'HUE_SAT').inputs['Saturation'].default_value = INSEGNA_RUGGINE
    m = semplice('insegna_bruciato', (0.03, 0.018, 0.011), 1.0, False, 0.04)   # legno carbonizzato: opaco
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    try:
        b.inputs['Specular IOR Level'].default_value = 0.15
    except KeyError:
        pass
    pbr('assi', 'weathered_planks', tile=1.5, var=0.1)
    pbr('imposte_verdi', 'weathered_planks', tile=1.0, tinta=(0.35, 0.55, 0.38))
    pbr('imposte_rosse', 'weathered_planks', tile=1.0, tinta=(0.78, 0.3, 0.22))
    pbr('imposte_blu', 'weathered_planks', tile=1.0, tinta=(0.32, 0.45, 0.65))
    pbr('coppi', 'clay_roof_tiles_02', tile=2.0, var=0.1, sporco=0.0)
    pbr('ardesia', 'roof_slates_02', tile=2.0, tinta=(0.5, 0.53, 0.58), var=0.1, sporco=0.0)
    pbr('paglia', 'thatch_roof_angled', tile=2.5, tinta=(1.0, 0.82, 0.55), var=0.12, sporco=0.0)
    pbr('tavole', 'weathered_planks', tile=1.5, tinta=(0.8, 0.6, 0.42), var=0.15)   # case di legno del borgo
    pbr('ferro', 'rusty_metal', tile=1.0, tinta=(0.3, 0.28, 0.27), metallo=0.6, sporco=0.0)
    pbr('vimini', 'thatch_roof_angled', tile=0.4, tinta=(0.95, 0.78, 0.5), sporco=0.0)
    pbr('juta', 'fabric_pattern_05', tile=0.15, colore=(0.3, 0.21, 0.12), sporco=0.0, var=0.12, normale=1.6)
    pbr('terracotta', None, colore=(0.5, 0.2, 0.1), sporco=0.0)
    semplice('interno_buio', (0.012, 0.01, 0.008), 0.9, False, 0.0)
    m = semplice('foglie', (0.04, 0.1, 0.022), 0.7, True, 0.3)   # chiome: rilievo a ciuffi
    nt = m.node_tree; b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tc = _n(nt, 'ShaderNodeTexCoord', 300, -400); vo = _n(nt, 'ShaderNodeTexVoronoi', 500, -400)
    _in(vo, 'Scale').default_value = 9.0
    nt.links.new(tc.outputs['Object'], vo.inputs['Vector'])
    bu = _n(nt, 'ShaderNodeBump', 800, -400); bu.inputs['Strength'].default_value = 0.9
    bu.inputs['Distance'].default_value = 0.08
    nt.links.new(vo.outputs['Distance'], bu.inputs['Height']); nt.links.new(bu.outputs['Normal'], b.inputs['Normal'])
    semplice('fiori_rossi', (0.6, 0.02, 0.03), 0.5)
    semplice('fiori_viola', (0.28, 0.06, 0.42), 0.5)
    semplice('fiori_gialli', (0.85, 0.55, 0.04), 0.5)
    semplice('mela', (0.42, 0.02, 0.02), 0.35)
    semplice('arancia', (0.8, 0.28, 0.02), 0.5)
    semplice('limone', (0.8, 0.65, 0.05), 0.45)
    semplice('cavolo', (0.16, 0.32, 0.07), 0.6)
    semplice('pane', (0.42, 0.22, 0.08), 0.8)
    semplice('formaggio', (0.8, 0.58, 0.2), 0.6)
    semplice('zucca', (0.7, 0.28, 0.03), 0.55)
    semplice('uva', (0.12, 0.02, 0.1), 0.3)
    semplice('bronzo', (0.4, 0.24, 0.1), 0.35, False, 0.0, metallo=1.0)
    vetro(); acqua(); acqua_getto()
    m, nt, b, out = nuovo_mat('brace')   # brace della forgia e del forno: luce propria
    b.inputs['Base Color'].default_value = (0.9, 0.25, 0.03, 1)
    try:
        b.inputs['Emission Color'].default_value = (1.0, 0.32, 0.05, 1); b.inputs['Emission Strength'].default_value = 30.0
    except KeyError:
        pass
    semplice('cuoio', (0.3, 0.17, 0.08), 0.6, True, 0.2)
    semplice('calce', (0.72, 0.7, 0.62), 0.12, False, 0.03)        # vasche della conceria
    semplice('conciante', (0.16, 0.09, 0.04), 0.06, False, 0.05)
    semplice('tintura_rossa', (0.32, 0.05, 0.03), 0.06, False, 0.05)
    semplice('tintura_ocra', (0.5, 0.3, 0.06), 0.06, False, 0.05)
    tessuto('tenda_bottega', (0.45, 0.04, 0.03), (0.75, 0.68, 0.52))
    tessuto('stendardo', (0.45, 0.03, 0.03), (0.65, 0.42, 0.06), righe=0.25)
    tessuto('festone_rosso', (0.5, 0.03, 0.03)); tessuto('festone_ocra', (0.7, 0.45, 0.06))
    tessuto('festone_blu', (0.05, 0.12, 0.35)); tessuto('festone_crema', (0.8, 0.74, 0.6))
    # stemmi: tempera consumata sull'intonaco (la grana e lo sporco della texture), colori poco saturi
    for nome, c in (('stemma_azzurro', (0.24, 0.33, 0.45)), ('stemma_rosso', (0.52, 0.2, 0.15)),
                    ('stemma_oro', (0.68, 0.53, 0.27)), ('stemma_verde', (0.25, 0.35, 0.24)),
                    ('stemma_argento', (0.8, 0.78, 0.72)), ('stemma_nero', (0.13, 0.12, 0.11))):
        pbr(nome, 'white_plaster_rough_01', tile=0.8, tinta=c, sporco=0.5)

TELI = [((0.45, 0.04, 0.03), (0.75, 0.68, 0.52)), ((0.08, 0.22, 0.08), (0.75, 0.68, 0.52)),
        ((0.05, 0.1, 0.3), (0.6, 0.4, 0.08)), ((0.6, 0.38, 0.08), (0.75, 0.68, 0.52)),
        ((0.25, 0.03, 0.05), (0.75, 0.68, 0.52)), ((0.75, 0.68, 0.52), None)]

# ----------------------------------------------------------------------
#  GEOMETRIA DI BASE (bmesh)
# ----------------------------------------------------------------------
DET_ID = {}   # id(bmesh) -> numero progressivo: chiave delle facciate per il controllo delle aperture
def nuovo_bm():
    bm = bmesh.new(); bm.loops.layers.uv.verify(); DET_ID[id(bm)] = len(DET_ID); return bm

CM = [None]   # matrice di lavoro corrente (per costruire le facciate laterali)

def _tr(p, M):
    v = Vector(p)
    if M is None:
        M = CM[0]
    return v if M is None else M @ v

def _P(ax, u, a, v):
    if ax == 'y': return (u, a, v)
    if ax == 'x': return (a, u, v)
    return (u, v, a)

def prism(bm, pts, a0, a1, mi, ax='y', M=None):
    f0 = [bm.verts.new(_tr(_P(ax, u, a0, v), M)) for u, v in pts]
    f1 = [bm.verts.new(_tr(_P(ax, u, a1, v), M)) for u, v in pts]
    fs = [bm.faces.new(f0), bm.faces.new(f1[::-1])]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        fs.append(bm.faces.new((f0[i], f0[j], f1[j], f1[i])))
    for f in fs:
        f.material_index = mi
    return fs

def box(bm, a, b, mi, M=None):
    x0, x1 = sorted((a[0], b[0])); y0, y1 = sorted((a[1], b[1])); z0, z1 = sorted((a[2], b[2]))
    return prism(bm, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], y0, y1, mi, 'y', M)

def rett(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]

def arco_pts(x0, x1, z0, z1, seg=12):
    r = (x1 - x0) / 2; xc = (x0 + x1) / 2; zs = z1 - r
    pts = [(x0, z0), (x1, z0), (x1, zs)]
    for i in range(1, seg):
        a = math.pi * i / seg
        pts.append((xc + r * math.cos(a), zs + r * math.sin(a)))
    pts.append((x0, zs))
    return pts

def lathe(bm, prof, seg=16, mi=0, M=None, cap0=True, cap1=True, chiuso=False, liscio=True, fase=0.0):
    anelli = []
    for (r, z) in prof:
        anelli.append([bm.verts.new(_tr((r * math.cos(fase + 2 * math.pi * i / seg),
                                          r * math.sin(fase + 2 * math.pi * i / seg), z), M))
                       for i in range(seg)])
    fs = []
    nr = len(anelli)
    coppie = [(k, k + 1) for k in range(nr - 1)]
    if chiuso:
        coppie.append((nr - 1, 0))
    for a, b in coppie:
        A, B = anelli[a], anelli[b]
        for i in range(seg):
            j = (i + 1) % seg
            fs.append(bm.faces.new((A[i], A[j], B[j], B[i])))
    if not chiuso:
        if cap0: fs.append(bm.faces.new(anelli[0][::-1]))
        if cap1: fs.append(bm.faces.new(anelli[-1]))
    for f in fs:
        f.material_index = mi; f.smooth = liscio
    return fs

def sfera(bm, c, r, mi, M=None, sc=(1, 1, 1), sub=2, rotz=0.0):
    Mm = Matrix.Translation(Vector(c)) @ RZ(rotz) @ Matrix.Diagonal((sc[0], sc[1], sc[2], 1.0))
    if M is None:
        M = CM[0]
    if M is not None:
        Mm = M @ Mm
    res = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r, matrix=Mm, calc_uvs=False)
    fs = set()
    for v in res['verts']:
        fs.update(v.link_faces)
    for f in fs:
        f.material_index = mi; f.smooth = True

def oggetto(nome, bm, mats, coll, ricalcola=True):
    if ricalcola:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me); bm.free()
    for n in mats:
        me.materials.append(MAT[n])
    ob = bpy.data.objects.new(nome, me)
    coll.objects.link(ob)
    return ob

def fora(ob, tagli, coll):
    """Sottrae le aperture (finestre, porte, archi) con un booleano esatto."""
    if not tagli:
        return ob
    bmc = nuovo_bm()
    for t in tagli:
        pts, a0, a1, ax, mi = t[:5]
        prism(bmc, pts, a0, a1, mi, ax, t[5] if len(t) > 5 else None)
    bmesh.ops.recalc_face_normals(bmc, faces=bmc.faces[:])
    mc = bpy.data.meshes.new("_taglio"); bmc.to_mesh(mc); bmc.free()
    ct = bpy.data.objects.new("_taglio", mc); coll.objects.link(ct)
    ct.hide_render = True
    mod = ob.modifiers.new("fori", 'BOOLEAN')
    mod.operation = 'DIFFERENCE'; mod.object = ct
    mod.solver = 'EXACT'
    if len(set(t[3] for t in tagli)) > 1:
        mod.use_self = True
    try:
        mod.material_mode = 'INDEX'
    except Exception:
        pass
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    vecchia = ob.data
    ob.modifiers.clear()
    ob.data = me
    if len(me.materials) == 0:
        for m in vecchia.materials:
            me.materials.append(m)
    bpy.data.meshes.remove(vecchia)
    bpy.data.objects.remove(ct, do_unlink=True); bpy.data.meshes.remove(mc)
    return ob

def unisci(objs, nome):
    objs = [o for o in objs if o is not None]
    if len(objs) > 1:
        with bpy.context.temp_override(active_object=objs[0], object=objs[0],
                                       selected_objects=objs, selected_editable_objects=objs):
            bpy.ops.object.join()
    ob = objs[0]; ob.name = nome; ob.data.name = nome
    return ob

TETTI = {'coppi', 'ardesia', 'paglia', 'coppi_vecchi'}

def uv_finale(ob):
    """UV in metri: proiezione a scatola, e lungo la falda per i tetti."""
    me = ob.data
    bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
    uv = bm.loops.layers.uv.verify()
    nomi = [(s.material.name if s.material else '') for s in ob.material_slots]
    for f in bm.faces:
        n = f.normal
        nm = nomi[f.material_index] if f.material_index < len(nomi) else ''
        if nm in TETTI and 0.05 < abs(n.z) < 0.985:
            hl = math.hypot(n.x, n.y)
            h = Vector((n.x / hl, n.y / hl, 0))
            ridge = Vector((-h.y, h.x, 0))
            t = Vector((-n.z * h.x, -n.z * h.y, hl))
            for l in f.loops:
                co = l.vert.co; l[uv].uv = (co.dot(ridge), co.dot(t))
        else:
            ax = max(range(3), key=lambda i: abs(n[i]))
            for l in f.loops:
                co = l.vert.co
                if ax == 0: l[uv].uv = (co.y, co.z)
                elif ax == 1: l[uv].uv = (co.x, co.z)
                else: l[uv].uv = (co.x, co.y)
    bm.to_mesh(me); bm.free()

def smussa(ob, w=0.015):
    if not SMUSSO:
        return
    m = ob.modifiers.new("smusso", 'BEVEL')
    m.width = w; m.segments = 2; m.limit_method = 'ANGLE'; m.angle_limit = math.radians(35)
    m.use_clamp_overlap = True

# ----------------------------------------------------------------------
#  OCCUPAZIONE DEL SUOLO (strade, lotti riservati, case gia' costruite, mura)
# ----------------------------------------------------------------------
OSTACOLI = []   # (xmin, ymin, xmax, ymax, poligono convesso) delle aree gia' occupate
GRIGLIA = {}    # indice spaziale: cella di CELLA metri -> indici in OSTACOLI
CELLA = 8.0

def _celle(x0, y0, x1, y1):
    for i in range(math.floor(x0 / CELLA), math.floor(x1 / CELLA) + 1):
        for j in range(math.floor(y0 / CELLA), math.floor(y1 / CELLA) + 1):
            yield (i, j)

def occupa(pol):
    xs = [p[0] for p in pol]; ys = [p[1] for p in pol]
    OSTACOLI.append((min(xs), min(ys), max(xs), max(ys), pol))
    for c in _celle(min(xs), min(ys), max(xs), max(ys)):
        GRIGLIA.setdefault(c, []).append(len(OSTACOLI) - 1)

def _vicini(x0, y0, x1, y1):
    visti = set()
    for c in _celle(x0, y0, x1, y1):
        for k in GRIGLIA.get(c, ()):
            if k not in visti:
                visti.add(k); yield OSTACOLI[k]

def occupato(p):
    x, y = p
    for (a0, b0, a1, b1, o) in _vicini(x, y, x, y):
        if a0 <= x <= a1 and b0 <= y <= b1:
            n = len(o)
            cr = [(o[(i + 1) % n][0] - o[i][0]) * (y - o[i][1]) - (o[(i + 1) % n][1] - o[i][1]) * (x - o[i][0])
                  for i in range(n)]
            if all(c >= 0 for c in cr) or all(c <= 0 for c in cr):
                return True
    return False

def rett_mondo(M, x0, y0, x1, y1):
    """Rettangolo in coordinate locali (x0..x1, y0..y1) portato in pianta con la matrice M."""
    return [tuple((M @ Vector((x, y, 0.0))).xy) for (x, y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]

def _separati(a, b):
    """Teorema dell'asse separatore per due poligoni convessi."""
    for pol in (a, b):
        n = len(pol)
        for i in range(n):
            (px, py), (qx, qy) = pol[i], pol[(i + 1) % n]
            ax, ay = qy - py, px - qx
            pa = [ax * x + ay * y for x, y in a]; pb = [ax * x + ay * y for x, y in b]
            if max(pa) <= min(pb) or max(pb) <= min(pa):
                return True
    return False

def dentro_poligono(p, pts):
    x, y = p; dentro = False; n = len(pts)
    for k in range(n):
        (x0, y0), (x1, y1) = pts[k], pts[(k + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            dentro = not dentro
    return dentro

def dentro_mura(p, margine):
    x, y = p; dentro = False; n = len(MURA)
    for k in range(n):
        (x0, y0), (x1, y1) = MURA[k], MURA[(k + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            dentro = not dentro
        dx, dy = x1 - x0, y1 - y0
        t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / (dx * dx + dy * dy)))
        if math.hypot(x - x0 - t * dx, y - y0 - t * dy) < margine:
            return False
    return dentro

def libero(pol):
    xs = [p[0] for p in pol]; ys = [p[1] for p in pol]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    for (a0, b0, a1, b1, o) in _vicini(x0, y0, x1, y1):
        if a0 < x1 and x0 < a1 and b0 < y1 and y0 < b1 and not _separati(pol, o):
            return False
    return all(dentro_mura(p, MARGINE_MURA) for p in pol)

def scosta(punti, d):
    """Polilinea parallela a distanza d sulla sinistra del verso di percorrenza (giunti a spigolo)."""
    P = [Vector((p[0], p[1])) for p in punti]
    perp = lambda v: Vector((-v.y, v.x)).normalized()
    out = []
    for k in range(len(P)):
        if k == 0:
            n = perp(P[1] - P[0])
        elif k == len(P) - 1:
            n = perp(P[-1] - P[-2])
        else:
            n1 = perp(P[k] - P[k - 1]); m = (n1 + perp(P[k + 1] - P[k])).normalized()
            n = m / max(0.5, m.dot(n1))
        out.append(tuple(P[k] + n * d))
    return out

def occupa_strada(punti, larg):
    """Il corridoio della strada (allungato di mezza larghezza ai capi per coprire i giunti)."""
    hw = larg / 2
    for a, b in zip(punti, punti[1:]):
        a = Vector(a); b = Vector(b); e = (b - a).normalized(); n = Vector((-e.y, e.x))
        p0, p1 = a - e * hw, b + e * hw
        occupa([tuple(p0 - n * hw), tuple(p1 - n * hw), tuple(p1 + n * hw), tuple(p0 + n * hw)])

def lotto_libero(M, W, D):
    """Il lotto W x D (coordinate locali della casa) non tocca strade, lotti riservati, case o mura."""
    return libero(rett_mondo(M, 0.15, 0.15, W - 0.15, D + 0.3))

def corsa(M, lim, D):
    """Larghezza massima (fino a lim) di un lotto libero profondo D che parte da M."""
    if lim < 4.2 or not lotto_libero(M, 4.2, D):
        return 0.0
    if lotto_libero(M, lim, D):
        return lim
    a, b = 4.2, lim
    while b - a > 0.1:
        c = (a + b) / 2
        if lotto_libero(M, c, D): a = c
        else: b = c
    return a

# ----------------------------------------------------------------------
#  EDIFICI
# ----------------------------------------------------------------------
MB = ['pietra_blocchi', 'pietra_muro', 'intonaco_bianco', 'intonaco_giallo', 'intonaco_rosa',
      'legno_travi', 'coppi', 'ardesia', 'paglia', 'vetro', 'assi', 'ferro', 'pietra_cornici',
      'imposte_verdi', 'imposte_rosse', 'imposte_blu', 'mattoni', 'foglie', 'fiori_rossi',
      'fiori_viola', 'fiori_gialli', 'interno_buio', 'tenda_bottega', 'stendardo', 'bronzo',
      'juta', 'legno_grezzo', 'pietra_mura', 'coppi_vecchi', 'festone_rosso', 'festone_crema', 'festone_blu',
      'cavolo', 'zucca', 'terra', 'prato', 'tavole', 'pietra_chiesa', 'vimini', 'pane', 'acqua', 'terracotta',
      'brace', 'cuoio', 'calce', 'conciante', 'tintura_rossa', 'tintura_ocra', 'fieno',
      'stemma_azzurro', 'stemma_rosso', 'stemma_oro', 'stemma_verde', 'stemma_argento', 'stemma_nero']
I = {n: i for i, n in enumerate(MB)}
H0, HF = 3.3, 2.8
FACCIATE = []   # (matrice, larghezza, stile, bottega) per piazzare oggetti davanti alle case
APERTURE = []   # finestre e porte marcate per il controllo finale: (tipo, verso esterno, tassello, facciata)
INFO_AP = {}    # numero apertura -> (oggetto, centro, verso esterno, z del centro, mezza altezza, mezza larghezza)

def segna_apertura(det, n0, tipo, fuori, tassello=None):
    """Le facce create da n0 in poi formano una finestra (o porta): le marca col suo numero per
    controlla_aperture(). 'fuori' = verso esterno nel sistema del lotto (matrice CM[0]); 'tassello' = foro
    scavato col booleano (punti, y del muro, y del fondo, asse, materiale del muro, matrice) da richiudere."""
    lay = det.faces.layers.int.get('apertura') or det.faces.layers.int.new('apertura')
    det.faces.ensure_lookup_table()
    Mc = CM[0] if CM[0] is not None else Matrix.Identity(4)
    fl = (Mc.to_3x3() @ Vector(fuori)).normalized()
    # facciata = stesso bmesh, stessa matrice di lavoro, stesso verso (tutte le finestre di un lato di una casa)
    chiave = (DET_ID.get(id(det)), tuple(round(v, 2) for r in Mc for v in r), tuple(round(c, 2) for c in fl))
    APERTURE.append((tipo, fl, tassello, chiave))
    for i in range(n0, len(det.faces)):
        det.faces[i][lay] = len(APERTURE)

def guscio(nome, costruisci, tagli, coll):
    bm = nuovo_bm(); costruisci(bm)
    ob = oggetto(nome, bm, MB, coll)
    return fora(ob, tagli, coll)

def fioriera(det, x0, x1, zA, Y):
    """Cassetta di fiori appoggiata al muro sotto il davanzale, su due mensole di ferro (prima stava 8 cm
    staccata dal muro, sospesa: dal basso, senza i fiori in vista, sembrava una trave che fluttuava)."""
    box(det, (x0 - 0.04, Y(-0.3), zA - 0.24), (x1 + 0.04, Y(0.0), zA - 0.03), I['assi'])
    for x in (x0 + 0.08, x1 - 0.08):   # mensole: braccio sotto la cassetta e saetta contro il muro
        box(det, (x - 0.015, Y(-0.28), zA - 0.27), (x + 0.015, Y(0.0), zA - 0.24), I['ferro'])
        prism(det, [(Y(0.0), zA - 0.27), (Y(0.0), zA - 0.5), (Y(-0.24), zA - 0.27)],
              x - 0.012, x + 0.012, I['ferro'], 'x')
    fiore = I[rc(['fiori_rossi', 'fiori_viola', 'fiori_gialli', 'fiori_rossi'])]
    cols = [I['foglie']] * 3 + [fiore] * 2
    for _ in range(int((x1 - x0) / 0.06) + 8):
        sfera(det, (rr(x0, x1), Y(rr(-0.28, -0.06)), zA - 0.02 + rr(0, 0.13)), rr(0.045, 0.075), rc(cols), sub=1)
    for _ in range(6):
        sfera(det, (rr(x0, x1), Y(-0.32), zA - 0.12 - rr(0, 0.3)), rr(0.04, 0.06), I['foglie'], sub=1)

def tenda(det, x0, x1, z, Y):
    v = [det.verts.new(p) for p in [(x0, Y(-0.02), z + 0.35), (x1, Y(-0.02), z + 0.35),
                                     (x1, Y(-1.1), z - 0.1), (x0, Y(-1.1), z - 0.1)]]
    f = det.faces.new(v); f.material_index = I['tenda_bottega']
    n = 14; top = []; bot = []
    for i in range(n + 1):
        u = i / n; x = x0 + (x1 - x0) * u
        top.append(det.verts.new((x, Y(-1.1), z - 0.1)))
        bot.append(det.verts.new((x, Y(-1.1), z - 0.3 - 0.06 * abs(math.sin(math.pi * u * 5)))))
    for i in range(n):
        f = det.faces.new((top[i], top[i + 1], bot[i + 1], bot[i])); f.material_index = I['tenda_bottega']
    for x in (x0 + 0.05, x1 - 0.05):
        box(det, (x - 0.015, Y(-0.02), z + 0.08), (x + 0.015, Y(-1.08), z + 0.11), I['ferro'])

def arco_rilievo(det, xc, zs, r0, r1, y0, y1, mi, n=10, M=None):
    """Ghiera ad arco in rilievo (centro xc, imposta zs) tra le profondita' y0 e y1."""
    for i in range(n):
        a0, a1 = math.pi * i / n, math.pi * (i + 1) / n
        prism(det, [(xc + r0 * math.cos(a0), zs + r0 * math.sin(a0)), (xc + r1 * math.cos(a0), zs + r1 * math.sin(a0)),
                    (xc + r1 * math.cos(a1), zs + r1 * math.sin(a1)), (xc + r0 * math.cos(a1), zs + r0 * math.sin(a1))],
              y0, y1, mi, 'y', M)

def bifora(det, tagli, xc, w, zA, zB, Y, mcut):
    """Bifora: due archetti con colonnina e capitello, ghiera esterna, stipiti e davanzale in rilievo."""
    pc = I['pietra_cornici']; x0, x1 = xc - w / 2, xc + w / 2
    r = (w / 2 - 0.15) / 2; zs = zB - r
    for (a, b) in ((x0 + 0.08, xc - 0.07), (xc + 0.07, x1 - 0.08)):
        tagli.append((arco_pts(a, b, zA, zB), Y(-0.4), Y(0.36), 'y', mcut, CM[0]))
        prism(det, arco_pts(a, b, zA, zB), Y(0.2), Y(0.22), I['vetro'])
    Mb = (CM[0] if CM[0] is not None else Matrix.Identity(4)) @ T(xc, Y(0.04), 0)
    lathe(det, [(0.075, zA), (0.055, zA + 0.1), (0.05, zs - 0.13), (0.11, zs - 0.04), (0.11, zs)], 10, pc, Mb)
    R = w / 2; zso = zB + 0.12 - R
    arco_rilievo(det, xc, zso, R, R + 0.14, Y(-0.08), Y(0.0), pc)
    box(det, (x0 - 0.14, Y(-0.08), zA), (x0, Y(0.0), zso), pc)
    box(det, (x1, Y(-0.08), zA), (x1 + 0.14, Y(0.0), zso), pc)
    box(det, (x0 - 0.2, Y(-0.14), zA - 0.14), (x1 + 0.2, Y(0.05), zA), pc)

# stemmi delle famiglie nobili: (disegno, campo, pezza) - uno diverso per palazzo, in ordine casuale (RNG_D)
ARMI = [('fascia', 'stemma_azzurro', 'stemma_argento'), ('partito', 'stemma_rosso', 'stemma_oro'),
        ('capriolo', 'stemma_verde', 'stemma_oro'), ('croce', 'stemma_rosso', 'stemma_argento'),
        ('palato', 'stemma_oro', 'stemma_nero'), ('capriolo', 'stemma_azzurro', 'stemma_argento'),
        ('fascia', 'stemma_nero', 'stemma_oro'), ('croce', 'stemma_verde', 'stemma_argento')]
ARME = [ARMI[0]]   # stemma del palazzo in costruzione
PALAZZI = []       # palazzetti gia' costruiti (per dare a ognuno il suo stemma)

def stemma_nobile(det, xc, zA, zB, Y, arme=None):
    """Stemma di famiglia: scudo dipinto a tempera (consumata) dentro una cornice di pietra a rilievo, pezza
    in leggero rilievo (2 cm), mensola sopra. Disegni: fascia, partito, capriolo, croce, palato."""
    disegno, campo, pezza = arme or ARME[0]
    pc = I['pietra_cornici']; zc = (zA + zB) / 2
    scudo = [(-0.42, zB), (0.42, zB), (0.42, zA + 0.45), (0.0, zA), (-0.42, zA + 0.45)]
    prism(det, [(xc + x * 1.25, zc + (z - zc) * 1.2) for x, z in scudo], Y(-0.1), Y(0.0), pc)   # cornice
    prism(det, [(xc + x, z) for x, z in scudo], Y(-0.13), Y(-0.1), I[campo])
    S = lambda pts: prism(det, [(xc + x, z) for x, z in pts], Y(-0.15), Y(-0.12), I[pezza])
    if disegno == 'fascia':
        S([(-0.42, zc - 0.05), (0.42, zc - 0.05), (0.42, zc + 0.15), (-0.42, zc + 0.15)])
    elif disegno == 'partito':
        S([(0.0, zB), (0.42, zB), (0.42, zA + 0.45), (0.0, zA)])
    elif disegno == 'capriolo':
        a = zc + 0.25
        S([(-0.36, a - 0.5), (0.0, a), (0.36, a - 0.5), (0.36, a - 0.3), (0.0, a + 0.2), (-0.36, a - 0.3)])
    elif disegno == 'croce':
        S([(-0.08, zA + 0.2), (0.08, zA + 0.2), (0.08, zB - 0.06), (-0.08, zB - 0.06)])
        for sg in (-1, 1):
            S([(sg * 0.08, zc + 0.02), (sg * 0.38, zc + 0.02), (sg * 0.38, zc + 0.18), (sg * 0.08, zc + 0.18)])
    elif disegno == 'palato':
        for x, zb0 in ((-0.26, zA + 0.42), (0.0, zA + 0.15), (0.26, zA + 0.42)):
            S([(x - 0.07, zb0), (x + 0.07, zb0), (x + 0.07, zB - 0.06), (x - 0.07, zB - 0.06)])
    box(det, (xc - 0.62, Y(-0.18), zB + 0.12), (xc + 0.62, Y(0.0), zB + 0.26), pc)

# piano del balcone e cima della porta-finestra sopra il pavimento del piano nobile: (normale, sotto il cornicione)
Z_BALCONE = {False: (0.45, 2.4), True: (0.15, 1.85)}
BALCONI = []       # centro di ogni balcone nel mondo (per le anteprime)

def portafinestra(det, tagli, xc, w, zA, zB, yface, verso, mcut):
    """Porta-finestra dietro il balcone: arco a tutto sesto dal pavimento del balcone (soglia di pietra, niente
    davanzale), due ante di legno con zoccolo pieno e vetri sopra, ghiera e stipiti in rilievo come le bifore."""
    Y = lambda d: yface - verso * d
    pc, lg = I['pietra_cornici'], I['legno_travi']
    x0, x1 = xc - w / 2, xc + w / 2; zs = zB - w / 2; zz = zA + 0.8   # imposta dell'arco, cima dello zoccolo
    tagli.append((arco_pts(x0, x1, zA, zB), Y(-0.4), Y(0.36), 'y', mcut, CM[0]))
    prism(det, arco_pts(x0, x1, zz, zB), Y(0.2), Y(0.22), I['vetro'])
    prism(det, rett(x0, x1, zA, zz), Y(0.18), Y(0.22), I['tavole'])
    for (a, b) in ((x0, x0 + 0.07), (xc - 0.035, xc + 0.035), (x1 - 0.07, x1)):   # montanti delle ante
        box(det, (a, Y(0.12), zA), (b, Y(0.2), zs if b < xc - 0.03 or a > xc else zB), lg)
    for z in (zz, zs):   # traversi
        box(det, (x0, Y(0.12), z - 0.035), (x1, Y(0.2), z + 0.035), lg)
    arco_rilievo(det, xc, zs, w / 2 - 0.07, w / 2, Y(0.12), Y(0.2), lg)
    box(det, (x0, Y(-0.02), zA), (x1, Y(0.22), zA + 0.03), pc)   # soglia
    arco_rilievo(det, xc, zs, w / 2, w / 2 + 0.14, Y(-0.08), Y(0.0), pc)
    box(det, (x0 - 0.14, Y(-0.08), zA), (x0, Y(0.0), zs), pc)
    box(det, (x1, Y(-0.08), zA), (x1 + 0.14, Y(0.0), zs), pc)

def balcone(det, xc, w, zp, yface, verso):
    """Balcone di legno del piano nobile, davanti alla porta-finestra: piano di tavole su tre mensole di pietra
    sagomate a gradoni, ringhiera di legno."""
    Y = lambda d: yface - verso * d
    lg, ass, pc = I['legno_travi'], I['assi'], I['pietra_cornici']
    x0, x1 = xc - w / 2 - 0.45, xc + w / 2 + 0.45; p = 0.9
    box(det, (x0, Y(-p), zp - 0.1), (x1, Y(0.0), zp), ass)
    for x in (x0 + 0.25, xc, x1 - 0.25):
        for (dp, za_, zb_) in ((p - 0.04, zp - 0.26, zp - 0.1), (p * 0.66, zp - 0.44, zp - 0.26),
                               (p * 0.36, zp - 0.62, zp - 0.44)):
            box(det, (x - 0.11, Y(-dp), za_), (x + 0.11, Y(0.0), zb_), pc)
    x = x0 + 0.05
    while x < x1 - 0.02:
        box(det, (x, Y(-p + 0.04), zp), (x + 0.05, Y(-p + 0.09), zp + 0.9), lg); x += 0.24
    for yy in (-p + 0.3, -p + 0.55, -p + 0.8):
        for xx in (x0 + 0.02, x1 - 0.07):
            box(det, (xx, Y(yy), zp), (xx + 0.05, Y(yy - 0.05), zp + 0.9), lg)
    box(det, (x0 - 0.03, Y(-p), zp + 0.9), (x1 + 0.03, Y(-p + 0.1), zp + 0.98), lg)
    for xx in (x0 - 0.03, x1 - 0.07):
        box(det, (xx, Y(-p), zp + 0.9), (xx + 0.1, Y(0.0), zp + 0.98), lg)

def aperture(k, W, nw, porta_i, bottega, stile, pal=False):
    xs = [W * (i + 0.5) / nw for i in range(nw)]
    slot = W / nw; res = []
    for i, x in enumerate(xs):
        if pal:   # palazzetto nobile (pal = varianti del palazzo): portale, stemma, bifore ai piani
            if k == 0:
                res.append(('porta', x, 1.8, 0.0, 3.0) if i == porta_i else ('finestra', x, 0.75, 1.3, 2.3))
            elif (k, i) == pal['stemma']:
                res.append(('stemma', x, 1.1, 0.35, 1.7))
            elif k == pal['ultimo']:   # sotto il cornicione (da z0 + 2,0): bifore piu' basse
                res.append(('bifora', x, 1.15, 0.6, 1.8))
            else:
                res.append(('bifora', x, pal['wbif'], 0.85, 2.4))
            continue
        if k == 0:
            if i == porta_i:
                res.append(('porta', x, 1.2, 0.0, 2.7 if stile == 'pietra' else 2.45))
            elif bottega:
                res.append(('bottega', x, min(2.4, slot - 0.7), 0.0, 2.75))
            else:
                res.append(('finestra', x, 0.95, 1.05, 2.25))
        else:
            if stile == 'pietra':
                res.append(('finestra', x, 0.9, 0.9, 2.3))
            else:
                res.append(('finestra', x, 0.82, 0.85, 2.1))
    return res

def apertura(det, tagli, a, z0, yface, verso, k, stile, imp, mcut):
    tipo, xc, w, za, zb = a
    x0, x1 = xc - w / 2, xc + w / 2
    zA, zB = z0 + za, z0 + zb
    Y = lambda d: yface - verso * d
    pc = I['pietra_cornici']; lg = I['legno_travi']
    if tipo == 'stemma':
        stemma_nobile(det, xc, zA, zB, Y, ARME[0]); return
    if tipo == 'bifora':
        bifora(det, tagli, xc, w, zA, zB, Y, mcut); return
    arco = stile == 'pietra' or tipo == 'bottega' or (tipo == 'porta' and stile == 'pietra')
    zbase = zA if zA > 0.01 else -0.2
    pts_t = arco_pts(x0, x1, zbase, zB) if arco else rett(x0, x1, zbase, zB)
    pts = arco_pts(x0, x1, zA, zB) if arco else rett(x0, x1, zA, zB)
    prof = {'finestra': 0.36, 'porta': 0.32, 'bottega': 1.3}[tipo]
    tagli.append((pts_t, Y(-0.4), Y(prof), 'y', mcut, CM[0]))
    if tipo == 'finestra':
        prism(det, pts, Y(0.2), Y(0.22), I['vetro'])
        tb = 0.06
        if not arco:
            box(det, (x0, Y(0.12), zA), (x0 + tb, Y(0.2), zB), lg)
            box(det, (x1 - tb, Y(0.12), zA), (x1, Y(0.2), zB), lg)
            box(det, (x0, Y(0.12), zA), (x1, Y(0.2), zA + tb), lg)
            box(det, (x0, Y(0.12), zB - tb), (x1, Y(0.2), zB), lg)
        box(det, (xc - 0.025, Y(0.15), zA), (xc + 0.025, Y(0.2), zB), lg)
        zs = zB - w / 2 if arco else zA + 0.6 * (zB - zA)
        box(det, (x0, Y(0.15), zs - 0.025), (x1, Y(0.2), zs + 0.025), lg)
        if (stile != 'graticcio' or k == 0) and stile != 'legno':
            box(det, (x0 - 0.1, Y(-0.09), zA - 0.09), (x1 + 0.1, Y(0.05), zA), pc)
        if stile == 'intonaco' and k >= 1:
            fw = 0.13
            box(det, (x0 - fw, Y(-0.03), zA), (x0, Y(0.0), zB + fw), pc)
            box(det, (x1, Y(-0.03), zA), (x1 + fw, Y(0.0), zB + fw), pc)
            box(det, (x0 - fw, Y(-0.03), zB), (x1 + fw, Y(0.0), zB + fw), pc)
        if k >= 1 and not arco:
            p = RNG.random()
            if p < 0.15:
                box(det, (x0, Y(0.02), zA), (xc - 0.005, Y(0.06), zB), I[imp])
                box(det, (xc + 0.005, Y(0.02), zA), (x1, Y(0.06), zB), I[imp])
            elif p < 0.85:
                yo0, yo1 = Y(-0.13), Y(-0.09)
                box(det, (x0 - w / 2 - 0.03, yo0, zA), (x0 - 0.03, yo1, zB), I[imp])
                box(det, (x1 + 0.03, yo0, zA), (x1 + w / 2 + 0.03, yo1, zB), I[imp])
            if p >= 0.15 and RNG.random() < 0.35:
                fioriera(det, x0, x1, zA, Y)
    elif tipo == 'porta':
        ma = rc(['assi', imp])
        if w > 1.6:
            ma = 'tavole'   # portone dei palazzi: legno bruno naturale, mai tinto come le imposte
        prism(det, pts, Y(0.2), Y(0.27), I[ma])
        for zz in (zA + 0.45, zA + 1.9):
            box(det, (x0 + 0.05, Y(0.16), zz), (x1 - 0.05, Y(0.2), zz + 0.07), I['ferro'])
        if verso < 0:
            box(det, (x0 - 0.2, Y(-0.45), 0.0), (x1 + 0.2, Y(0.05), 0.14), pc)
            if RNG.random() < 0.45:   # lanterna a muro
                lx = x1 + 0.35; fe = I['ferro']
                box(det, (lx - 0.02, Y(0.0), 2.95), (lx + 0.02, Y(-0.4), 2.99), fe)
                ML = T(lx, Y(-0.38), 0)
                lathe(det, [(0.06, 2.54), (0.1, 2.6)], 6, fe, ML, liscio=False)
                lathe(det, [(0.09, 2.6), (0.09, 2.8)], 6, I['vetro'], ML, liscio=False)
                lathe(det, [(0.13, 2.8), (0.03, 2.95)], 6, fe, ML, liscio=False)
        if not arco:
            box(det, (x0 - 0.15, Y(-0.05), zB), (x1 + 0.15, Y(0.05), zB + 0.22), pc)
        elif w > 1.6:   # portale nobile: doppia ghiera in rilievo e stipiti
            zs = zB - w / 2
            arco_rilievo(det, xc, zs, w / 2, w / 2 + 0.22, Y(-0.12), Y(0.0), pc)
            arco_rilievo(det, xc, zs, w / 2 + 0.22, w / 2 + 0.42, Y(-0.2), Y(0.0), pc)
            for (a, b) in ((x0 - 0.42, x0), (x1, x1 + 0.42)):
                box(det, (a, Y(-0.16), 0.0), (b, Y(0.0), zs), pc)
    else:  # bottega
        box(det, (x0 - 0.05, Y(1.2), zA), (x1 + 0.05, Y(1.26), zB), I['interno_buio'])
        box(det, (x0 + 0.08, Y(0.1), 0.0), (x1 - 0.08, Y(0.55), 0.92), I['assi'])
        box(det, (x0 + 0.02, Y(0.02), 0.92), (x1 - 0.02, Y(0.6), 0.98), lg)
        tenda(det, x0 - 0.25, x1 + 0.25, zB + 0.05, Y)

def montanti(det, L, nw, z0, h, Y):
    """Intonaco dei piani alti: montanti di legno in rilievo vero agli spigoli e fra le campate delle finestre,
    con la trave in testa al piano (prima erano travi dipinte nella texture dell'intonaco giallo)."""
    lg = I['legno_travi']
    for i in range(nw + 1):
        x = L * i / nw
        box(det, (max(0.0, x - 0.09), Y(-0.08), z0), (min(L, x + 0.09), Y(0.0), z0 + h), lg)
    box(det, (0.0, Y(-0.08), z0 + h - 0.18), (L, Y(0.0), z0 + h), lg)

def travi(det, W, z0, h, yface, verso, ap):
    Y = lambda d: yface - verso * d
    lg = I['legno_travi']; y0, y1 = Y(-0.08), Y(0.03)
    B = lambda xa, xb, za, zb: box(det, (xa, y0, za), (xb, y1, zb), lg)
    B(0, W, z0, z0 + 0.22); B(0, W, z0 + h - 0.2, z0 + h)
    B(0, 0.2, z0, z0 + h); B(W - 0.2, W, z0, z0 + h)
    posti = [(0, 0.2), (W - 0.2, W)]; vani = set()
    for (tipo, xc, w, za, zb) in ap:
        x0, x1 = xc - w / 2, xc + w / 2
        B(x0 - 0.16, x0, z0, z0 + h); B(x1, x1 + 0.16, z0, z0 + h)
        posti += [(x0 - 0.16, x0), (x1, x1 + 0.16)]; vani.add((x0, x1))
        B(x0 - 0.16, x1 + 0.16, z0 + za - 0.14, z0 + za)
        B(x0 - 0.16, x1 + 0.16, z0 + zb, z0 + zb + 0.14)
    posti.sort()
    zl, zh = z0 + 0.22, z0 + h - 0.2
    for (a, b), (c, d) in zip(posti, posti[1:]):
        gap = c - b
        if gap < 0.6:
            continue
        if gap > 1.9:
            m = (b + c) / 2
            B(m - 0.08, m + 0.08, zl, zh)
            campate = [(b, m - 0.08), (m + 0.08, c)]
        else:
            campate = [(b, c)]
        for (xa, xb) in campate:
            tb = 0.15
            verso_diag = RNG.random() < 0.5   # estratto anche per i vani: la sequenza casuale (e il borgo) non cambia
            if (xa, xb) in vani:
                continue   # campata fra i montanti di una finestra: niente diagonale davanti al vetro
            if verso_diag:
                pts = [(xa, zl), (xa + tb, zl), (xb, zh), (xb - tb, zh)]
            else:
                pts = [(xb - tb, zl), (xb, zl), (xa + tb, zh), (xa, zh)]
            prism(det, pts, y0, y1, lg)
            if xb - xa > 1.1:
                zm = (zl + zh) / 2
                B(xa, xb, zm - 0.07, zm + 0.07)

def tetto_lato(det, W, yf, D, zt, pend, mt, mw, cornice):
    tp = math.tan(pend); ov = 0.45; ovs = 0.3; th = 0.16; tv = th / math.cos(pend)
    ym = (yf + D) / 2; s = ym - yf; zr = zt + s * tp
    ye, ze = yf - ov, zt - ov * tp
    yb = D + ov
    prism(det, [(ye, ze), (ym, zr), (ym, zr + tv), (ye, ze + tv)], -ovs, W + ovs, I[mt], 'x')
    prism(det, [(ym, zr), (yb, ze), (yb, ze + tv), (ym, zr + tv)], -ovs, W + ovs, I[mt], 'x')
    cz = zr + tv - 0.03
    prism(det, [(ym + 0.12 * math.cos(math.pi * i / 8), cz + 0.12 * math.sin(math.pi * i / 8)) for i in range(9)],
          -ovs, W + ovs, I[mt], 'x')
    for (a0, a1) in ((0.0, 0.3), (W - 0.3, W)):
        prism(det, [(yf, zt), (D, zt), (ym, zr)], a0, a1, I[mw], 'x')
    if cornice:
        box(det, (-0.02, yf - 0.28, zt - 0.22), (W + 0.02, yf + 0.02, zt + 0.02), I['pietra_cornici'])
        box(det, (-0.02, D - 0.02, zt - 0.22), (W + 0.02, D + 0.28, zt + 0.02), I['pietra_cornici'])
    return zr, ym, s

def tetto_fronte(det, W, yf, D, zt, pend, mt, graticcio):
    tp = math.tan(pend); ov = 0.35; ovf = 0.55; th = 0.16; tv = th / math.cos(pend)
    xm = W / 2; zr = zt + xm * tp; ze = zt - ov * tp
    y0, y1 = yf - ovf, D + 0.35
    prism(det, [(-ov, ze), (xm, zr), (xm, zr + tv), (-ov, ze + tv)], y0, y1, I[mt], 'y')
    prism(det, [(xm, zr), (W + ov, ze), (W + ov, ze + tv), (xm, zr + tv)], y0, y1, I[mt], 'y')
    cz = zr + tv - 0.03
    prism(det, [(xm + 0.12 * math.cos(math.pi * i / 8), cz + 0.12 * math.sin(math.pi * i / 8)) for i in range(9)],
          y0, y1, I[mt], 'y')
    if graticcio:
        lg = I['legno_travi']
        prism(det, [(-ov, ze - 0.2), (xm, zr - 0.2), (xm, zr + tv), (-ov, ze + tv)], y0 - 0.04, y0 + 0.03, lg, 'y')
        prism(det, [(xm, zr - 0.2), (W + ov, ze - 0.2), (W + ov, ze + tv), (xm, zr + tv)], y0 - 0.04, y0 + 0.03, lg, 'y')
    return zr

def comignolo(det, x, y, z0, z1):
    box(det, (x - 0.3, y - 0.4, z0), (x + 0.3, y + 0.4, z1), I['mattoni'])
    box(det, (x - 0.38, y - 0.48, z1), (x + 0.38, y + 0.48, z1 + 0.1), I['pietra_cornici'])
    box(det, (x - 0.12, y - 0.12, z1 + 0.1), (x + 0.12, y + 0.12, z1 + 0.35), I['terracotta'] if 'terracotta' in I else I['mattoni'])

def zona_di(p):
    for nome, pts in ZONE:
        if dentro_poligono(p, pts):
            return nome
    return 'misto'

def materiali_casa(stile, Z=None):
    """Muro del piano terra, muro dei piani alti, tetto e pendenza per uno stile; con una zona Z il tetto
    e' quello dominante della zona nell'80% dei casi."""
    if stile == 'pietra':
        mt0 = rc(['pietra_blocchi', 'pietra_muro', 'mattoni']); ms = mt0
        mtet = rc(['coppi', 'ardesia']); pend = math.radians(rr(30, 38))
    elif stile == 'graticcio':
        mt0 = rc(['pietra_muro', 'pietra_blocchi']); ms = rc(['intonaco_bianco', 'intonaco_bianco', 'intonaco_giallo'])
        mtet = rc(['ardesia', 'ardesia', 'coppi', 'paglia']); pend = math.radians(rr(48, 56))
    elif stile == 'legno':
        mt0 = rc(['tavole', 'tavole', 'pietra_muro']); ms = 'tavole'
        mtet = 'paglia'; pend = math.radians(rr(46, 54))
    else:
        mt0 = rc(['pietra_blocchi', 'pietra_muro']); ms = rc(['intonaco_giallo', 'intonaco_rosa', 'intonaco_bianco'])
        mtet = 'coppi'; pend = math.radians(rr(24, 30))
    if Z is not None:
        if RNG.random() < 0.8:
            mtet = Z['tetto']
        else:
            mtet = rc([t for t in ('coppi', 'ardesia', 'coppi_vecchi') if t != Z['tetto']])
        if mtet == 'paglia':
            pend = max(pend, math.radians(46))
    return mt0, ms, mtet, pend

def edificio(nome, W, D, n, stile, tetto, M, coll, retro=True, bottega=False, lati=(False, False), Z=None):
    mt0, ms, mtet, pend = materiali_casa(stile, Z)
    imp = rc(['imposte_verdi', 'imposte_rosse', 'imposte_blu', 'assi'])
    j = 0.32 if stile == 'graticcio' else 0.0
    det = nuovo_bm(); parti = []
    pal = bool(Z and Z.get('palazzo')) and stile == 'pietra'   # palazzetto nobile
    n_rng = n   # i numeri casuali si estraggono come prima (stesso borgo), le varianti vengono da RNG_D
    vp = None
    if pal:   # ogni palazzetto diverso dai vicini: piani, bifore, portale, stemma
        vp = dict(piano_in_piu=RNG_D.random() < 0.45, bifore=RNG_D.choice([-1, 0, 0, 1]),
                  centrale=RNG_D.random() < 0.5, posto_stemma=RNG_D.choice(['portale', 'alto', 'lato']),
                  wbif=round(RNG_D.uniform(1.25, 1.6), 2))
        if not PALAZZI:
            RNG_D.shuffle(ARMI)
        ARME[0] = ARMI[len(PALAZZI) % len(ARMI)]; PALAZZI.append(nome)
        if vp['piano_in_piu']:
            n += 1
    piani = []
    for k in range(n):
        z0 = 0.0 if k == 0 else H0 + (k - 1) * HF
        piani.append((k, z0, H0 if k == 0 else HF, -j * k))
    zt = piani[-1][1] + piani[-1][2]; yft = piani[-1][3]
    nw = max(1, int(W / 2.3))
    porta_i = RNG.randrange(nw)
    pc = I['pietra_cornici']
    balc = None
    if pal:
        tetto = 'lato'
        ib = None
        if n_rng > 1 and RNG.random() < 0.45:
            ib = RNG.randrange(nw)
            if ib != porta_i:
                RNG.randint(1, n_rng - 1)   # era il piano del balcone: ora sempre il piano nobile
            else:
                ib = None
        if vp['bifore'] < 0 and nw > 2 or vp['bifore'] > 0 and W / (nw + 1) >= 2.1:
            nw += vp['bifore']
        porta_i = nw // 2 if vp['centrale'] and nw % 2 == 1 else min(porta_i, nw - 1)
        vp['ultimo'] = n - 1
        vp['stemma'] = {'portale': (1, porta_i), 'alto': (n - 1, nw // 2),
                        'lato': (1, nw - 1 if porta_i < nw / 2 else 0)}[vp['posto_stemma']]
        if ib is not None:
            ib = min(ib, nw - 1)
            if ib != porta_i and (1, ib) != vp['stemma']:
                balc = (1, ib)
    for (k, z0, h, yf) in piani:
        mw = mt0 if k == 0 else ms
        mcut = pc if mw.startswith('intonaco') else I[mw]
        tagli = []
        facce = [(yf, -1)] + ([(D, 1)] if retro else [])
        for (yface, verso) in facce:
            ap = aperture(k, W, nw, porta_i if verso < 0 else (0 if k == 0 else -1), bottega and verso < 0, stile,
                          vp if pal and verso < 0 else None)
            for ia, a in enumerate(ap):
                n0 = len(det.faces)
                if balc == (k, ia) and verso < 0 and a[0] == 'bifora':   # al posto della bifora
                    zp, zb = Z_BALCONE[k == vp['ultimo']]
                    portafinestra(det, tagli, a[1], min(a[2], 1.2), z0 + zp, z0 + zb, yface, verso, mcut)
                    balcone(det, a[1], a[2], z0 + zp, yface, verso)
                    BALCONI.append((M @ Vector((a[1], yface, z0 + zp)), M.to_3x3() @ Vector((0, verso, 0))))
                    continue
                apertura(det, tagli, a, z0, yface, verso, k, stile, imp, mcut)
                if a[0] in ('finestra', 'porta'):
                    pts, _, a1, ax, _, Mt = tagli[-1]
                    segna_apertura(det, n0, a[0], (0, verso, 0), (pts, yface, a1, ax, I[mw], Mt))
            if stile == 'graticcio' and k >= 1:
                travi(det, W, z0, h, yface, verso, ap)
            Y = lambda d, yface=yface, verso=verso: yface - verso * d
            if stile in ('pietra', 'intonaco') and k >= 1:
                box(det, (-0.02, Y(-0.1), z0 - 0.06), (W + 0.02, Y(0.02), z0 + 0.12), pc)
            if stile == 'intonaco' and k >= 1:
                montanti(det, W, nw, z0, h, Y)
            if stile == 'legno':   # pali d'angolo e trave di piano
                for (xa, xb) in ((0.0, 0.18), (W - 0.18, W)):
                    box(det, (xa, Y(-0.06), z0), (xb, Y(0.0), z0 + h), I['legno_travi'])
                box(det, (0.0, Y(-0.06), z0 + h - 0.18), (W, Y(0.0), z0 + h), I['legno_travi'])
            if (stile == 'intonaco') or (k == 0 and stile == 'graticcio'):
                z = z0; alt = 0
                while z < z0 + h - 0.05:
                    wq = 0.42 if alt % 2 == 0 else 0.26
                    zz = min(z + 0.3, z0 + h)
                    box(det, (0, Y(-0.035), z), (wq, Y(0.0), zz), pc)
                    box(det, (W - wq, Y(-0.035), z), (W, Y(0.0), zz), pc)
                    z += 0.32; alt += 1
        # facciate laterali esposte (case d'angolo o accanto a un vicolo)
        for li, lato in enumerate(('sx', 'dx')):
            if not lati[li]:
                continue
            Ls = D - yf
            CM[0] = (RZ(-math.pi / 2) @ T(-D, 0, 0)) if lato == 'sx' else (T(W, 0, 0) @ RZ(math.pi / 2) @ T(yf, 0, 0))
            try:
                aps = aperture(k, Ls, max(1, int(Ls / 2.6)), -1, False, stile)
                for a in aps:
                    n0 = len(det.faces)
                    apertura(det, tagli, a, z0, 0.0, -1, k, stile, imp, mcut)
                    if a[0] in ('finestra', 'porta'):
                        pts, _, a1, ax, _, Mt = tagli[-1]
                        segna_apertura(det, n0, a[0], (0, -1, 0), (pts, 0.0, a1, ax, I[mw], Mt))
                if stile == 'graticcio' and k >= 1:
                    travi(det, Ls, z0, h, 0.0, -1, aps)
                if stile == 'intonaco' and k >= 1:
                    montanti(det, Ls, max(1, int(Ls / 2.6)), z0, h, lambda d: d)
            finally:
                CM[0] = None
        sh = guscio(f"{nome}_p{k}",
                    lambda bm, z0=z0, h=h, yf=yf, mw=mw: box(bm, (0, yf, z0), (W, D, z0 + h), I[mw]),
                    tagli, coll)
        parti.append(sh)
        if j > 0 and k >= 1:
            yprev = piani[k - 1][3]
            x = 0.35
            while x < W - 0.3:
                box(det, (x - 0.07, yf + 0.02, z0 - 0.16), (x + 0.07, yprev + 0.05, z0), I['legno_travi'])
                x += 0.55
    # --- tetto ---
    if tetto == 'lato':
        zr, ym, s = tetto_lato(det, W, yft, D, zt, pend, mtet, ms, stile in ('pietra', 'intonaco'))
        if pal:   # cornicione su mensole, davanti e dietro
            for (yy, v) in ((yft, -1), (D, 1)):
                x = 0.35
                while x < W - 0.2:
                    y0, y1 = sorted((yy, yy + v * 0.38))
                    box(det, (x - 0.09, y0, zt - 0.62), (x + 0.09, y1, zt - 0.22), pc); x += 0.7
                y0, y1 = sorted((yy, yy + v * 0.14))
                box(det, (-0.02, y0, zt - 0.8), (W + 0.02, y1, zt - 0.62), pc)
        if RNG.random() < 0.7:
            cx = rr(0.25, 0.75) * W; cy = ym + s * 0.35 * rc([-1, 1])
            comignolo(det, cx, cy, zt, zr + 0.9)
    else:
        zr = tetto_fronte(det, W, yft, D, zt, pend, mtet, stile in ('graticcio', 'legno'))
        xm = W / 2
        tg = []
        fin = (zr - zt) > 2.3
        if fin:
            ap = ('finestra', xm, 0.75, 0.7, 1.7)
            mcut = pc if ms.startswith('intonaco') else I[ms]
            n0 = len(det.faces)
            apertura(det, tg, ap, zt, yft, -1, 2, stile, imp, mcut)
            pts, _, a1, ax, _, Mt = tg[-1]
            segna_apertura(det, n0, 'finestra', (0, -1, 0), (pts, yft, a1, ax, I[ms], Mt))
        sh = guscio(f"{nome}_frontone",
                    lambda bm: prism(bm, [(0, zt), (W, zt), (xm, zr)], yft, yft + 0.3, I[ms], 'y'), tg, coll)
        parti.append(sh)
        prism(det, [(0, zt), (W, zt), (xm, zr)], D - 0.3, D, I[ms], 'y')
        if stile == 'graticcio':
            lg = I['legno_travi']; y0, y1 = yft - 0.05, yft + 0.03
            prism(det, [(0, zt), (0.3, zt), (xm, zr - 0.3), (xm, zr)], y0, y1, lg, 'y')
            prism(det, [(W - 0.3, zt), (W, zt), (xm, zr), (xm, zr - 0.3)], y0, y1, lg, 'y')
            if fin:
                box(det, (xm - 0.55, y0, zt), (xm - 0.39, y1, zt + 1.84), lg)
                box(det, (xm + 0.39, y0, zt), (xm + 0.55, y1, zt + 1.84), lg)
                box(det, (xm - 0.55, y0, zt + 1.7), (xm + 0.55, y1, zt + 1.84), lg)
                box(det, (xm - 0.55, y0, zt + 0.56), (xm + 0.55, y1, zt + 0.7), lg)
                if zr - 0.3 > zt + 1.9:
                    box(det, (xm - 0.08, y0, zt + 1.84), (xm + 0.08, y1, zr - 0.25), lg)
            else:
                box(det, (xm - 0.08, y0, zt), (xm + 0.08, y1, zr - 0.25), lg)
        if RNG.random() < 0.6:
            comignolo(det, xm + xm * 0.45 * rc([-1, 1]), rr(yft + 1.5, D - 1.5), zt, zr + 0.6)
    parti.append(oggetto(f"{nome}_det", det, MB, coll))
    ob = unisci(parti, nome)
    uv_finale(ob)
    ob.matrix_world = M
    smussa(ob)
    FACCIATE.append((M, W, stile, bottega, n))
    return ob

def scegli_stile(Z=None):
    p = RNG.random()
    if Z is None:
        if p < 0.5: return 'graticcio', ('fronte' if RNG.random() < 0.6 else 'lato')
        if p < 0.8: return 'intonaco', ('lato' if RNG.random() < 0.85 else 'fronte')
        return 'pietra', ('lato' if RNG.random() < 0.7 else 'fronte')
    for stile, w in Z['stili']:
        p -= w
        if p < 0:
            break
    if stile in ('graticcio', 'legno'): return stile, ('fronte' if RNG.random() < 0.6 else 'lato')
    if stile == 'intonaco': return stile, ('lato' if RNG.random() < 0.85 else 'fronte')
    return stile, ('lato' if RNG.random() < 0.7 else 'fronte')

def fila(prefisso, punti, coll, prof=(8.0, 10.0), piani=(2, 3), retro=True, botteghe=0.0, buchi=(),
         interno=None, vicolo=0.0, per_zona=False, fronte=0.0, accessori=None):
    """Case lungo una polilinea: facciata a destra del verso di percorrenza, profondita' a sinistra.
    I tratti occupati (strade, lotti riservati, altre case, fascia delle mura) restano liberi;
    'buchi' = intervalli di ascissa curvilinea da lasciare comunque vuoti.
    Con 'interno' (vedi Interno) costruisce case semplici e lastrica davanti un vicolo largo 'vicolo'.
    Con 'per_zona' larghezze, piani, botteghe, stili e tetti seguono STILI_ZONA della zona del lotto;
    'fronte' = spazio libero davanti alla facciata (per le tettoie, messe in 'accessori')."""
    i = 0; s0 = 0.0
    for a, b in zip(punti, punti[1:]):
        a = Vector((a[0], a[1], 0)); e = Vector((b[0], b[1], 0)) - a
        L = e.length; e.normalize()
        R = Matrix.Translation(a) @ RZ(math.atan2(e.y, e.x))
        s = 0.0; dopo_buco = True
        while L - s >= 4.2:
            dentro = [bc for bc in buchi if bc[0] - 0.01 <= s0 + s < bc[1]]
            if dentro:
                s = dentro[0][1] - s0; dopo_buco = True; continue
            M = R @ T(s, 0, 0)
            Z = STILI_ZONA.get(zona_di(tuple((M @ Vector((3.0, 4.0, 0.0))).xy))) if per_zona else None
            wmax = Z['larg'][1] + 1.0 if Z else 8.5
            cap = wmax + 3.5
            lim = min([L - s, cap] + [bc[0] - s0 - s for bc in buchi if bc[0] > s0 + s])
            spazio = corsa(M, lim, 5.0)
            if spazio < 4.2:
                s += 0.5; dopo_buco = True; continue
            W = rr(*Z['larg']) if Z else rr(5.2, 7.6)
            if spazio - W < 4.2:
                W = spazio if spazio <= wmax else spazio / 2
            fine = W > spazio - 0.05 and spazio < cap - 0.05
            pr = Z['prof'] if (Z and interno is None) else prof
            D = rr(pr[0], pr[1])
            if not lotto_libero(M, W, D):   # dietro c'e' qualcosa: casa meno profonda
                d0, d1 = 5.0, D
                while d1 - d0 > 0.1:
                    c = (d0 + d1) / 2
                    if lotto_libero(M, W, c): d0 = c
                    else: d1 = c
                D = d0
            lati = (dopo_buco, fine); dopo_buco = False
            if interno is None:
                stile, tetto = scegli_stile(Z)
                pi = Z['piani'] if Z else piani
                n = RNG.randint(pi[0], pi[1])
                edificio(f"{prefisso}_{i:02d}", W, D, n, stile, tetto, M, coll, retro=retro,
                         bottega=RNG.random() < (Z['botteghe'] if Z else botteghe), lati=lati, Z=Z)
                if Z and accessori and fronte >= 1.0 and RNG.random() < Z.get('tettoie', 0.0):
                    accessori.tettoia(W, min(1.5, fronte), M)
            else:
                pi = Z['piani_int'] if Z else piani
                interno.casa(W, D, RNG.randint(pi[0], pi[1]), M, vicolo, Z)
            occupa(rett_mondo(M, 0, 0, W, D))
            s += W; i += 1
        s0 += L

def linee_prima_fila():
    """Le quattro file che si affacciano sulla piazza: nome, polilinea, parametri."""
    PX, PY, EXT = PIAZZA_X, PIAZZA_Y, 9.0
    return [("Casa_S", [(PX + EXT, -PY), (-(PX + EXT), -PY)], dict(piani=(2, 3), botteghe=0.45)),
            ("Casa_N", [(-(PX + EXT), PY), (PX + EXT, PY)], dict(piani=(2, 4), botteghe=0.45)),
            ("Casa_E", [(PX, PY), (PX, -PY)], dict(piani=(2, 3), botteghe=0.45)),
            ("Casa_O", [(-PX, -PY), (-PX, PY)], dict(piani=(2, 3), botteghe=0.3))]

# ----------------------------------------------------------------------
#  INTERNO DEGLI ISOLATI (case sul retro, cortili, rimesse, vicoli)
#  Costruzioni semplici: aperture finte (niente booleani), raccolte in pochi oggetti.
# ----------------------------------------------------------------------
def facce_casa(W, D):
    """(lunghezza, matrice) delle quattro facciate: x lungo la facciata, -y verso l'esterno."""
    return [(W, Matrix.Identity(4)), (W, T(W, D, 0) @ RZ(math.pi)),
            (D, RZ(-math.pi / 2) @ T(-D, 0, 0)), (D, T(W, 0, 0) @ RZ(math.pi / 2))]

def finestra_finta(det, xc, w, zA, zB, imp, stile='pietra'):
    """Finestra delle case interne (muro pieno, senza booleano): mazzette e architrave in rilievo fanno da
    strombo, vetro scuro a filo del muro con telaio e croce di legno come quelle delle vie, davanzale;
    imposte aperte contro le mazzette."""
    x0, x1 = xc - w / 2, xc + w / 2
    lg = I['legno_travi']
    mz = lg if stile in ('graticcio', 'legno') else I['pietra_cornici']
    sp, lm = 0.11, 0.12   # sporgenza e larghezza di mazzette e architrave
    box(det, (x0 - lm, -sp, zA), (x0, 0.0, zB), mz)
    box(det, (x1, -sp, zA), (x1 + lm, 0.0, zB), mz)
    box(det, (x0 - lm, -sp, zB), (x1 + lm, 0.0, zB + 0.14), mz)
    box(det, (x0 - lm - 0.04, -sp - 0.06, zA - 0.09), (x1 + lm + 0.04, 0.0, zA), I['pietra_cornici'])
    box(det, (x0, -0.012, zA), (x1, -0.002, zB), I['vetro'])
    tb = 0.055
    for (a, b, c, d) in ((x0, x0 + tb, zA, zB), (x1 - tb, x1, zA, zB), (x0, x1, zA, zA + tb), (x0, x1, zB - tb, zB)):
        box(det, (a, -0.06, c), (b, -0.002, d), lg)
    box(det, (xc - 0.025, -0.045, zA), (xc + 0.025, -0.002, zB), lg)   # croce
    zs = zA + 0.6 * (zB - zA)
    box(det, (x0, -0.045, zs - 0.025), (x1, -0.002, zs + 0.025), lg)
    if imp:
        box(det, (x0 - lm - w / 2 - 0.02, -sp - 0.04, zA), (x0 - lm - 0.02, -sp, zB), I[imp])
        box(det, (x1 + lm + 0.02, -sp - 0.04, zA), (x1 + lm + w / 2 + 0.02, -sp, zB), I[imp])

def travi_interne(det, L, nw, n, zt):
    """Graticcio delle case interne in rilievo vero (10 cm): dormienti ai piani, montanti agli spigoli e ai lati
    delle finestre, saette (8 cm) nelle campate. Il verso delle saette viene da RNG_D: il borgo non cambia."""
    lg = I['legno_travi']; sp = 0.10
    B = lambda x0, x1, z0, z1, d=sp: box(det, (x0, -d, z0), (x1, 0.0, z1), lg)
    posti = [(-sp, 0.2), (L - 0.2, L)]   # il montante d'angolo sinistro copre lo spigolo
    for i in range(nw):
        xc = L * (i + 0.5) / nw
        posti += [(xc - 0.375 - 0.15, xc - 0.375 - 0.01), (xc + 0.375 + 0.01, xc + 0.375 + 0.15)]
    posti.sort()
    for (a, b) in posti:
        B(a, b, H0, zt)
    for k in range(1, n):
        z0 = H0 + (k - 1) * HF
        zh = (z0 + HF if k < n - 1 else zt) - 0.11
        B(-sp, L, z0 - 0.1, z0 + 0.12)
        zl = z0 + 0.12
        for (a, b), (c, d) in zip(posti, posti[1:]):
            gap = c - b
            if gap < 0.6 or any(abs(b - (L * (i + 0.5) / nw - 0.375 - 0.01)) < 1e-6 for i in range(nw)):
                continue   # campata della finestra
            campate = [(b, c)]
            if gap > 1.9:
                m = (b + c) / 2; B(m - 0.08, m + 0.08, zl, zh)
                campate = [(b, m - 0.08), (m + 0.08, c)]
            for (xa, xb) in campate:
                tb = 0.15
                if RNG_D.random() < 0.5:
                    pts = [(xa, zl), (xa + tb, zl), (xb, zh), (xb - tb, zh)]
                else:
                    pts = [(xb - tb, zl), (xb, zl), (xa + tb, zh), (xa, zh)]
                prism(det, pts, -0.08, 0.0, lg)
                if xb - xa > 1.1:
                    zm = (zl + zh) / 2; B(xa, xb, zm - 0.07, zm + 0.07, 0.08)
    B(-sp, L, zt - 0.22, zt)

def casa_semplice(det, W, D, n, M, Z=None):
    """Casa dell'interno: stesse masse e tetti delle case sulle strade, dettagli ridotti."""
    stile, tetto = scegli_stile(Z)
    mt0, ms, mtet, pend = materiali_casa(stile, Z)
    imp = rc(['imposte_verdi', 'imposte_rosse', 'imposte_blu', 'assi', None])
    if W > D * 1.1:
        tetto = 'lato'
    elif D > W * 1.1 and RNG.random() < 0.75:
        tetto = 'fronte'
    zt = H0 + (n - 1) * HF
    CM[0] = M
    try:
        box(det, (0, 0, 0), (W, D, H0), I[mt0])
        if n > 1:
            box(det, (0, 0, H0), (W, D, zt), I[ms])
        for f, (L, Mf) in enumerate(facce_casa(W, D)):
            CM[0] = M @ Mf
            nw = max(1, int(L / 2.6))
            porta_i = RNG.randrange(nw) if f == 0 else -1
            for k in range(n):
                z0 = 0.0 if k == 0 else H0 + (k - 1) * HF
                for i in range(nw):
                    xc = L * (i + 0.5) / nw; n0 = len(det.faces)
                    if k == 0 and i == porta_i:
                        box(det, (xc - 0.55, -0.04, 0.0), (xc + 0.55, 0.0, 2.2), I['assi'])
                        box(det, (xc - 0.7, -0.1, 2.2), (xc + 0.7, 0.0, 2.38), I['pietra_cornici'])
                        segna_apertura(det, n0, 'porta', (0, -1, 0))
                    elif k == 0:
                        finestra_finta(det, xc, 0.7, 1.1, 2.0, None, stile)
                        segna_apertura(det, n0, 'finestra', (0, -1, 0))
                    else:
                        finestra_finta(det, xc, 0.75, z0 + 0.85, z0 + 2.0, imp if f < 2 else None, stile)
                        segna_apertura(det, n0, 'finestra', (0, -1, 0))
            if stile == 'graticcio' and n > 1:
                travi_interne(det, L, nw, n, zt)
            elif n > 1 and stile in ('pietra', 'intonaco'):
                box(det, (-0.02, -0.08, H0 - 0.05), (L + 0.02, 0.0, H0 + 0.1), I['pietra_cornici'])
                if stile == 'intonaco':
                    montanti(det, L, nw, H0, zt - H0, lambda d: d)
            elif stile == 'legno':
                for x in (0.0, L - 0.18):
                    box(det, (x, -0.05, 0.0), (x + 0.18, 0.0, zt), I['legno_travi'])
        CM[0] = M
        if tetto == 'lato':
            zr, ym, s = tetto_lato(det, W, 0.0, D, zt, pend, mtet, ms, stile in ('pietra', 'intonaco'))
            if RNG.random() < 0.5:
                comignolo(det, rr(0.25, 0.75) * W, ym + s * 0.35 * rc([-1, 1]), zt, zr + 0.9)
        else:
            zr = tetto_fronte(det, W, 0.0, D, zt, pend, mtet, stile in ('graticcio', 'legno'))
            for (y0, y1) in ((0.0, 0.3), (D - 0.3, D)):
                prism(det, [(0, zt), (W, zt), (W / 2, zr)], y0, y1, I[ms], 'y')
            if RNG.random() < 0.5:
                comignolo(det, W / 2 + W * 0.22 * rc([-1, 1]), rr(1.5, max(1.6, D - 1.5)), zt, zr + 0.6)
    finally:
        CM[0] = None

def catasta(det, x0, x1, y0, y1, h, M):
    """Catasta di tronchi distesi lungo x."""
    r = 0.09
    for riga in range(int(h / (2 * r))):
        for c in range(int((y1 - y0) / (2 * r))):
            y = y0 + r + c * 2 * r + (r if riga % 2 else 0) * 0.5
            lathe(det, [(r * rr(0.8, 1.1), x0 + rr(0, 0.08)), (r, x1 - rr(0, 0.08))], 6, I['legno_grezzo'],
                  M @ T(0, y, r + riga * 2 * r * 0.9) @ RY(math.pi / 2), liscio=False)

RIMESSE = []   # (matrice, larghezza, profondita') delle rimesse, per controlli e punti di vista

def porta_rimessa(det, L, h):
    """Porta di tavole (o portone, se il lato e' largo) al centro di un lato della rimessa, nel sistema della
    facciata (x lungo il lato, -y verso fuori): telaio di travi, bandelle di ferro."""
    wd, hd = (min(1.8, L - 0.8), min(2.1, h - 0.2)) if L >= 2.6 else (0.9, min(1.9, h - 0.2))
    x0, x1 = L / 2 - wd / 2, L / 2 + wd / 2; lg = I['legno_travi']
    box(det, (x0, -0.05, 0.0), (x1, 0.0, hd), I['tavole'])
    box(det, (x0 - 0.1, -0.08, 0.0), (x0, 0.0, hd), lg)
    box(det, (x1, -0.08, 0.0), (x1 + 0.1, 0.0, hd), lg)
    box(det, (x0 - 0.1, -0.08, hd), (x1 + 0.1, 0.0, hd + 0.12), lg)
    for z in (0.4, hd - 0.45):
        box(det, (x0 + 0.05, -0.065, z), (x1 - 0.05, -0.05, z + 0.06), I['ferro'])

def rimessa(det, W, D, M):
    """Rimessa a un piano: tetto di paglia spesso a una falda, portico davanti con il portone, una porta su
    ogni altro lato (quelle contro un'altra costruzione le toglie controlla_aperture), a volte la legna."""
    h = rr(2.3, 2.9); mw = rc(['assi', 'assi', 'pietra_muro', 'legno_travi'])
    rc(['coppi', 'paglia', 'assi', 'ardesia'])   # estratto comunque: la sequenza casuale non cambia
    t = math.tan(math.radians(rr(16, 24))); ov = 0.45; yp = min(0.8, D * 0.25); th = 0.35
    zf = h + (D - yp) * t
    zr = lambda y: h + (D - y) * t   # intradosso della falda
    RIMESSE.append((M, W, D))
    CM[0] = M
    try:
        box(det, (0, yp, 0), (W, D, h), I[mw])
        prism(det, [(yp, h), (D, h), (yp, zf)], 0, W, I[mw], 'x')
        # paglia con spessore vero: 35 cm, sporge di 45 cm sui lati e dietro, di 20 cm oltre il portico
        prism(det, [(-0.2, zr(-0.2)), (D + ov, zr(D + ov)), (D + ov, zr(D + ov) + th), (-0.2, zr(-0.2) + th)],
              -ov, W + ov, I['paglia'], 'x')
        for x in (0.05, W - 0.2):   # pali del portico
            box(det, (x, 0.0, 0), (x + 0.15, 0.15, zf + yp * t), I['legno_travi'])
        wp = min(2.4, W - 1.0); xc = W / 2
        n0 = len(det.faces)
        if wp > 1.0:
            box(det, (xc - wp / 2, yp - 0.02, 0), (xc + wp / 2, yp, 2.0), I['interno_buio'])
            box(det, (xc - wp / 2 - 0.12, yp - 0.1, 2.0), (xc + wp / 2 + 0.12, yp, 2.18), I['legno_travi'])
        else:
            CM[0] = M @ T(0, yp, 0); porta_rimessa(det, W, h); CM[0] = M
        segna_apertura(det, n0, 'porta', (0, -1, 0))
        # una porta su ogni altro lato
        for f, (L, Mf) in enumerate(facce_casa(W, D - yp)):
            if f == 0 or L < 1.5:
                continue
            CM[0] = M @ T(0, yp, 0) @ Mf
            n0 = len(det.faces)
            porta_rimessa(det, L, h)
            segna_apertura(det, n0, 'porta', (0, -1, 0))
        CM[0] = M
        if yp >= 0.6 and xc - wp / 2 > 1.0 and RNG.random() < 0.5:
            catasta(det, 0.3, xc - wp / 2 - 0.2, 0.15, yp - 0.05, rr(0.8, 1.3), M)
    finally:
        CM[0] = None

PIANTE = {}          # modello -> collezioni-variante da istanziare
COLL_PIANTE = [None]  # collezione delle istanze
# modello Poly Haven: scala (il glTF e' in metri) per avere alberi e cespugli di taglia plausibile
SCALA_PIANTE = {'island_tree_02': 1.25, 'jacaranda_tree': 0.42, 'shrub_02': 0.7}
# tinta (lineare) della corteccia: l'olivo di Poly Haven e' grigio chiaro, qui grigio-bruno
TINTA_CORTECCIA = {'island_tree_02': (0.55, 0.45, 0.38)}

def carica_piante():
    """Importa i modelli di PIANTE (la prima volta dal glTF, poi da una cache .blend accanto, molto piu'
    veloce) e mette ogni variante in una collezione da istanziare, esclusa dalla scena."""
    PIANTE.clear()
    base = collezione("_Modelli_piante")
    for mid in SCALA_PIANTE:
        cartella = os.path.join(MODELLI, mid)
        cache = os.path.join(cartella, mid + "_cache.blend"); gltf = os.path.join(cartella, mid + ".gltf")
        prima = set(bpy.data.objects)
        try:
            if os.path.isfile(cache):
                with bpy.data.libraries.load(cache) as (src, dst):
                    dst.objects = list(src.objects)
                nuovi = [o for o in dst.objects if o is not None]
            elif os.path.isfile(gltf):
                bpy.ops.import_scene.gltf(filepath=gltf)
                nuovi = [o for o in bpy.data.objects if o not in prima]
                bpy.data.libraries.write(cache, set(nuovi), path_remap='ABSOLUTE')
            else:
                print("Modello mancante:", mid); continue
        except Exception as ex:
            print("Modello non caricato:", mid, ex); continue
        varianti = []
        for o in nuovi:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            for sl in (o.material_slots if mid in TINTA_CORTECCIA else []):
                m = sl.material
                if not m or 'leaves' in m.name or not m.use_nodes or m.get('_tinta'):
                    continue
                b = next((nd for nd in m.node_tree.nodes if nd.type == 'BSDF_PRINCIPLED'), None)
                if b and b.inputs['Base Color'].links:
                    mx = _mix(m.node_tree, -200, 400); _in(mx, 'Factor', 'VALUE').default_value = 1.0
                    m.node_tree.links.new(b.inputs['Base Color'].links[0].from_socket, _in(mx, 'A', 'RGBA'))
                    _in(mx, 'B', 'RGBA').default_value = (*TINTA_CORTECCIA[mid], 1)
                    m.node_tree.links.new(_out(mx, 'Result', 'RGBA'), b.inputs['Base Color'])
                m['_tinta'] = True
        for k, r in enumerate([o for o in nuovi if o.parent is None]):
            c = bpy.data.collections.new(f"{mid}_{k}"); base.children.link(c)
            gruppo = [r] + list(r.children_recursive)
            for o in gruppo:
                c.objects.link(o)
            pts = [o.matrix_world @ Vector(v) for o in gruppo if o.type == 'MESH' for v in o.bound_box]
            c.instance_offset = (sum(p.x for p in pts) / len(pts), sum(p.y for p in pts) / len(pts), 0.0)
            varianti.append(c)
        PIANTE[mid] = varianti
    lc = bpy.context.view_layer.layer_collection.children.get(base.name)
    if lc:
        lc.exclude = True

def istanza(mid, M, scala):
    if not PIANTE.get(mid) or COLL_PIANTE[0] is None:
        return False
    e = bpy.data.objects.new(mid, None)
    e.instance_type = 'COLLECTION'; e.instance_collection = rc(PIANTE[mid])
    s = scala * SCALA_PIANTE[mid]
    e.matrix_world = M @ RZ(rr(0, 2 * math.pi)) @ Matrix.Diagonal((s, s, s, 1.0))
    COLL_PIANTE[0].objects.link(e)
    return True

def albero(det, M, scala=1.0, tipo=None):
    """Albero Poly Haven (olivo o grande latifoglia), istanziato; senza modelli nessun albero."""
    tipo = tipo or ('island_tree_02' if RNG.random() < 0.7 else 'jacaranda_tree')
    istanza(tipo, M, rr(0.85, 1.15) * scala)

def cespuglio(det, M, scala=1.0):
    if istanza('shrub_02', M, rr(0.6, 1.2) * scala):
        return
    s = rr(0.5, 0.8) * scala   # senza modelli: cespuglio basso fatto di sfere
    for _ in range(RNG.randint(7, 12)):
        a = rr(0, 2 * math.pi); d = rr(0, 0.6) * s
        sfera(det, (d * math.cos(a), d * math.sin(a), rr(0.2, 0.6) * s), rr(0.25, 0.48) * s, I['foglie'], M,
              sc=(1, 1, 0.85), sub=2)
    if RNG.random() < 0.25:   # qualche fiore
        f = I[rc(['fiori_gialli', 'fiori_rossi', 'fiori_viola'])]
        for _ in range(6):
            a = rr(0, 2 * math.pi)
            sfera(det, (0.55 * s * math.cos(a), 0.55 * s * math.sin(a), rr(0.4, 0.8) * s), 0.09, f, M, sub=1)

def tettoia(det, W, prof, M):
    """Tettoia di bottega artigiana davanti alla facciata: pali, falda di assi o coppi, catasta e banco."""
    mt = I[rc(['assi', 'coppi_vecchi'])]; lg = I['legno_travi']
    x0, x1 = rr(0.2, 0.8), W - rr(0.2, 0.8); yp = -prof
    t = 0.45 / prof
    for x in [x0, x1] + ([(x0 + x1) / 2] if x1 - x0 > 4.5 else []):
        box(det, (x - 0.07, yp, 0.0), (x + 0.07, yp + 0.14, 2.6), lg, M)
    box(det, (x0 - 0.1, yp - 0.02, 2.5), (x1 + 0.1, yp + 0.16, 2.65), lg, M)
    prism(det, [(0.0, 3.05), (yp - 0.25, 2.6 - 0.25 * t), (yp - 0.25, 2.7 - 0.25 * t), (0.0, 3.15)],
          x0 - 0.3, x1 + 0.3, mt, 'x', M)
    xm = (x0 + x1) / 2
    catasta(det, x0 + 0.2, xm - 0.2, yp + 0.25, -0.1, rr(0.8, 1.3), M)
    box(det, (xm + 0.2, yp + 0.3, 0.75), (x1 - 0.3, -0.25, 0.85), I['assi'], M)    # banco
    for x in (xm + 0.3, x1 - 0.45):
        box(det, (x, yp + 0.35, 0.0), (x + 0.1, yp + 0.45, 0.75), lg, M)
        box(det, (x, -0.45, 0.0), (x + 0.1, -0.35, 0.75), lg, M)

def orto(det, W, D, M):
    """Orto recintato: steccato con cancelletto, aiuole rialzate con cavoli, insalate e qualche zucca."""
    lg, ass = I['legno_grezzo'], I['assi']
    perimetro = [((0, 0), (W, 0)), ((W, 0), (W, D)), ((W, D), (0, D)), ((0, D), (0, 0))]
    for k, ((ax, ay), (bx, by)) in enumerate(perimetro):
        Lp = math.hypot(bx - ax, by - ay); n = max(1, int(Lp / 1.5))
        for i in range(n + 1):
            t = i / n
            if k == 0 and abs(t * Lp - W / 2) < 0.7:   # cancelletto
                continue
            x, y = ax + (bx - ax) * t, ay + (by - ay) * t
            box(det, (x - 0.05, y - 0.05, 0.0), (x + 0.05, y + 0.05, 1.05), lg, M)
        for z in (0.45, 0.9):
            if k == 0:
                for (xa, xb) in ((0.0, W / 2 - 0.65), (W / 2 + 0.65, W)):
                    box(det, (xa, -0.02, z), (xb, 0.02, z + 0.08), ass, M)
            else:
                box(det, (min(ax, bx) - 0.02, min(ay, by) - 0.02, z), (max(ax, bx) + 0.02, max(ay, by) + 0.02, z + 0.08),
                    ass, M)
    y = 0.9
    while y < D - 0.6:
        box(det, (0.5, y - 0.3, 0.0), (W - 0.5, y + 0.3, 0.12), I['terra'], M)
        pianta = rc(['cavolo', 'cavolo', 'foglie', 'foglie', 'zucca'])
        x = 0.7
        while x < W - 0.6:
            r = rr(0.13, 0.2) if pianta != 'zucca' else rr(0.15, 0.22)
            sfera(det, (x + rr(-0.05, 0.05), y + rr(-0.05, 0.05), 0.12 + r * 0.6), r, I[pianta], M,
                  sc=(1, 1, 0.8), sub=1)
            x += rr(0.42, 0.55)
        y += 1.15

def giardino(det, W, D, M):
    """Giardino nobile: muro basso con copertina, prato, vialetti a croce con siepi, alberi nei quadranti,
    vasca di pietra al centro."""
    pm, pc = I['pietra_muro'], I['pietra_cornici']
    for (a, b) in [((0, 0), (W, 0.4)), ((0, D - 0.4), (W, D)), ((0, 0), (0.4, D)), ((W - 0.4, 0), (W, D))]:
        box(det, (a[0], a[1], 0.0), (b[0], b[1], 1.6), pm, M)
        box(det, (a[0] - 0.05, a[1] - 0.05, 1.6), (b[0] + 0.05, b[1] + 0.05, 1.72), pc, M)
    box(det, (0.4, 0.4, 0.0), (W - 0.4, D - 0.4, 0.03), I['prato'], M)
    xm, ym = W / 2, D / 2
    box(det, (xm - 0.7, 0.4, 0.0), (xm + 0.7, D - 0.4, 0.05), I['terra'], M)
    box(det, (0.4, ym - 0.7, 0.0), (W - 0.4, ym + 0.7, 0.05), I['terra'], M)
    for sx in (-1, 1):   # siepi lungo i vialetti, interrotte attorno alla vasca
        for (a, b) in ((0.6, ym - 2.2), (ym + 2.2, D - 0.6)):
            x0, x1 = sorted((xm + sx * 0.75, xm + sx * 1.25))
            box(det, (x0, a, 0.0), (x1, b, 0.75), I['foglie'], M)
        for (a, b) in ((0.6, xm - 2.2), (xm + 2.2, W - 0.6)):
            y0, y1 = sorted((ym + sx * 0.75, ym + sx * 1.25))
            box(det, (a, y0, 0.0), (b, y1, 0.75), I['foglie'], M)
    lathe(det, [(1.4, 0.0), (1.4, 0.55), (1.2, 0.55), (1.2, 0.2), (0.0, 0.2)], 24, pc, M @ T(xm, ym, 0))
    lathe(det, [(0.18, 0.2), (0.12, 1.3), (0.35, 1.45), (0.0, 1.5)], 12, pc, M @ T(xm, ym, 0))
    for qx in (0.25, 0.75):
        for qy in (0.25, 0.75):
            albero(det, M @ T(W * qx + rr(-0.8, 0.8), D * qy + rr(-0.8, 0.8), 0), rr(0.6, 0.75), 'jacaranda_tree')
            if D > 14 and RNG.random() < 0.7:
                albero(det, M @ T(W * qx + rr(-1.5, 1.5), D * (qy + rr(-0.1, 0.1)) + 3.0, 0), rr(0.8, 1.0), 'island_tree_02')

class Interno:
    """Raccoglie le costruzioni dell'interno in oggetti da 'per_oggetto' elementi, e il lastricato di
    vicoli e cortili in un unico oggetto."""
    def __init__(self, coll, per_oggetto=40, prefisso="Interno", lastricato="Vicoli_e_cortili"):
        self.coll = coll; self.per = per_oggetto; self.n = 0; self.k = 0
        self.prefisso = prefisso; self.lastricato = lastricato
        self.det = nuovo_bm(); self.pav = nuovo_bm()

    def _conta(self):
        self.n += 1
        if self.n % self.per == 0:
            self._blocco()

    def _blocco(self):
        if len(self.det.verts):
            uv_finale(oggetto(f"{self.prefisso}_{self.k:02d}", self.det, MB, self.coll)); self.k += 1
        self.det = nuovo_bm()

    def pavimenta(self, M, x0, y0, x1, y1):
        self.pav.faces.new([self.pav.verts.new((x, y, 0.015)) for (x, y) in rett_mondo(M, x0, y0, x1, y1)])

    def casa(self, W, D, n, M, vicolo=0.0, Z=None):
        casa_semplice(self.det, W, D, n, M, Z)
        if vicolo > 0:   # vicolo davanti e cortiletto fino alle case sulla strada
            self.pavimenta(M, 0, -vicolo - 2.0, W, 0)
        self._conta()

    def rimessa(self, W, D, M):
        rimessa(self.det, W, D, M); self._conta()

    def cortile(self, W, D, M):
        self.pavimenta(M, 0, 0, W, D)
        for _ in range(RNG.randint(0, 3)):
            botte(self.det, rr(0.5, W - 0.5), rr(0.5, 1.2), I['legno_grezzo'], I['ferro'], M)
        for _ in range(RNG.randint(0, 2)):
            sacco(self.det, rr(0.5, W - 0.5), rr(D - 1.2, D - 0.5), I['juta'], M, rr(0, 3))
        if RNG.random() < 0.65:
            albero(self.det, M @ T(rr(0.35, 0.65) * W, rr(0.35, 0.65) * D, 0), 1.0, 'island_tree_02')
        self._conta()

    def tettoia(self, W, prof, M):
        tettoia(self.det, W, prof, M); self._conta()

    def orto(self, W, D, M):
        orto(self.det, W, D, M); self._conta()

    def giardino(self, W, D, M):
        giardino(self.det, W, D, M); self._conta()

    def chiudi(self):
        self._blocco(); self.det.free()
        if len(self.pav.faces):
            uv_finale(oggetto(self.lastricato, self.pav, ['selciato'], self.coll, ricalcola=False))
        else:
            self.pav.free()

def _lotto(p, ang, sx, sy, W, D):
    """Matrice di un lotto W x D con un angolo in p, esteso nel quadrante (sx, sy) del sistema ruotato."""
    e = Vector((math.cos(ang), math.sin(ang))); nn = Vector((-e.y, e.x))
    o = Vector(p) - e * (W if sx < 0 else 0.0) - nn * (D if sy < 0 else 0.0)
    return Matrix.Translation((o.x, o.y, 0.0)) @ RZ(ang)

def _massimo(ok, a, b):
    """Il valore piu' grande in [a, b] per cui ok() e' vero (ok(a) gia' verificato)."""
    if ok(b):
        return b
    while b - a > 0.2:
        c = (a + b) / 2
        if ok(c): a = c
        else: b = c
    return a

def riempi_spazi(inn):
    """Scansione a griglia di 1 m: negli spazi liberi rimasti mette case, cortili, rimesse e orti (secondo
    la zona), allineati all'edificio o alla strada piu' vicini, cosi' gli isolati restano ordinati."""
    segs = [(a, b) for (_, _, P, _) in STRADE for a, b in zip(P, P[1:])]
    segs += [(P[0], P[1]) for (_, P, _) in linee_prima_fila()]
    def dist_seg(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
        return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)
    def angolo(p):
        # prima l'edificio (o strada, o lotto) piu' vicino entro 8 m: le case nuove si allineano ai vicini
        best = None
        for (a0, b0, a1, b1, o) in _vicini(p[0] - 8, p[1] - 8, p[0] + 8, p[1] + 8):
            d = min(dist_seg(p, o[i], o[(i + 1) % len(o)]) for i in range(len(o)))
            if d < 8.0 and (best is None or d < best[0]):
                best = (d, math.atan2(o[1][1] - o[0][1], o[1][0] - o[0][0]) % (math.pi / 2))
        if best:
            return best[1]
        return min((dist_seg(p, a, b), math.atan2(b[1] - a[1], b[0] - a[0]) % (math.pi / 2)) for a, b in segs)[1]
    libero_l = lambda p, ang, sx, sy, W, D: libero(rett_mondo(_lotto(p, ang, sx, sy, W, D), 0.1, 0.1, W - 0.1, D - 0.1))
    xs = [p[0] for p in MURA]; ys = [p[1] for p in MURA]
    y = min(ys) + 0.5
    while y < max(ys):
        x = min(xs) + 0.5
        while x < max(xs):
            p = (x, y); x += 1.0
            if not dentro_mura(p, MARGINE_MURA + 0.2) or occupato(p):
                continue
            zn = zona_di(p); Z = STILI_ZONA.get(zn)
            ang = angolo(p)
            if Z:
                Wt, Dt = rr(Z['larg'][0], Z['larg'][1] + 1.0), rr(6.0, 9.0) if zn != 'borgo' else rr(5.0, 7.0)
            else:
                Wt, Dt = rr(5.5, 8.0), rr(6.0, 9.0)
            scelta = None
            for sx in (1, -1):
                for sy in (1, -1):
                    if not libero_l(p, ang, sx, sy, 3.0, 3.0):
                        continue
                    W = _massimo(lambda w: libero_l(p, ang, sx, sy, w, 3.0), 3.0, Wt)
                    D = _massimo(lambda d: libero_l(p, ang, sx, sy, W, d), 3.0, Dt)
                    if scelta is None or W * D > scelta[0]:
                        scelta = (W * D, sx, sy, W, D)
            if scelta is None:
                continue
            _, sx, sy, W, D = scelta
            M = _lotto(p, ang, sx, sy, W, D)
            grande = min(W, D) >= 4.2 and W * D >= 24
            if Z and min(W, D) >= 4.5 and RNG.random() < Z.get('orti', 0.0):
                inn.orto(W, D, M)
            elif min(W, D) >= 5.5 and RNG.random() < (Z['cortili'] if Z else 0.15):
                inn.cortile(W, D, M)
            elif grande and not (Z and RNG.random() < Z.get('rimesse', 0.0)):
                pi = Z['piani_int'] if Z else (2, 3)
                inn.casa(W, D, 1 if W * D < 30 else RNG.randint(pi[0], pi[1]), M, 0.0, Z)
                # a volte un vicolo lungo il fianco, per spezzare i blocchi troppo compatti
                if RNG.random() < 0.3 and libero(rett_mondo(M, W + 0.1, 0.1, W + 2.3, D - 0.1)):
                    inn.pavimenta(M, W, 0, W + 2.4, D); occupa(rett_mondo(M, W, 0, W + 2.4, D))
            else:
                inn.rimessa(W, D, M)
            occupa(rett_mondo(M, 0, 0, W, D))
        y += 1.0

def isolati(coll):
    """Riempie l'interno degli isolati: prima file di case sul retro lungo vicoli paralleli alle strade
    (alla piazza), poi case, cortili, rimesse e orti negli spazi rimasti. Stili per zona."""
    inn = Interno(coll)
    fronti = [([a, b], 10.0) for (_, P, _) in linee_prima_fila() for a, b in zip(P, P[1:])]
    for (nome, larg, punti, par) in STRADE:
        pm = par.get('prof', (8.0, 10.0))[1]
        for P in (punti, punti[::-1]):
            Q = scosta(P, larg / 2)
            fronti += [([a, b], pm) for a, b in zip(Q, Q[1:])]
    dist = [pm for _, pm in fronti]
    for k in range(FILE_INTERNE):   # una fila alla volta per tutte le strade: ogni isolato cresce da ogni lato
        for i, (seg, pm) in enumerate(fronti):
            v = rr(2.0, 3.0); dist[i] += v
            fila("Interno", scosta(seg, dist[i]), coll, prof=(7.0, 8.5), piani=(2, 3), interno=inn, vicolo=v,
                 per_zona=True)
            dist[i] += 8.5
    n_file = inn.n
    riempi_spazi(inn)
    print("Interno degli isolati:", n_file, "case sul retro,", inn.n - n_file, "case/cortili/rimesse/orti negli spazi")
    inn.chiudi()

# ----------------------------------------------------------------------
#  CONTROLLO DI FINESTRE E PORTE (a scena costruita: le case nascono una dopo l'altra e una casa
#  costruita dopo puo' coprire le finestre di una gia' fatta)
# ----------------------------------------------------------------------
# materiali che chiudono la vista davanti a una finestra: muri, tetti, infissi e imposte di altre case
CHIUDONO = {'pietra_blocchi', 'pietra_muro', 'intonaco_bianco', 'intonaco_giallo', 'intonaco_rosa', 'legno_travi',
            'coppi', 'ardesia', 'paglia', 'vetro', 'assi', 'pietra_cornici', 'imposte_verdi', 'imposte_rosse',
            'imposte_blu', 'mattoni', 'interno_buio', 'pietra_mura', 'coppi_vecchi', 'tavole', 'pietra_chiesa'}

def _scena_muri():
    """Tutte le mesh della scena in coordinate di mondo, con le facce marcate (aperture, muri che chiudono la
    vista, vetri, ante) e un BVH dei soli muri e tetti."""
    obs = [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_render and len(o.data.polygons)]
    verts, polys, ap_l, chiude_l, vetro_l, anta_l, ob_l, base = [], [], [], [], [], [], [], 0
    for oi, o in enumerate(obs):
        me = o.data; nv, npo = len(me.vertices), len(me.polygons)
        co = np.empty(nv * 3, np.float64); me.vertices.foreach_get('co', co)
        Mw = np.array(o.matrix_world)
        verts.append(co.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3])
        ls = np.empty(npo, np.int64); me.polygons.foreach_get('loop_start', ls)
        lt = np.empty(npo, np.int64); me.polygons.foreach_get('loop_total', lt)
        lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', lv); lv += base
        polys += [lv[a:a + b].tolist() for a, b in zip(ls, lt)]
        mi = np.empty(npo, np.int64); me.polygons.foreach_get('material_index', mi)
        mi = np.minimum(mi, max(0, len(o.material_slots) - 1))
        nz = np.empty(npo * 3); me.polygons.foreach_get('normal', nz)
        nomi = [s.material.name if s.material else '' for s in o.material_slots] or ['']
        chiude_l.append(np.array([n in CHIUDONO for n in nomi], bool)[mi] & (np.abs(nz[2::3]) < 0.95))
        vetro_l.append(np.array([n == 'vetro' for n in nomi], bool)[mi])
        anta_l.append(np.array([n in ('assi', 'tavole') or n.startswith('imposte') for n in nomi], bool)[mi]
                      & (np.abs(nz[2::3]) < 0.3))
        a = np.zeros(npo, np.int64)
        if me.attributes.get('apertura'):
            me.attributes['apertura'].data.foreach_get('value', a)
        ap_l.append(a); ob_l.append(np.full(npo, oi))
        base += nv
    V = np.concatenate(verts); A = np.concatenate(ap_l); CH = np.concatenate(chiude_l)
    VE = np.concatenate(vetro_l); AN = np.concatenate(anta_l); OB = np.concatenate(ob_l); inizio = np.cumsum([0] + [len(x) for x in ap_l])
    # i raggi vedono solo muri e tetti (niente aperture: il davanzale ha il retro sul piano del muro)
    bvh = BVHTree.FromPolygons(V.tolist(), [polys[i] for i in np.nonzero(CH & (A == 0))[0]],
                               all_triangles=False, epsilon=0.0)

    return obs, V, polys, A, CH, VE, AN, OB, inizio, bvh

BVH_MURI = [None]   # BVH dei muri dell'ultimo controllo, se dopo non e' cambiato nulla (lo riusa riapri_facciate)

def controlla_aperture(togli=True, davanti=0.6):
    """Ogni finestra o porta marcata con segna_apertura() deve avere il muro dietro a tutta la sua sagoma
    (imposte e davanzale compresi: niente finestre oltre lo spigolo o sospese) e almeno 'davanti' m liberi
    davanti al vetro (niente finestre contro un'altra casa). Quelle che non passano si tolgono; se l'apertura
    era scavata col booleano il foro si richiude con un tassello di muro. Restituisce l'elenco delle sbagliate:
    (tipo, motivo, oggetto, centro, verso esterno, distanza dell'ostacolo, numero dell'apertura)."""
    obs, V, polys, A, CH, VE, AN, OB, inizio, bvh = _scena_muri()

    def primo(o, d, dist, mia):
        """Distanza del primo muro o tetto lungo il raggio, o None."""
        return bvh.ray_cast(o, d, dist)[3]

    gruppi = {}
    for i in np.nonzero(A)[0]:
        gruppi.setdefault(int(A[i]), []).append(int(i))
    sbagliate = []; per_oggetto = {}
    for k, idx in gruppi.items():
        tipo, fuori_loc, tassello = APERTURE[k - 1][:3]
        oi = int(OB[idx[0]]); o = obs[oi]
        n = (o.matrix_world.to_3x3() @ fuori_loc); n.z = 0; n.normalize()
        t = Vector((-n.y, n.x, 0))
        def sagoma(ii):
            P = np.array([V[v] for i in ii for v in polys[i]])
            s_, z_ = P @ np.array(t), P[:, 2]
            return (s_.min() + s_.max()) / 2, (z_.min() + z_.max()) / 2, (s_.max() - s_.min()) / 2,                    (z_.max() - z_.min()) / 2, P @ np.array(n)
        cs, cz, hs, hz, d_ = sagoma(idx)
        fronte = d_.max() + 0.01
        punto = lambda s, z, d: t * s + Vector((0, 0, z)) + n * d
        # pannello: il vetro della finestra o l'anta della porta
        vv = [i for i in idx if (VE[i] if tipo == 'finestra' else AN[i])]
        vs, vz, vhs, vhz, vd = sagoma(vv) if vv else (cs, cz, hs, hz, d_)
        INFO_AP[k] = (o.name, punto(cs, cz, d_.max()), n.copy(), cz, hz, hs)
        motivo = None
        # 1) muro dietro a tutta la sagoma (angoli rientrati di 4 cm). Il raggio parte 30 cm davanti: le ante
        #    incassate stanno dentro il foro e negli angoli di un arco si partirebbe dentro il muro pieno.
        #    Un angolo che cade sul pannello e' retto dall'apertura stessa (il frontone e' forato da parte a parte)
        for fs in (-1, 1):
            for fz in (-1, 1):
                s0, z0 = cs + fs * (hs - 0.04), cz + fz * (hz - 0.04)
                if vv and abs(s0 - vs) < vhs + 0.02 and abs(z0 - vz) < vhz + 0.02:
                    continue
                if primo(punto(s0, z0, fronte + 0.3), -n, fronte + 0.3 - d_.min() + 0.5, k) is None:
                    motivo = 'fuori dal muro'
        # 2) spazio libero davanti al pannello, centro e verso gli angoli
        if motivo is None:
            for (fs, fz) in ((0, 0), (-0.35, -0.35), (0.35, -0.35), (-0.35, 0.35), (0.35, 0.35)):
                dist = primo(punto(vs + fs * vhs, vz + fz * vhz, vd.max() + 0.003), n, davanti, k)
                if dist is not None:
                    motivo = 'contro un muro'; break
        if motivo:
            sbagliate.append((tipo, motivo, o.name, punto(cs, cz, fronte), n, dist if motivo == 'contro un muro' else None, k))
            per_oggetto.setdefault(oi, []).append((k, [i - inizio[oi] for i in idx], tassello))
    if togli:
        for oi, lista in per_oggetto.items():
            o = obs[oi]; bm = bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table()
            via = [bm.faces[i] for (_, ii, _) in lista for i in ii]
            for (_, _, tas) in lista:
                if tas:   # foro scavato: tassello di muro dal filo della facciata al fondo del foro
                    pts, y0, y1, ax, mi, Mt = tas
                    prism(bm, pts, y0, y1, mi, ax, Mt if Mt is not None else Matrix.Identity(4))
            bmesh.ops.delete(bm, geom=via, context='FACES')
            bm.to_mesh(o.data); bm.free()
            if any(tas for (_, _, tas) in lista):
                uv_finale(o)
    BVH_MURI[0] = None if sbagliate and togli else bvh
    return sbagliate

def riapri_facciate(tolte, passo=0.2, interasse=1.8):
    """Facciate che hanno perso tutte le aperture (tolte = numeri delle aperture tolte): dove guardano (via o
    piazza = davanti c'e' il selciato; vicolo o cortile; altro). Su quelle che danno su una via, una piazza, un
    vicolo o un cortile rimette finestre (come quelle delle case interne, senza booleano) dove il muro e' pieno dietro a tutta la
    cornice e ci sono 0,6 m liberi davanti. Restituisce (elenco delle facciate cieche, finestre aggiunte)."""
    bvh = None   # BVH dei muri: si costruisce solo se c'e' davvero una facciata da riaprire
    sc = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get()
    facciate = {}
    for k, ap in enumerate(APERTURE, 1):
        facciate.setdefault(ap[3], []).append(k)
    cieche = []; nuove = {}; aggiunte = 0
    for chiave, ks in facciate.items():
        if not all(k in tolte for k in ks):
            continue
        info = [INFO_AP[k] for k in ks if k in INFO_AP]
        if not info:
            continue
        nome, n = info[0][0], info[0][2]
        t = Vector((-n.y, n.x, 0))
        c = sum((i[1] for i in info), Vector()) / len(info)
        p = c + n * 2.5
        hit, loc, _, _, ob, _ = sc.ray_cast(dg, Vector((p.x, p.y, 1.0)), Vector((0, 0, -1)))
        davanti_muro = sc.ray_cast(dg, Vector((c.x, c.y, 1.5)) + n * 0.3, n, distance=2.2)[0]
        if hit and ob.name.startswith('Selciato') and not davanti_muro:
            luogo = 'via o piazza'
        elif hit and ob.name.startswith(('Vicoli', 'Lastricati')):   # anche se al piano terra c'e' un vicino
            luogo = 'vicolo o cortile'
        else:
            luogo = 'altro'
        posti = []
        if luogo in ('via o piazza', 'vicolo o cortile'):
            if bvh is None:
                bvh = BVH_MURI[0] or _scena_muri()[-1]
            dws = [h[0].dot(n) for h in (bvh.ray_cast(i[1] + n * 0.6, -n, 1.5) for i in info) if h[0] is not None]
            if dws:
                dw = sorted(dws)[len(dws) // 2]
                P = lambda s_, z_, d_: t * s_ + Vector((0, 0, z_)) + n * d_
                ss = [i[1].dot(t) for i in info]
                rimaste = [(i[1], i[5]) for k2, i in INFO_AP.items() if k2 not in tolte
                           and i[2].dot(n) > 0.9 and abs(i[1].dot(n) - dw) < 0.6]
                def libera(s0, zA, zB, w):
                    """Profondita' del muro dove la finestra ci sta, o None. La profondita' si misura sul posto:
                    nelle case a graticcio ogni piano sporge di 32 cm su quello sotto."""
                    h = bvh.ray_cast(P(s0, (zA + zB) / 2, dw + 1.2), -n, 2.4)[0]
                    if h is None:
                        return None
                    d = h.dot(n)
                    for (fs, z_) in ((-1, zA - 0.08), (1, zA - 0.08), (-1, zB + 0.13), (1, zB + 0.13)):
                        h = bvh.ray_cast(P(s0 + fs * (w / 2 + 0.11), z_, d + 0.3), -n, 0.45)
                        if h[0] is None or abs(h[0].dot(n) - d) > 0.06:
                            return None
                    for (fs, fz) in ((0, 0.5), (-0.35, 0.2), (0.35, 0.2), (-0.35, 0.8), (0.35, 0.8)):
                        if bvh.ray_cast(P(s0 + fs * w, zA + fz * (zB - zA), d + 0.18), n, 0.6)[0] is not None:
                            return None
                    # cielo libero davanti alla finestra, alla sua altezza: non dentro una casa vicina addossata
                    # (nei vicoli interni le case sono spesso a contatto) e non sotto il tetto di un'altra costruzione
                    for fs in (-0.5, 0.5):
                        if sc.ray_cast(dg, P(s0 + fs * w, zA - 0.1, d + 0.7), Vector((0, 0, 1)), distance=40.0)[0]:
                            return None
                    if all(abs(c2.dot(t) - s0) > w / 2 + hs2 + 0.4 or abs(c2.z - (zA + zB) / 2) > 1.2
                           for (c2, hs2) in rimaste):
                        return d
                for cz in sorted({round(i[3], 1) for i in info}):
                    zA, zB = (1.1, 2.0) if cz < 3.0 else (cz - 0.55, cz + 0.6)
                    w = 0.7 if cz < 3.0 else 0.75
                    s0 = min(ss) - 1.5; riga = []
                    while s0 <= max(ss) + 1.5:
                        if all(abs(s0 - q[0]) >= interasse for q in riga):
                            d = libera(s0, zA, zB, w)
                            if d is not None:
                                riga.append((s0, d))
                        s0 += passo
                    posti += [(q, zA, zB, w, d) for (q, d) in riga]
                if posti:
                    bm = nuove.setdefault(nome, nuovo_bm())
                    try:
                        for (q, zA, zB, w, d) in posti:
                            CM[0] = Matrix(((t.x, -n.x, 0, n.x * d), (t.y, -n.y, 0, n.y * d), (0, 0, 1, 0), (0, 0, 0, 1)))
                            finestra_finta(bm, q, w, zA, zB, None, 'pietra')
                    finally:
                        CM[0] = None
                    aggiunte += len(posti)
        cieche.append((nome, luogo, c, n, len(posti)))
    for nome, bm in nuove.items():   # le finestre nuove entrano nell'oggetto della casa
        ob = bpy.data.objects[nome]
        bm.transform(ob.matrix_world.inverted())
        tmp = oggetto("_finestre_riaperte", bm, MB, ob.users_collection[0])
        tmp.matrix_world = ob.matrix_world
        uv_finale(tmp)
        unisci([ob, tmp], nome)
    return cieche, aggiunte

# ----------------------------------------------------------------------
#  PALAZZO COMUNALE E TORRE
# ----------------------------------------------------------------------
def piramide(det, x0, y0, x1, y1, z, h, mi):
    a = [det.verts.new(p) for p in [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]]
    ap = det.verts.new(((x0 + x1) / 2, (y0 + y1) / 2, z + h))
    det.faces.new(a[::-1]).material_index = mi
    for i in range(4):
        det.faces.new((a[i], a[(i + 1) % 4], ap)).material_index = mi
    return Vector(((x0 + x1) / 2, (y0 + y1) / 2, z + h))

def campana(det, cx, cy, ztop):
    prof = [(0.06, ztop), (0.3, ztop - 0.05), (0.4, ztop - 0.5), (0.48, ztop - 0.95),
            (0.62, ztop - 1.15), (0.6, ztop - 1.2)]
    lathe(det, [(r, z) for r, z in prof], 20, I['bronzo'], T(cx, cy, 0))

def stendardo(det, xb, yb, ztop, larg=1.0, alt=3.0, onda=0.05):
    box(det, (xb - larg / 2 - 0.15, yb - 0.05, ztop), (xb + larg / 2 + 0.15, yb + 0.05, ztop + 0.08), I['ferro'])
    nu, nv = 6, 12
    grid = []
    for i in range(nu + 1):
        u = i / nu; x = xb - larg / 2 + larg * u; col = []
        for jv in range(nv + 1):
            v = jv / nv
            z = ztop - alt * v
            if jv == nv:
                z = ztop - alt + 0.35 * (1 - abs(2 * u - 1))
            y = yb - onda * math.sin(math.pi * 2 * v + u * 2)
            col.append(det.verts.new((x, y, z)))
        grid.append(col)
    for i in range(nu):
        for jv in range(nv):
            f = det.faces.new((grid[i][jv], grid[i + 1][jv], grid[i + 1][jv + 1], grid[i][jv + 1]))
            f.material_index = I['stendardo']; f.smooth = True

def finestre_laterali_palazzo(det, tg, W, D, z0, k, pb):
    for lato in ('sx', 'dx'):
        CM[0] = (RZ(-math.pi / 2) @ T(-D, 0, 0)) if lato == 'sx' else (T(W, 0, 0) @ RZ(math.pi / 2))
        try:
            for i in range(3):
                xc = D * (i + 0.5) / 3
                apertura(det, tg, ('finestra', xc, 1.0, 0.95, 2.45), z0, 0.0, -1, k, 'pietra', 'assi', pb)
        finally:
            CM[0] = None

def palazzo(M, coll):
    W, D = 16.0, 11.0; hg, hf = 4.6, 3.4
    pb, pc = I['pietra_blocchi'], I['pietra_cornici']
    det = nuovo_bm(); parti = []
    # piano terra: loggia ad archi
    tg = []; na = 4; span = W / na
    for i in range(na):
        xc = span * (i + 0.5); w = span - 1.1
        tg.append((arco_pts(xc - w / 2, xc + w / 2, -0.2, 3.9), -0.4, 3.6, 'y', pb))
        if i in (1, 2):
            prism(det, arco_pts(xc - 0.7, xc + 0.7, 0.0, 2.8), 3.52, 3.6, I['assi'])
            box(det, (xc - 0.9, 3.45, 2.8), (xc + 0.9, 3.6, 3.0), pc)
        else:
            prism(det, arco_pts(xc - 0.45, xc + 0.45, 1.2, 2.6), 3.56, 3.6, I['vetro'])
    for i in range(na + 1):
        x = span * i
        box(det, (max(-0.05, x - 0.62), -0.08, 0), (min(W + 0.05, x + 0.62), 0.0, 0.35), pc)
        box(det, (max(-0.05, x - 0.62), -0.1, 2.75), (min(W + 0.05, x + 0.62), 0.0, 2.95), pc)
    parti.append(guscio("Palazzo_p0", lambda bm: box(bm, (0, 0, 0), (W, D, hg), pb), tg, coll))
    box(det, (-0.1, -0.15, hg - 0.25), (W + 0.1, 0.05, hg + 0.05), pc)
    # primo piano: bifore
    tg = []; nb = 5; z0 = hg
    for i in range(nb):
        xc = W * (i + 0.5) / nb; w = 1.3
        apertura(det, tg, ('finestra', xc, w, 0.95, 2.75), z0, 0.0, -1, 1, 'pietra', 'assi', pb)
        lathe(det, [(0.07, z0 + 0.95), (0.06, z0 + 2.1), (0.1, z0 + 2.15)], 10, pc, T(xc, 0.1, 0))
        apertura(det, tg, ('finestra', xc, 1.0, 0.95, 2.4), z0, D, 1, 1, 'pietra', 'assi', pb)
    finestre_laterali_palazzo(det, tg, W, D, z0, 1, pb)
    parti.append(guscio("Palazzo_p1", lambda bm: box(bm, (0, 0, z0), (W, D, z0 + hf), pb), tg, coll))
    box(det, (-0.1, -0.15, z0 + hf - 0.1), (W + 0.1, 0.05, z0 + hf + 0.12), pc)
    # secondo piano
    tg = []; z1 = hg + hf
    for i in range(nb):
        xc = W * (i + 0.5) / nb
        apertura(det, tg, ('finestra', xc, 1.0, 0.9, 2.5), z1, 0.0, -1, 2, 'intonaco', 'imposte_verdi', pb)
        apertura(det, tg, ('finestra', xc, 1.0, 0.9, 2.4), z1, D, 1, 2, 'pietra', 'assi', pb)
    finestre_laterali_palazzo(det, tg, W, D, z1, 2, pb)
    parti.append(guscio("Palazzo_p2", lambda bm: box(bm, (0, 0, z1), (W, D, z1 + hf), pb), tg, coll))
    zt = hg + 2 * hf
    # beccatelli, parapetto e merli
    x = 0.3
    while x < W - 0.2:
        box(det, (x - 0.12, -0.4, zt - 0.45), (x + 0.12, 0.02, zt), pc); x += 0.6
    for (a, b) in [((-0.4, -0.4), (W + 0.4, 0.15)), ((-0.4, D - 0.15), (W + 0.4, D + 0.4)),
                   ((-0.4, -0.4), (0.15, D + 0.4)), ((W - 0.15, -0.4), (W + 0.4, D + 0.4))]:
        box(det, (a[0], a[1], zt), (b[0], b[1], zt + 0.6), pb)
    # tetto a padiglione in coppi dietro i merli
    zb = zt + 0.05; a0, a1, b0, b1 = 0.15, W - 0.15, 0.15, D - 0.15
    hd = (b1 - b0) / 2; hr = hd * math.tan(math.radians(24)); ym = (b0 + b1) / 2
    vb = [det.verts.new(p) for p in [(a0, b0, zb), (a1, b0, zb), (a1, b1, zb), (a0, b1, zb)]]
    r0 = det.verts.new((a0 + hd, ym, zb + hr)); r1 = det.verts.new((a1 - hd, ym, zb + hr))
    for fv in [(vb[0], vb[1], r1, r0), (vb[2], vb[3], r0, r1), (vb[1], vb[2], r1), (vb[3], vb[0], r0),
               (vb[3], vb[2], vb[1], vb[0])]:
        det.faces.new(fv).material_index = I['coppi']
    x = -0.4
    while x < W + 0.3:
        x0, x1 = x, min(x + 0.6, W + 0.4)
        prism(det, [(x0, zt + 0.6), (x1, zt + 0.6), (x1, zt + 1.6), ((x0 + x1) / 2, zt + 1.25), (x0, zt + 1.6)],
              -0.4, 0.15, pb, 'y')
        x += 1.1
    # torretta campanaria
    tx0, tx1, ty0, ty1 = W / 2 - 1.5, W / 2 + 1.5, D - 4.5, D - 1.5
    tg = [(arco_pts(W / 2 - 0.7, W / 2 + 0.7, zt + 2.2, zt + 4.0), ty0 - 0.5, ty1 + 0.5, 'y', I['mattoni']),
          (arco_pts(ty0 + 0.8, ty1 - 0.8, zt + 2.2, zt + 4.0), tx0 - 0.5, tx1 + 0.5, 'x', I['mattoni'])]
    parti.append(guscio("Palazzo_torretta", lambda bm: box(bm, (tx0, ty0, zt), (tx1, ty1, zt + 4.6), I['mattoni']), tg, coll))
    campana(det, W / 2, (ty0 + ty1) / 2, zt + 3.9)
    box(det, (tx0 - 0.2, ty0 - 0.2, zt + 4.6), (tx1 + 0.2, ty1 + 0.2, zt + 4.85), pc)
    ap = piramide(det, tx0 - 0.3, ty0 - 0.3, tx1 + 0.3, ty1 + 0.3, zt + 4.85, 2.6, I['ardesia'])
    lathe(det, [(0.03, ap.z - 0.2), (0.03, ap.z + 2.2)], 8, I['ferro'], T(ap.x, ap.y, 0))
    sfera(det, (ap.x, ap.y, ap.z + 0.5), 0.12, I['ferro'])
    stendardo(det, ap.x + 0.6, ap.y, ap.z + 2.15, larg=1.1, alt=0.7, onda=0.12)
    # stendardi in facciata
    for xb in (W * 0.4, W * 0.6):
        stendardo(det, xb, -0.55, zt - 0.75, larg=0.95, alt=3.4)
        box(det, (xb - 0.04, -0.55, zt - 0.75), (xb + 0.04, 0.0, zt - 0.67), I['ferro'])
    parti.append(oggetto("Palazzo_det", det, MB, coll))
    ob = unisci(parti, "Palazzo_Comunale")
    uv_finale(ob); ob.matrix_world = M; smussa(ob)
    occupa(rett_mondo(M, 0, 0, W, D))
    return ob

def torre(M, coll, pietra='pietra_chiesa'):
    S, H, hb = 6.0, 24.0, 5.2
    pb = pc = I[pietra]   # campanile: stessa pietra della chiesa
    det = nuovo_bm(); parti = []
    tg = []
    for z in (6.0, 11.5, 17.0):
        p = rett(S / 2 - 0.16, S / 2 + 0.16, z, z + 1.2)
        tg += [(p, -0.3, 0.5, 'y', pb), (p, S - 0.5, S + 0.3, 'y', pb),
               (p, -0.3, 0.5, 'x', pb), (p, S - 0.5, S + 0.3, 'x', pb)]
        box(det, (S / 2 - 0.2, 0.44, z - 0.05), (S / 2 + 0.2, 0.48, z + 1.25), I['interno_buio'])
    tg.append((arco_pts(S / 2 - 0.7, S / 2 + 0.7, -0.2, 2.7), -0.3, 0.45, 'y', pb))
    prism(det, arco_pts(S / 2 - 0.7, S / 2 + 0.7, 0.0, 2.7), 0.3, 0.38, I['assi'])
    parti.append(guscio("Torre_fusto", lambda bm: box(bm, (0, 0, 0), (S, S, H), pb), tg, coll))
    for (cx, cy) in ((0, 0), (S - 0.55, 0), (0, S - 0.55), (S - 0.55, S - 0.55)):
        box(det, (cx - 0.08 if cx == 0 else cx, cy - 0.08 if cy == 0 else cy, 0),
            (cx + 0.55 if cx == 0 else S + 0.08, cy + 0.55 if cy == 0 else S + 0.08, H), pb)
    box(det, (-0.25, -0.25, H - 0.3), (S + 0.25, S + 0.25, H + 0.15), pc)
    tg = [(arco_pts(S / 2 - 1.3, S / 2 + 1.3, H + 0.9, H + 4.4), -0.5, S + 0.5, 'y', pb),
          (arco_pts(S / 2 - 1.3, S / 2 + 1.3, H + 0.9, H + 4.4), -0.5, S + 0.5, 'x', pb)]
    parti.append(guscio("Torre_cella", lambda bm: box(bm, (0, 0, H), (S, S, H + hb), pb), tg, coll))
    campana(det, S / 2, S / 2, H + 4.1)
    box(det, (0.2, S / 2 - 0.12, H + 4.1), (S - 0.2, S / 2 + 0.12, H + 4.3), I['legno_travi'])
    box(det, (-0.3, -0.3, H + hb), (S + 0.3, S + 0.3, H + hb + 0.35), pc)
    ap = piramide(det, -0.35, -0.35, S + 0.35, S + 0.35, H + hb + 0.35, 6.5, I['ardesia'])
    lathe(det, [(0.04, ap.z - 0.3), (0.04, ap.z + 1.8)], 8, I['ferro'], T(ap.x, ap.y, 0))
    sfera(det, (ap.x, ap.y, ap.z + 0.9), 0.14, I['ferro'])
    # orologio
    zc = H - 2.4
    Mc = T(S / 2, 0.0, zc) @ RX(math.radians(90))
    lathe(det, [(1.15, -0.02), (1.15, 0.1)], 32, pc, Mc, liscio=False)
    lathe(det, [(0.97, 0.1), (0.97, 0.13)], 32, I['intonaco_bianco'], Mc, liscio=False)
    for h12 in range(12):
        a = 2 * math.pi * h12 / 12
        box(det, (S / 2 + 0.82 * math.sin(a) - 0.035, -0.17, zc + 0.82 * math.cos(a) - 0.06),
            (S / 2 + 0.82 * math.sin(a) + 0.035, -0.13, zc + 0.82 * math.cos(a) + 0.06), I['ferro'])
    box(det, (S / 2 - 0.03, -0.2, zc - 0.05), (S / 2 + 0.03, -0.16, zc + 0.72), I['ferro'])
    prism(det, [(S / 2, zc - 0.04), (S / 2 + 0.5, zc + 0.25), (S / 2 + 0.47, zc + 0.3), (S / 2 - 0.03, zc + 0.01)],
          -0.21, -0.17, I['ferro'], 'y')
    parti.append(oggetto("Torre_det", det, MB, coll))
    ob = unisci(parti, "Torre_Campanaria")
    uv_finale(ob); ob.matrix_world = M; smussa(ob)
    occupa(rett_mondo(M, 0, 0, S, S))
    return ob

# ----------------------------------------------------------------------
#  EDIFICI DELLE ZONE: CHIESA, TORRE DEI NOBILI, PALAZZETTO
# ----------------------------------------------------------------------
def cornice_sagomata(det, x0, x1, y, z, verso, mi, sporto=0.4, alto=0.45, M=None):
    """Cornice in rilievo a tre gradoni (listello, gola, gocciolatoio) lungo x sulla faccia y;
    verso = -1 se la faccia guarda verso -y."""
    for (a, b, s) in ((0.0, 0.27, 0.3), (0.27, 0.55, 0.62), (0.55, 1.0, 1.0)):
        y1 = y + verso * sporto * s
        box(det, (x0 - sporto * s, min(y, y1), z + alto * a), (x1 + sporto * s, max(y, y1), z + alto * b), mi, M)

def lesena(det, x, y, z1, verso, mi, larg=0.7, sp=0.25, M=None):
    """Lesena in rilievo con zoccolo e capitello, sulla faccia y (verso = -1 verso -y)."""
    for (za, zb, dl, ds) in ((0.0, 0.7, 0.14, 0.12), (0.7, z1 - 0.45, 0.0, 0.0), (z1 - 0.45, z1, 0.12, 0.1)):
        y1 = y + verso * (sp + ds)
        box(det, (x - larg / 2 - dl, min(y, y1), za), (x + larg / 2 + dl, max(y, y1), zb), mi, M)

def chiesa(M, coll):
    """Chiesa di San Michele in arenaria a conci grandi: facciata a capanna con lesene e cornici in rilievo,
    rosone e portale strombato; fianchi con monofore, lesene e archetti pensili; abside semicircolare;
    tetto a capanna in coppi. Facciata a y=0 verso -y (il sagrato)."""
    B, L, H, F = 6.5, 24.0, 11.0, 7.0      # mezza larghezza navata, lunghezza, altezza, mezza facciata
    pend = math.atan(4.5 / B)
    pb = pc = I['pietra_chiesa']; fe = I['ferro']
    det = nuovo_bm(); parti = []
    zf = H + 0.3 + F * math.tan(pend)       # colmo della facciata (piu' alto del tetto: la nasconde)
    zro, rro = 11.9, 1.6                    # rosone
    cerchio = [(rro * math.cos(2 * math.pi * i / 32), zro + rro * math.sin(2 * math.pi * i / 32)) for i in range(32)]
    portale = arco_pts(-1.4, 1.4, -0.3, 5.2)
    tg = [(portale, -0.9, 0.95, 'y', pc), (cerchio, -0.9, 0.7, 'y', pc)]
    parti.append(guscio("Chiesa_facciata", lambda bm: prism(bm, [(-F, 0), (F, 0), (F, H + 0.3), (0, zf), (-F, H + 0.3)],
                                                             -0.5, 0.25, pb, 'y'), tg, coll))
    # navata con monofore sui fianchi
    tg = [(portale, -0.9, 0.95, 'y', pb), (cerchio, -0.9, 0.7, 'y', pb)]
    finestre = [4.0 + 4.5 * i for i in range(5)]
    for yc in finestre:
        a = arco_pts(yc - 0.45, yc + 0.45, 5.8, 9.4)
        tg += [(a, -B - 0.5, -B + 0.6, 'x', pb), (a, B - 0.6, B + 0.5, 'x', pb)]
        for xg in (-B + 0.55, B - 0.57):
            prism(det, arco_pts(yc - 0.45, yc + 0.45, 5.8, 9.4), xg, xg + 0.02, I['vetro'], 'x')
        for sx in (-1, 1):   # davanzale e ghiera della monofora, in rilievo
            x0, x1 = sorted((sx * B, sx * (B + 0.14)))
            box(det, (x0, yc - 0.65, 5.6), (x1, yc + 0.65, 5.8), pc)
            for i in range(8):
                a0, a1 = math.pi * i / 8, math.pi * (i + 1) / 8
                prism(det, [(yc + 0.45 * math.cos(a0), 9.0 + 0.45 * math.sin(a0)), (yc + 0.68 * math.cos(a0), 9.0 + 0.68 * math.sin(a0)),
                            (yc + 0.68 * math.cos(a1), 9.0 + 0.68 * math.sin(a1)), (yc + 0.45 * math.cos(a1), 9.0 + 0.45 * math.sin(a1))],
                      x0, x1, pc, 'x')
    parti.append(guscio("Chiesa_navata", lambda bm: box(bm, (-B, 0.2, 0), (B, L, H), pb), tg, coll))
    # facciata: zoccolo, lesene con base e capitello, cornice marcapiano e cornici rampanti a due ordini, croce
    cornice_sagomata(det, -F, F, -0.5, 0.0, -1, pc, sporto=0.25, alto=0.6)
    for x in (-F + 0.35, -3.2, 3.2, F - 0.35):
        lesena(det, x, -0.5, 9.3, -1, pc)
    cornice_sagomata(det, -F - 0.1, F + 0.1, -0.5, 9.25, -1, pc, sporto=0.45, alto=0.5)
    for s in (-1, 1):
        prism(det, [(s * (F + 0.15), H + 0.15), (0, zf - 0.05), (0, zf + 0.3), (s * (F + 0.15), H + 0.5)], -0.75, -0.4, pc, 'y')
        prism(det, [(s * (F + 0.3), H + 0.4), (0, zf + 0.2), (0, zf + 0.5), (s * (F + 0.3), H + 0.7)], -0.95, -0.4, pc, 'y')
        for i in range(10):   # archetti pensili sotto la cornice rampante
            t0 = (i + 0.5) / 10.5
            xa = s * (F - 0.4) * (1 - t0); za = H + 0.3 + (F - 0.4) * t0 * math.tan(pend) - 0.15
            box(det, (xa - 0.08, -0.62, za - 0.45), (xa + 0.08, -0.5, za), pc)
    box(det, (-0.07, -0.65, zf + 0.45), (0.07, -0.5, zf + 1.8), fe)
    box(det, (-0.42, -0.65, zf + 1.25), (0.42, -0.5, zf + 1.38), fe)
    # portale strombato: tre ghiere a gradoni, battenti, gradini
    for k in range(3):
        ghiera(det, 1.4 + 0.3 * k, 5.2 + 0.3 * k, -0.5 - 0.1 * k, -1, 0.3, pc)
    prism(det, portale, 0.85, 0.95, I['assi'], 'y')
    for z in (1.0, 2.6, 4.0):
        box(det, (-1.35, 0.8, z), (1.35, 0.85, z + 0.08), fe)
    box(det, (-0.03, 0.8, 0.0), (0.03, 0.85, 5.0), I['legno_travi'])
    for i in range(3):
        box(det, (-3.0 + 0.3 * i, -1.8 + 0.4 * i, 0.0), (3.0 - 0.3 * i, -0.5, 0.16 * (i + 1)), pc)
    # rosone: vetro, ghiera a due anelli, mozzo, raggi e anello intermedio
    Mr = lambda y: T(0, y, zro) @ RX(math.radians(90))
    lathe(det, [(rro, 0.0), (rro, 0.02)], 32, I['vetro'], Mr(0.55))
    lathe(det, [(rro, 0.0), (rro + 0.3, 0.0), (rro + 0.3, 0.16), (rro, 0.16)], 32, pc, Mr(-0.5), chiuso=True)
    lathe(det, [(rro + 0.3, 0.0), (rro + 0.55, 0.0), (rro + 0.55, 0.3), (rro + 0.3, 0.3)], 32, pc, Mr(-0.5), chiuso=True)
    lathe(det, [(0.4, -0.06), (0.55, -0.06), (0.55, 0.06), (0.4, 0.06)], 20, pc, Mr(0.0), chiuso=True)
    for i in range(12):
        box(det, (0.5, -0.06, -0.05), (rro + 0.05, 0.06, 0.05), pc, T(0, 0.0, zro) @ RY(2 * math.pi * i / 12))
    lathe(det, [(rro * 0.72, -0.05), (rro * 0.78, -0.05), (rro * 0.78, 0.05), (rro * 0.72, 0.05)], 28, pc, Mr(0.0),
          chiuso=True)
    # fianchi: zoccolo, lesene, archetti pensili e cornice di gronda a gradoni
    for sx in (-1, 1):
        Mf = T(sx * B, 0, 0) @ RZ(sx * math.pi / 2)    # -y locale verso l'esterno del fianco
        xl = lambda y, sx=sx: y if sx > 0 else -y      # ascissa locale del punto y della navata
        x0, x1 = sorted((xl(0.25), xl(L)))
        cornice_sagomata(det, x0, x1, 0.0, 0.0, -1, pc, sporto=0.22, alto=0.55, M=Mf)
        for yc in [2.0] + [y + 2.25 for y in finestre[:-1]] + [L - 0.3]:
            lesena(det, xl(yc), 0.0, H - 0.75, -1, pc, larg=0.6, sp=0.22, M=Mf)
        y = 0.7
        while y < L - 0.5:   # archetti pensili
            xc = xl(y + 0.4); zs = H - 1.05
            for i in range(6):
                a0, a1 = math.pi * i / 6, math.pi * (i + 1) / 6
                prism(det, [(xc + 0.3 * math.cos(a0), zs + 0.3 * math.sin(a0)), (xc + 0.4 * math.cos(a0), zs + 0.4 * math.sin(a0)),
                            (xc + 0.4 * math.cos(a1), zs + 0.4 * math.sin(a1)), (xc + 0.3 * math.cos(a1), zs + 0.3 * math.sin(a1))],
                      -0.14, 0.0, pc, 'y', Mf)
            box(det, (xl(y) - 0.06, -0.14, zs - 0.25), (xl(y) + 0.06, 0.0, zs + 0.05), pc, Mf)
            y += 0.8
        cornice_sagomata(det, x0, x1, 0.0, H - 0.6, -1, pc, sporto=0.4, alto=0.6, M=Mf)
    # tetto a capanna (dietro la facciata) e timpano posteriore
    CM[0] = T(-B, 0, 0)
    try:
        zr = tetto_fronte(det, 2 * B, 0.85, L, H, pend, 'coppi', False)
        prism(det, [(0, H), (2 * B, H), (B, zr)], L - 0.3, L, pb, 'y')
    finally:
        CM[0] = None
    # abside semicircolare con lesene, monofore, cornice a gradoni e tetto a cono
    Ma = T(0, L, 0)
    lathe(det, [(5.0, 0.0), (5.0, 8.0)], 32, pb, Ma)
    for (r, z0, z1) in ((5.22, 0.0, 0.5), (5.15, 7.4, 7.6), (5.3, 7.6, 7.8), (5.45, 7.8, 8.05)):
        lathe(det, [(5.0, z0), (r, z0), (r, z1), (5.0, z1)], 32, pc, Ma, chiuso=True)
    for a in (20, 55, 90, 125, 160):
        box(det, (4.95, -0.28, 0.5), (5.2, 0.28, 7.4), pc, Ma @ RZ(math.radians(a)))
    lathe(det, [(5.55, 8.0), (0.3, 11.4)], 32, I['coppi'], Ma, cap0=False, liscio=False)
    for a in (72, 108):
        box(det, (4.97, -0.22, 3.6), (5.04, 0.22, 6.2), I['vetro'], Ma @ RZ(math.radians(a)))
    parti.append(oggetto("Chiesa_det", det, MB, coll))
    ob = unisci(parti, "Chiesa_San_Michele")
    uv_finale(ob); ob.matrix_world = M; smussa(ob)
    return ob

def torre_nobili(M, coll):
    """Torre gentilizia alta e stretta: buche pontaie, poche finestre ad arco, porta rialzata, merli."""
    S, H = 5.8, 27.0
    pb = I['pietra_blocchi']
    det = nuovo_bm(); tg = []
    for z in (9.0, 15.0, 21.0):
        a = arco_pts(S / 2 - 0.4, S / 2 + 0.4, z, z + 1.6)
        tg += [(a, -0.3, 0.5, 'y', pb), (a, S - 0.5, S + 0.3, 'y', pb), (a, -0.3, 0.5, 'x', pb), (a, S - 0.5, S + 0.3, 'x', pb)]
    porta_r = arco_pts(S / 2 - 0.55, S / 2 + 0.55, 3.2, 5.6)   # porta rialzata, con scala di legno
    tg.append((porta_r, S - 0.5, S + 0.3, 'y', pb))
    corpo = guscio("Torre_Nobili_corpo", lambda bm: box(bm, (0, 0, 0), (S, S, H), pb), tg, coll)
    for z in (9.0, 15.0, 21.0):   # vetri sui quattro lati
        a = arco_pts(S / 2 - 0.4, S / 2 + 0.4, z, z + 1.6)
        prism(det, a, 0.45, 0.47, I['vetro'], 'y'); prism(det, a, S - 0.47, S - 0.45, I['vetro'], 'y')
        prism(det, a, 0.45, 0.47, I['vetro'], 'x'); prism(det, a, S - 0.47, S - 0.45, I['vetro'], 'x')
    prism(det, porta_r, S - 0.46, S - 0.42, I['assi'], 'y')
    for i in range(9):   # scala di legno verso la porta rialzata
        box(det, (S / 2 - 0.6, S + 2.6 - 0.32 * i, 0.0), (S / 2 + 0.6, S + 2.9 - 0.32 * i, 0.35 * (i + 1)), I['assi'])
    z = 2.0
    while z < H - 2.0:   # buche pontaie
        sopra_aperture = any(zw - 0.3 <= z <= zw + 1.9 for zw in (3.2, 9.0, 15.0, 21.0))
        for f, Mf in enumerate(facce_casa(S, S)):
            for x in ((1.0, S - 1.0) if sopra_aperture else (1.0, S / 2, S - 1.0)):
                box(det, (x - 0.08, -0.03, z), (x + 0.08, 0.0, z + 0.16), I['interno_buio'], Mf[1])
        z += 1.7
    coronamento(det, 0, 0, S, S, H, pb)
    stendardo(det, S / 2, -0.55, H - 1.0, larg=1.0, alt=3.6)
    box(det, (S / 2 - 0.04, -0.55, H - 1.0), (S / 2 + 0.04, 0.0, H - 0.92), I['ferro'])
    ob = unisci([corpo, oggetto("Torre_Nobili_det", det, MB, coll)], "Torre_dei_Nobili")
    uv_finale(ob); ob.matrix_world = M; smussa(ob)
    return ob

def edifici_zone(coll, acc):
    """Chiesa, torre e palazzetto dei nobili, giardini, orti del borgo, alberi sul sagrato."""
    x0, y0, x1, y1 = LOTTO_CHIESA
    chiesa(T((x0 + x1) / 2, y0 + 0.6, 0), coll)
    x0, y0, x1, y1 = LOTTO_TORRE_NOBILI
    torre_nobili(T(x0 + 0.05, y0 + 0.1, 0), coll)
    x0, y0, x1, y1 = LOTTO_PALAZZETTO   # palazzetto con cortiletto davanti, verso Via dei Nobili
    Mp = T(x0 + 0.2, y0 + 2.2, 0)
    edificio("Palazzetto_Nobile", x1 - x0 - 0.4, y1 - y0 - 2.4, 3, 'pietra', 'lato', Mp, coll, lati=(True, True),
             Z=STILI_ZONA['nobili'])
    acc.pavimenta(Mp, 0, -2.2, x1 - x0 - 0.4, 0)
    for (x0, y0, x1, y1) in GIARDINI:
        acc.giardino(x1 - x0, y1 - y0, T(x0, y0, 0))
    for (x0, y0, x1, y1) in ORTI:
        acc.orto(x1 - x0, y1 - y0, T(x0, y0, 0))
    x0, y0, x1, y1 = SAGRATO
    for (x, y) in ((x0 + 2.0, y0 + 2.5), (x0 + 2.0, y1 - 2.5), (x1 - 2.0, y1 - 2.5)):
        albero(acc.det, T(x, y, 0), 0.8, 'jacaranda_tree')

# ----------------------------------------------------------------------
#  EDIFICI CON UN RUOLO (passo 4)
#  Ogni lotto ha un sistema locale: facciata principale a y=0 verso -y (la strada), x da 0 a W, profondita' D.
# ----------------------------------------------------------------------

def lotto(rett, fronte):
    """Matrice, larghezza e profondita' del lotto con la facciata verso 'S', 'N', 'E' o 'O'."""
    x0, y0, x1, y1 = rett
    if fronte == 'S': return T(x0, y0, 0), x1 - x0, y1 - y0
    if fronte == 'N': return T(x1, y1, 0) @ RZ(math.pi), x1 - x0, y1 - y0
    if fronte == 'O': return T(x0, y1, 0) @ RZ(-math.pi / 2), y1 - y0, x1 - x0
    return T(x1, y0, 0) @ RZ(math.pi / 2), y1 - y0, x1 - x0

def luce_calda(nome, pos, watt, coll):
    """Luce puntiforme arancio (brace della forgia, bocca del forno)."""
    ld = bpy.data.lights.new(nome, 'POINT'); ld.energy = watt; ld.color = (1.0, 0.45, 0.15)
    ld.shadow_soft_size = 0.25
    ob = bpy.data.objects.new(nome, ld); ob.location = pos; coll.objects.link(ob)

def _bx(det, M, a, b, mat):
    box(det, a, b, I[mat], M)

def tavolo(det, M, lungo=1.8):
    """Tavolo d'osteria con due panche, una brocca e due boccali."""
    h = lungo / 2
    _bx(det, M, (-h, -0.4, 0.72), (h, 0.4, 0.78), 'assi')
    for (lx, ly) in ((-h + 0.1, -0.3), (h - 0.18, -0.3), (-h + 0.1, 0.22), (h - 0.18, 0.22)):
        _bx(det, M, (lx, ly, 0), (lx + 0.08, ly + 0.08, 0.72), 'legno_travi')
    for by in (-0.78, 0.63):
        _bx(det, M, (-h, by, 0.42), (h, by + 0.15, 0.46), 'assi')
        for lx in (-h + 0.1, h - 0.17):
            _bx(det, M, (lx, by + 0.03, 0), (lx + 0.07, by + 0.12, 0.42), 'legno_travi')
    lathe(det, [(0.07, 0.78), (0.09, 0.86), (0.06, 0.98), (0.05, 1.02)], 10, I['terracotta'], M @ T(rr(-0.3, 0.3), 0.05, 0))
    for x in (-0.5, 0.45):
        lathe(det, [(0.04, 0.78), (0.045, 0.9)], 8, I['legno_grezzo'], M @ T(x, rr(-0.2, 0.2), 0), cap1=False)

def cassa(det, M, w=0.7, d=0.5, h=0.5):
    _bx(det, M, (0, 0, 0), (w, d, h), 'legno_grezzo')
    for z in (0.04, h - 0.08):   # assi di rinforzo
        _bx(det, M, (-0.015, -0.015, z), (w + 0.015, d + 0.015, z + 0.06), 'legno_travi')

def carretto(det, M):
    """Carretto a due ruote con stanghe."""
    _bx(det, M, (-1.1, -0.6, 0.62), (1.1, 0.6, 0.7), 'assi')
    for (a, b) in (((-1.1, -0.6), (1.1, -0.56)), ((-1.1, 0.56), (1.1, 0.6)), ((-1.1, -0.6), (-1.06, 0.6)), ((1.06, -0.6), (1.1, 0.6))):
        _bx(det, M, (a[0], a[1], 0.7), (b[0], b[1], 1.0), 'assi')
    for sy in (-0.72, 0.72):
        Mw = M @ T(0.1, sy, 0.55) @ RX(math.radians(90))
        lathe(det, [(0.55, -0.04), (0.55, 0.04), (0.48, 0.04), (0.48, -0.04)], 24, I['legno_travi'], Mw, chiuso=True)
        lathe(det, [(0.1, -0.07), (0.1, 0.07)], 10, I['legno_travi'], Mw)
        for s in range(8):
            box(det, (0.08, -0.02, -0.02), (0.5, 0.02, 0.02), I['legno_travi'], Mw @ RZ(s * math.pi / 4))
    for sy in (-0.5, 0.5):
        prism(det, [(1.1, 0.62), (2.6, 0.05), (2.6, 0.13), (1.1, 0.7)], sy - 0.03, sy + 0.03, I['legno_travi'], 'y', M)

# --- insegna della locanda ---------------------------------------------------------------------------------
# La parte appesa (catene + tavola) e' un oggetto a parte, "Insegna_Cinghiale", con l'origine sull'asse del braccio:
# Y locale = braccio (dal muro verso la strada), X = normale della tavola, Z in alto. Nel web oscilla rigida attorno
# a quell'asse (esporta_borgo.py la riconosce dal nome, citta.js la fa dondolare con le raffiche del vento);
# il braccio di ferro battuto resta nei dettagli della locanda.
# medieval_wood: assi con una scanalatura ogni ~43 px e chiodi vicino alle scanalature; per ogni asse dell'insegna
# una striscia pulita fra due scanalature (u), ripetuta specchiata in INS_FASCE fasce lungo l'asse (le pieghe sono
# parallele alla venatura e non si vedono) e allungata lungo la venatura (INS_VENA m per ripetizione)
COLONNE_LEGNO = [(0.762, 0.789), (0.479, 0.502), (0.525, 0.545)]   # misurate: nessun chiodo dentro
INS_VENA, INS_FASCE = 1.6, 3
INS_T, INS_R = 0.04, 0.009             # spessore delle assi, raggio dei bordi arrotondati
INS_MEZZA, INS_CATENE = 0.58, 0.53     # mezza larghezza della tavola, posizione delle catene (y)
INS_FRECCIA, INS_ASSE_H, INS_FESSURA = 0.06, 0.236, 0.004   # freccia dell'arco in alto, altezza di un'asse, fessura
INS_BRACCIO = (-0.80, 0.62)            # braccio: dal muro (y locale) alla punta
# sagoma del cinghiale rivolto a destra (u verso la testa, v in alto, zampe a v = 0) e parti chiare al suo interno:
# groppa bassa e spiovente, spalle alte con la criniera irta lungo tutta la schiena, testa grande a cuneo con la fronte
# dritta che scende fino al grugno, zanne a falce, zampe corte e robuste (la prima versione sembrava un maiale)
def _sagoma_cinghiale():
    def dorso(u):   # schiena senza le setole: dalla groppa sale alle spalle, poi il collo scende verso l'orecchio
        t = min(1.0, max(0.0, (u - 0.08) / 0.5))
        return 0.37 + 0.2 * math.sin(t * math.pi / 2) - 0.03 * max(0.0, (u - 0.6) / 0.1)
    p = [(0.075, 0.33), (0.088, 0.365)]
    u, k = 0.095, 0
    while u < 0.67:   # setole: punte inclinate all'indietro, irregolari, piu' alte sulle spalle e sul collo
        h = 0.02 + 0.05 * min(1.0, max(0.0, (u - 0.08) / 0.45)) * (0.75 + 0.25 * ((k * 7) % 3) / 2)
        p += [(u, dorso(u)), (u - 0.004, dorso(u) + h), (u + 0.014, dorso(u + 0.014))]
        u += 0.022; k += 1
    p += [(0.70, 0.545), (0.705, 0.6), (0.712, 0.645), (0.73, 0.595), (0.745, 0.545),                    # orecchio
          (0.80, 0.49), (0.86, 0.42), (0.92, 0.35), (0.965, 0.3), (0.99, 0.285),                          # fronte dritta
          (1.0, 0.27), (1.0, 0.18), (0.99, 0.165),                                                        # grugno
          (0.95, 0.16), (0.9, 0.15), (0.85, 0.14), (0.8, 0.13), (0.755, 0.12),                            # mascella, gola
          (0.745, 0.075), (0.748, 0.03), (0.756, 0.0), (0.716, 0.0), (0.71, 0.04), (0.705, 0.085),        # zampe davanti
          (0.694, 0.09), (0.69, 0.045), (0.693, 0.008), (0.656, 0.008), (0.654, 0.05), (0.648, 0.105),
          (0.58, 0.115), (0.48, 0.12), (0.39, 0.13), (0.33, 0.125),                                      # ventre che risale
          (0.322, 0.075), (0.325, 0.03), (0.332, 0.0), (0.294, 0.0), (0.288, 0.04), (0.282, 0.085),       # zampe dietro
          (0.272, 0.088), (0.266, 0.045), (0.268, 0.008), (0.232, 0.008), (0.228, 0.05), (0.218, 0.12),
          (0.17, 0.17), (0.125, 0.22), (0.09, 0.28),                                                      # coscia
          (0.085, 0.292), (0.066, 0.278), (0.055, 0.252), (0.05, 0.222), (0.042, 0.212),                  # coda
          (0.034, 0.228), (0.041, 0.258), (0.054, 0.292), (0.075, 0.308)]
    return p
SAGOMA_CINGHIALE = _sagoma_cinghiale()
BUCHI_CINGHIALE = [
    [(0.828, 0.395), (0.842, 0.404), (0.856, 0.395), (0.842, 0.386)],                                     # occhio
    [(0.905, 0.17), (0.935, 0.178), (0.96, 0.196), (0.976, 0.225), (0.98, 0.255), (0.972, 0.28),          # zanna a falce
     (0.962, 0.262), (0.962, 0.24), (0.952, 0.218), (0.935, 0.203), (0.915, 0.196), (0.9, 0.192)],
    [(0.85, 0.158), (0.868, 0.166), (0.882, 0.184), (0.886, 0.21), (0.877, 0.216), (0.873, 0.194),        # zanna di la'
     (0.86, 0.178), (0.845, 0.172)],
    [(0.992, 0.19), (0.995, 0.19), (0.995, 0.262), (0.992, 0.262)],                                       # disco del grugno
    [(0.64, 0.47), (0.66, 0.39), (0.665, 0.29), (0.65, 0.2), (0.659, 0.2), (0.676, 0.29),
     (0.671, 0.39), (0.649, 0.47)],                                                                       # spalla
    [(0.2, 0.36), (0.235, 0.3), (0.25, 0.23), (0.24, 0.17), (0.249, 0.17), (0.26, 0.23),
     (0.246, 0.305), (0.208, 0.365)],                                                                     # coscia
]

def _pulisci(pts, d=0.001):
    out = []
    for p in pts:
        if not out or (p - out[-1]).length > d:
            out.append(p)
    if len(out) > 2 and (out[0] - out[-1]).length <= d:
        out.pop()
    return out

def _sposta(pts, d):
    """Contorno chiuso (antiorario) spostato verso l'interno di d (d < 0: verso l'esterno), spigoli a mitra."""
    n = len(pts); out = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        e1 = (b - a).normalized(); e2 = (c - b).normalized()
        n1 = Vector((e1.y, -e1.x)); n2 = Vector((e2.y, -e2.x))   # normali esterne
        m = n1 + n2
        m = m.normalized() if m.length > 1e-6 else n1
        out.append(b - m * (d / max(0.5, m.dot(n1))))
    return out

def _bordo_alto(y, z_alto):
    """Lato alto della tavola: arco leggero, z_alto ai lati, z_alto + freccia al centro."""
    return z_alto + INS_FRECCIA * (1.0 - (y / INS_MEZZA) ** 2)

def _contorno_asse(y0, y1, z0, z1, raggi, z_alto=None, passo=0.03):
    """Contorno (y, z) antiorario di un'asse con gli angoli arrotondati (basso-sx, basso-dx, alto-dx, alto-sx);
    con z_alto il lato di sopra segue l'arco della tavola."""
    alto = (lambda y: _bordo_alto(y, z_alto)) if z_alto is not None else (lambda y: z1)
    rb, rd, rt, rs = raggi
    pts = []
    def lato(a, b):
        n = max(1, int((b - a).length / passo))
        pts.extend(a.lerp(b, i / n) for i in range(n))
    def angolo(c, r, a0):
        for i in range(4):
            a = math.radians(a0 + 22.5 * i)
            pts.append(Vector((c.x + r * math.cos(a), c.y + r * math.sin(a))))
    V = lambda y, z: Vector((y, z))
    lato(V(y0 + rb, z0), V(y1 - rd, z0)); angolo(V(y1 - rd, z0 + rd), rd, -90)
    lato(V(y1, z0 + rd), V(y1, alto(y1) - rt)); angolo(V(y1 - rt, alto(y1) - rt), rt, 0)
    n = max(2, int((y1 - y0) / passo))
    for i in range(n):
        y = (y1 - rt) + ((y0 + rs) - (y1 - rt)) * i / n
        pts.append(V(y, alto(y)))
    angolo(V(y0 + rs, alto(y0) - rs), rs, 90)
    lato(V(y0, alto(y0) - rs), V(y0, z0 + rb)); angolo(V(y0 + rb, z0 + rb), rb, 180)
    return _pulisci(pts)

def _consuma(pts, rng):
    """Usura del bordo: rientra di 0-2,5 mm, con due o tre scheggiature di 5-8 mm."""
    n = len(pts); d = [rng.uniform(0.0, 0.0025) for _ in range(n)]
    for _ in range(rng.randint(2, 3)):
        c = rng.randrange(n); prof = rng.uniform(0.005, 0.008)
        for k, f in ((-2, 0.3), (-1, 0.75), (0, 1.0), (1, 0.7), (2, 0.25)):
            d[(c + k) % n] += prof * f
    out = []
    for i in range(n):
        a, b = pts[i - 1], pts[(i + 1) % n]
        t = (b - a).normalized(); out.append(pts[i] - Vector((t.y, -t.x)) * d[i])
    return out

def _asse_tonda(bm, pts, t, r, mi, uvf, S=3):
    """Asse con i bordi arrotondati: contorno (y, z) estruso lungo x da -t/2 a t/2 (quarti di cerchio in S passi)."""
    prof = [(r * (1 - math.cos(math.pi / 2 * k / S)), -(t / 2 - r) - r * math.sin(math.pi / 2 * k / S))
            for k in range(S, -1, -1)]
    prof += [(r * (1 - math.cos(math.pi / 2 * k / S)), (t / 2 - r) + r * math.sin(math.pi / 2 * k / S))
             for k in range(S + 1)]
    anelli = [[bm.verts.new((x, p.x, p.y)) for p in (_sposta(pts, d) if d > 1e-6 else pts)] for (d, x) in prof]
    uv = bm.loops.layers.uv.verify(); fs = []
    for A, B in zip(anelli, anelli[1:]):
        for i in range(len(A)):
            j = (i + 1) % len(A)
            f = bm.faces.new((A[i], A[j], B[j], B[i])); f.smooth = True; fs.append(f)
    fs += [bm.faces.new(anelli[0][::-1]), bm.faces.new(anelli[-1])]
    for f in fs:
        f.material_index = mi
        if uvf:
            for l in f.loops:
                l[uv].uv = uvf(l.vert.co)
    return fs

def _anello(bm, c, a, b, R1, R2, r, mi, nu=14, nv=6):
    """Anello o maglia ovale di ferro: centro c, semiassi R1 lungo a e R2 lungo b (versori), filo di raggio r."""
    no = a.cross(b); giri = []
    for i in range(nu):
        t = 2 * math.pi * i / nu
        p = c + a * (R1 * math.cos(t)) + b * (R2 * math.sin(t))
        q = (a * (math.cos(t) / R1) + b * (math.sin(t) / R2)).normalized()
        giri.append([bm.verts.new(p + q * (r * math.cos(2 * math.pi * k / nv)) + no * (r * math.sin(2 * math.pi * k / nv)))
                     for k in range(nv)])
    fs = []
    for i in range(nu):
        A, B = giri[i], giri[(i + 1) % nu]
        for k in range(nv):
            f = bm.faces.new((A[k], A[(k + 1) % nv], B[(k + 1) % nv], B[k])); f.material_index = mi; f.smooth = True
            fs.append(f)
    return fs

def _nastro(bm, pts, larg, spess, mi, M):
    """Ferro piatto lungo la polilinea (y, z): larghezza 'larg' in x, spessore 'spess' nel piano."""
    n = len(pts); sez = []
    for i, p in enumerate(pts):
        t = (pts[min(n - 1, i + 1)] - pts[max(0, i - 1)]).normalized(); o = Vector((-t.y, t.x)) * (spess / 2)
        sez.append([bm.verts.new(_tr((x, q.x, q.y), M)) for (x, q) in
                    ((-larg / 2, p + o), (larg / 2, p + o), (larg / 2, p - o), (-larg / 2, p - o))])
    fs = []
    for A, B in zip(sez, sez[1:]):
        for k in range(4):
            fs.append(bm.faces.new((A[k], A[(k + 1) % 4], B[(k + 1) % 4], B[k])))
    fs += [bm.faces.new(sez[0][::-1]), bm.faces.new(sez[-1])]
    for f in fs:
        f.material_index = mi
    return fs

def _spirale(c, r0, r1, a0, giri, verso=1, n=48):
    """Ricciolo: spirale da raggio r0 (angolo a0, gradi) a r1 in 'giri' giri."""
    return [Vector((c[0] + (r0 + (r1 - r0) * s) * math.cos(math.radians(a0) + verso * 2 * math.pi * giri * s),
                    c[1] + (r0 + (r1 - r0) * s) * math.sin(math.radians(a0) + verso * 2 * math.pi * giri * s)))
            for s in (i / n for i in range(n + 1))]

def _font_insegna():
    for p in INSEGNA_FONT:
        if os.path.isfile(p):
            try:
                return bpy.data.fonts.load(p, check_existing=True)
            except Exception:
                pass
    return None

def _curva_2d(nome, testo=None, contorni=None, font=None):
    """Riempimento di una scritta o di contorni chiusi (i contorni interni fanno da buco) -> lista di poligoni (u, v)."""
    if testo is not None:
        cu = bpy.data.curves.new(nome, 'FONT'); cu.body = testo; cu.size = 1.0
        if font:
            cu.font = font
        cu.align_x = 'CENTER'; cu.align_y = 'BOTTOM_BASELINE'
    else:
        cu = bpy.data.curves.new(nome, 'CURVE'); cu.dimensions = '2D'
        for c in contorni:
            sp = cu.splines.new('POLY'); sp.points.add(len(c) - 1)
            for p, (u, v) in zip(sp.points, c):
                p.co = (u, v, 0.0, 1.0)
            sp.use_cyclic_u = True
    cu.fill_mode = 'BOTH'
    ob = bpy.data.objects.new(nome, cu); bpy.context.scene.collection.objects.link(ob)
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    poli = [[tuple(me.vertices[i].co[:2]) for i in p.vertices] for p in me.polygons]
    bpy.data.objects.remove(ob); bpy.data.curves.remove(cu); bpy.data.meshes.remove(me)
    return poli

def _scala_poli(poli, larg, alto, u0=None):
    """Fattore di scala perche' i poligoni stiano in larg x alto, e centro orizzontale."""
    us = [u for p in poli for u, v in p]; vs = [v for p in poli for u, v in p]
    s = min(larg / (max(us) - min(us)), alto / (max(vs) - min(0.0, min(vs))))
    return s, (max(us) + min(us)) / 2

def insegna_cinghiale(det, M, x, y_muro, z, coll):
    """Insegna a bandiera della locanda (M = matrice del lotto). Oggetto fermo "Insegna_Braccio": braccio di ferro
    battuto murato a (x, y_muro) alla quota z, con tirante e riccioli. Oggetto "Insegna_Cinghiale": due catene di anelli e
    una tavola di tre assi (4 cm, bordi arrotondati e consumati, lato alto ad arco) con bandelle di ferro, il
    cinghiale e la scritta pirografati su entrambe le facce."""
    rng = random.Random(SEED + 7)   # usura propria: non sposta le sequenze RNG e RNG_D del borgo
    y0b, y1b = INS_BRACCIO
    Ms = M @ T(x, y_muro + y0b, z) @ RZ(math.pi)   # origine sull'asse del braccio, a meta' fra le catene
    # --- braccio (fermo, oggetto a parte "Insegna_Braccio" con il ferro dell'insegna): piastra al muro, barra quadra,
    #     tirante dall'alto, due riccioli, ricciolo in punta
    bb = nuovo_bm()
    box(bb, (-0.03, y0b, -0.10), (0.03, y0b + 0.012, 0.50), 0, Ms)
    for zb in (-0.05, 0.2, 0.45):
        sfera(bb, (0.0, y0b + 0.014, zb), 0.011, 0, Ms, sc=(1.0, 0.45, 1.0), sub=1)
    box(bb, (-0.016, y0b, -0.016), (0.016, y1b, 0.016), 0, Ms)
    _nastro(bb, [Vector((y0b + 0.014, 0.45)), Vector((0.2, 0.016))], 0.026, 0.012, 0, Ms)
    box(bb, (-0.02, 0.17, -0.02), (0.02, 0.23, 0.02), 0, Ms)                       # fascetta del tirante
    _nastro(bb, _spirale((-0.628, 0.188), 0.16, 0.022, -90, 1.55, 1), 0.02, 0.01, 0, Ms)
    _nastro(bb, _spirale((-0.15, 0.085), 0.062, 0.014, -90, 1.4, -1), 0.02, 0.01, 0, Ms)
    _nastro(bb, _spirale((y1b, 0.05), 0.05, 0.012, -90, 1.3, 1), 0.032, 0.01, 0, Ms)

    ob_b = oggetto("Insegna_Braccio", bb, ['insegna_ferro'], coll)
    uv_finale(ob_b)
    # --- parte appesa (oggetto a parte, coordinate locali)
    MI = ['insegna_legno', 'insegna_ferro', 'insegna_bruciato']
    LG, FE, BR = range(3)
    bm = nuovo_bm(); chiusi = []
    X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
    # catene: un anello tondo attorno al braccio, poi sei maglie ovali a piani alterni, l'ultima nell'occhiello
    rf, Lm, Wm = 0.0042, 0.062, 0.036
    for yc in (-INS_CATENE, INS_CATENE):
        zc = 0.016 - 0.0215                        # l'anello poggia sulla barra (raggio interno 21,5 mm)
        chiusi += _anello(bm, Vector((0, yc, zc)), Z, X, 0.026, 0.026, 0.0045, FE, nu=16)
        zfondo = zc - 0.026
        for i in range(6):
            zm = zfondo - Lm / 2 + 2 * rf - i * (Lm - 4 * rf)
            chiusi += _anello(bm, Vector((0, yc, zm)), Z, (Y if i % 2 == 0 else X), Lm / 2 - rf, Wm / 2 - rf, rf, FE)
        zfondo = zm - (Lm / 2 - rf)
        ze = zfondo + rf + 0.005 - 0.018            # occhiello piatto, nel piano della tavola
        chiusi += _anello(bm, Vector((0, yc, ze)), Z, Y, 0.018, 0.018, 0.005, FE, nu=12)
        z_occhio = ze - 0.023
    z_alto = z_occhio - 0.004 - INS_FRECCIA * (1.0 - (INS_CATENE / INS_MEZZA) ** 2)   # bordo alto ai lati
    z_basso = z_alto - 3 * INS_ASSE_H - 2 * INS_FESSURA
    # tre assi: ognuna con una tavola intera della texture (venatura lungo l'asse), un po' sfalsate e consumate
    fessure = []; assi = []
    for k in range(3):
        za = z_basso + k * (INS_ASSE_H + INS_FESSURA); zb = za + INS_ASSE_H
        dy = rng.uniform(-0.004, 0.004)
        raggi = (0.035 if k == 0 else 0.006, 0.035 if k == 0 else 0.006, 0.028 if k == 2 else 0.006,
                 0.028 if k == 2 else 0.006)
        pts = _contorno_asse(-INS_MEZZA + dy, INS_MEZZA + dy, za, zb, raggi, z_alto if k == 2 else None)
        pts = _consuma(pts, rng)
        chiusi += _asse_tonda(bm, pts, INS_T, INS_R, LG, None)
        assi.append((za, COLONNE_LEGNO[k], rng.uniform(0.0, INS_VENA)))
        if k < 2:
            fessure.append((zb, zb + INS_FESSURA))
    # UV delle assi: tagli alle pieghe delle fasce, poi u a dente di sega specchiato, v lungo l'asse
    hb = INS_ASSE_H / INS_FASCE
    for k, (za, _, _) in enumerate(assi):
        for i in range(1, INS_FASCE + (1 if k == 2 else 0)):
            lg = [f for f in bm.faces if f.material_index == LG]
            geom = list({v for f in lg for v in f.verts}) + list({e for f in lg for e in f.edges}) + lg
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, za + i * hb), plane_no=(0, 0, 1))
    uvl = bm.loops.layers.uv.verify()
    for f in bm.faces:
        if f.material_index != LG:
            continue
        zc = f.calc_center_median().z
        za, (u0, u1), off = next((a for a in reversed(assi) if zc >= a[0] - 0.002), assi[0])
        for l in f.loops:
            s = ((l.vert.co.z - za) / hb) % 2.0
            l[uvl].uv = (1.2 * (u0 + (u1 - u0) * (2.0 - s if s > 1.0 else s)), (l.vert.co.y + off) * 1.2 / INS_VENA)
    # bandelle di ferro alle estremita' (girano sotto la tavola e sopra, fino all'occhiello), con i chiodi
    h, s = INS_T / 2, 0.003
    for yc in (-INS_CATENE, INS_CATENE):
        zt = _bordo_alto(yc, z_alto)
        for sx in (-1, 1):
            chiusi += box(bm, (sx * h, yc - 0.0175, z_basso - s), (sx * (h + s), yc + 0.0175, zt + s), FE)
            for zc in (z_basso + 0.12, z_basso + 0.36, z_basso + 0.6):
                sfera(bm, (sx * (h + s + 0.0015), yc, zc), 0.0075, FE, sc=(0.4, 1.0, 1.0), sub=1)
        chiusi += box(bm, (-h - s, yc - 0.0175, z_basso - s), (h + s, yc + 0.0175, z_basso), FE)
        chiusi += box(bm, (-h - s, yc - 0.0175, zt), (h + s, yc + 0.0175, zt + s), FE)
        chiusi += box(bm, (-0.005, yc - 0.007, zt), (0.005, yc + 0.007, z_occhio + 0.006), FE)   # gambo dell'occhiello
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])   # solo parti chiuse fin qui (assi, catene, bandelle)

    # --- pirografia (a 1 mm dalla faccia): cornice, scritta ad arco, cinghiale, scritta, due losanghe
    font = _font_insegna()
    zc_alto = _bordo_alto(0.0, z_alto)
    R_arco = INS_MEZZA ** 2 / (2 * INS_FRECCIA) - 0.12            # scritta in alto parallela all'arco
    disegni = []   # (poligoni, funzione (u, v) -> (y, z), specchiare sul retro: le scritte si leggono dai due lati)
    s1 = None
    if INSEGNA_SCRITTA[0]:
        p = _curva_2d("_scritta1", testo=INSEGNA_SCRITTA[0], font=font)
        s1, c1 = _scala_poli(p, 0.80, 0.072)
        zb1 = zc_alto - 0.062 - 0.072
        f1 = lambda u, v, s=s1, c=c1, zb=zb1: (
            (R_arco + v * s) * math.sin((u - c) * s / R_arco), zb - R_arco + (R_arco + v * s) * math.cos((u - c) * s / R_arco))
        disegni.append((p, f1, True))
    if INSEGNA_SCRITTA[1]:
        p = _curva_2d("_scritta2", testo=INSEGNA_SCRITTA[1], font=font)
        s2, c2 = _scala_poli(p, 0.78, 0.088)
        zb2 = z_basso + 0.062
        f2 = lambda u, v, s=s2, c=c2, zb=zb2: ((u - c) * s, zb + v * s)
        disegni.append((p, f2, True))
        lw = max((u - c2) * s2 for q in p for u, v in q)
        for sy in (-1, 1):   # losanghe ai lati della scritta
            cy, cz = sy * (lw + 0.045), zb2 + 0.044
            disegni.append(([[(cy, cz - 0.02), (cy + 0.012, cz), (cy, cz + 0.02), (cy - 0.012, cz)]], lambda u, v: (u, v),
                            True))
    sb = _curva_2d("_cinghiale", contorni=[SAGOMA_CINGHIALE] + BUCHI_CINGHIALE)
    zt_c = (zb1 - 0.04) if s1 else zc_alto - 0.08
    zb_c = z_basso + 0.062 + 0.088 + 0.065
    sc, cc = _scala_poli(sb, 0.62, zt_c - zb_c)
    fc = lambda u, v, s=sc, c=cc, zb=zb_c: ((u - c) * s, zb + v * s)
    disegni.append((sb, fc, False))
    # cornice bruciata a 3 cm dal bordo (fra le bandelle e l'estremita' della tavola sui lati)
    bordo = _contorno_asse(-INS_MEZZA, INS_MEZZA, z_basso, 0.0, (0.035, 0.035, 0.028, 0.028), z_alto, passo=0.02)
    def striscia(d0, d1):
        a, b = _sposta(bordo, d0), _sposta(bordo, d1); n = len(a)
        return [[tuple(a[i]), tuple(a[(i + 1) % n]), tuple(b[(i + 1) % n]), tuple(b[i])] for i in range(n)]
    disegni.append((striscia(0.027, 0.033), lambda u, v: (u, v), True))
    uv = bm.loops.layers.uv.verify()
    for sx in (-1, 1):
        for (poli, f, testo) in disegni:
            for pol in poli:
                vs = []
                for (u, v) in pol:
                    yy, zz = f(u, v)
                    vs.append(bm.verts.new((sx * (h + 0.001), (yy if sx > 0 or not testo else -yy), zz)))
                try:
                    fa = bm.faces.new(vs)
                except ValueError:
                    continue
                fa.material_index = BR; fa.normal_update()
                if fa.normal.x * sx < 0:
                    fa.normal_flip()
    dec = [f for f in bm.faces if f.material_index == BR]
    bmesh.ops.remove_doubles(bm, verts=list({v for f in dec for v in f.verts}), dist=1e-5)
    # la pirografia non attraversa le fessure fra le assi
    for (za, zb) in fessure:
        for zz in (za, zb):
            dec = [f for f in bm.faces if f.material_index == BR]
            geom = list({v for f in dec for v in f.verts}) + list({e for f in dec for e in f.edges}) + dec
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, zz), plane_no=(0, 0, 1))
        via = [f for f in bm.faces if f.material_index == BR and za < f.calc_center_median().z < zb]
        bmesh.ops.delete(bm, geom=via, context='FACES')
    # UV a scatola per ferro e pirografia (le assi le hanno gia')
    bm.normal_update()
    for f in bm.faces:
        if f.material_index == LG:
            continue
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        for l in f.loops:
            co = l.vert.co
            l[uv].uv = (co.y, co.z) if ax == 0 else ((co.x, co.z) if ax == 1 else (co.x, co.y))
    ob = oggetto("Insegna_Cinghiale", bm, MI, coll, ricalcola=False)
    ob.matrix_world = Ms
    return ob

def locanda(coll, pav):
    M, W, D = lotto(LOTTO_LOCANDA, 'S')
    det = nuovo_bm()
    yb = 3.4; Wb = 10.6
    edificio("Locanda_del_Cinghiale", Wb, 9.0, 3, 'graticcio', 'lato', M @ T(0.3, yb, 0), coll,
             bottega=True, lati=(True, True))
    # terrazza con pergolato, tavoli e insegna
    pav.pavimenta(M, 0.0, 0.0, Wb + 0.6, yb)
    for x in (0.5, 3.8, 7.1, 10.4):
        _bx(det, M, (x - 0.08, 0.3, 0), (x + 0.08, 0.46, 2.7), 'legno_travi')
    _bx(det, M, (0.3, 0.3, 2.62), (10.6, 0.46, 2.78), 'legno_travi')
    x = 0.45
    while x < 10.6:
        _bx(det, M, (x, 0.2, 2.78), (x + 0.1, yb + 0.1, 2.88), 'legno_travi'); x += 0.75
    x = 0.6
    while x < 10.4:   # vite sul pergolato: cespugli Poly Haven piccoli e schiacciati sulle travi
        for y in (0.9, yb - 0.9):
            istanza('shrub_02', M @ T(x + rr(-0.3, 0.3), y + rr(-0.3, 0.3), 2.82) @ Matrix.Diagonal((1, 1, 0.5, 1)),
                    rr(0.8, 1.0))
        x += rr(0.8, 1.1)
    for x in (0.5, 10.4):   # e rampicanti al piede dei pali d'angolo
        istanza('shrub_02', M @ T(x, 0.6, 0), rr(0.4, 0.5))
    for (x, y) in ((2.1, 1.5), (5.4, 1.6), (8.7, 1.5)):
        tavolo(det, M @ T(x, y, 0))
    botte(det, 10.0, 2.6, I['legno_grezzo'], I['ferro'], M); botte(det, 10.0, 2.0, I['legno_grezzo'], I['ferro'], M)
    insegna_cinghiale(det, M, 0.75, yb - 0.32, 4.9, coll)   # muro del primo piano (graticcio: sporge 32 cm)
    # passo carraio verso il cortile, cortile con abbeveratoio e carro
    xp0, xp1 = Wb + 0.6, W - 0.2
    for x in (xp0 + 0.1, xp1 - 0.25):
        _bx(det, M, (x, yb - 0.15, 0), (x + 0.25, yb + 0.15, 3.4), 'legno_travi')
    _bx(det, M, (xp0, yb - 0.25, 3.4), (xp1, yb + 0.25, 3.65), 'legno_travi')
    prism(det, [(yb - 0.6, 3.6), (yb, 4.2), (yb + 0.6, 3.6), (yb + 0.6, 3.75), (yb, 4.35), (yb - 0.6, 3.75)],
          xp0 - 0.2, xp1 + 0.2, I['coppi'], 'x', M)
    pav.pavimenta(M, xp0, 0.0, W, D - 5.2); pav.pavimenta(M, 0.0, yb + 9.0, W, D - 5.2)
    _bx(det, M, (1.0, 13.4, 0), (3.6, 14.2, 0.7), 'pietra_muro')
    _bx(det, M, (1.12, 13.52, 0.45), (3.48, 14.08, 0.6), 'acqua')
    carretto(det, M @ T(7.5, 14.0, 0) @ RZ(math.radians(-20)))
    for i in range(5):   # balle di fieno
        _bx(det, M, (4.5 + i * 0.95, 15.3, 0), (5.35 + i * 0.95, 15.8, 0.45), 'fieno')
    _bx(det, M, (5.0, 15.35, 0.45), (6.7, 15.75, 0.9), 'fieno')
    # stalle: muro di fondo e fianchi in pietra, poste aperte verso il cortile, tetto a una falda
    ys, Ds, hs = D - 5.2, 5.0, 3.0
    _bx(det, M, (0.2, ys + Ds - 0.5, 0), (W - 0.2, ys + Ds, hs + 0.8), 'pietra_muro')
    for x in (0.2, W - 0.7):
        prism(det, [(ys, 0), (ys + Ds, 0), (ys + Ds, hs + 0.8), (ys, hs)], x, x + 0.5, I['pietra_muro'], 'x', M)
    prism(det, [(ys - 0.5, hs - 0.1), (ys + Ds + 0.3, hs + 0.9), (ys + Ds + 0.3, hs + 1.02), (ys - 0.5, hs + 0.02)],
          0.0, W, I['coppi_vecchi'], 'x', M)
    nst = 5; passo = (W - 1.4) / nst
    for i in range(nst + 1):
        x = 0.7 + i * passo
        _bx(det, M, (x - 0.1, ys, 0), (x + 0.1, ys + 0.2, hs), 'legno_travi')
        if 0 < i < nst:
            _bx(det, M, (x - 0.04, ys + 0.2, 0), (x + 0.04, ys + Ds - 0.5, 1.6), 'assi')
    _bx(det, M, (0.2, ys - 0.1, hs - 0.25), (W - 0.2, ys + 0.2, hs), 'legno_travi')
    for i in range(nst):
        x0 = 0.7 + i * passo + 0.15
        _bx(det, M, (x0, ys + 0.02, 0), (x0 + passo * 0.42, ys + 0.08, 1.25), 'assi')   # mezze porte
        _bx(det, M, (x0, ys + Ds - 1.6, 0), (x0 + passo - 0.4, ys + Ds - 0.5, 0.35), 'fieno')
        _bx(det, M, (x0 + 0.2, ys + 0.3, 0.0), (x0 + passo - 0.6, ys + Ds - 0.6, 0.06), 'fieno')
    ob = oggetto("Locanda_dettagli", det, MB, coll); uv_finale(ob); smussa(ob, 0.008)

def casa_mercante(coll, pav):
    M, W, D = lotto(LOTTO_MERCANTE, 'S')
    det = nuovo_bm()
    Wb, Db, yb, xb = 9.0, 8.4, 1.4, 0.5
    edificio("Casa_del_Mercante", Wb, Db, 4, 'intonaco', 'fronte', M @ T(xb, yb, 0), coll, bottega=True, lati=(True, True))
    pav.pavimenta(M, 0.0, -3.0, W, yb)   # fino alla Via Maestra
    Mb = M @ T(xb, yb, 0); xc = Wb / 2; zt = H0 + 3 * HF
    for k in (1, 2, 3):   # porte di carico sovrapposte, con le ante aperte
        z0 = H0 + (k - 1) * HF
        _bx(det, Mb, (xc - 0.7, -0.03, z0 + 0.15), (xc + 0.7, 0.0, z0 + 2.35), 'interno_buio')
        _bx(det, Mb, (xc - 0.85, -0.12, z0 + 0.05), (xc + 0.85, 0.0, z0 + 0.15), 'legno_travi')
        for sx in (-1, 1):
            xa = xc + sx * 0.7
            x0, x1 = sorted((xa, xa + sx * 0.06))
            _bx(det, Mb, (x0, -0.72, z0 + 0.15), (x1, -0.02, z0 + 2.3), 'assi')
    # argano: trave sporgente sotto il colmo, carrucola, fune e sacco appeso
    za = zt + 1.65
    _bx(det, Mb, (xc - 0.12, -1.7, za), (xc + 0.12, 0.6, za + 0.22), 'legno_travi')
    prism(det, [(-1.0, za + 0.22), (-0.2, za + 0.2), (-0.2, za + 0.32)], xc - 0.06, xc + 0.06, I['legno_travi'], 'x', Mb)
    for sx in (-1, 1):
        _bx(det, Mb, (xc + sx * 0.25 - 0.2, -1.8, za + 0.42), (xc + sx * 0.25 + 0.2, 0.1, za + 0.5), 'coppi')
    lathe(det, [(0.2, -0.03), (0.2, 0.03)], 16, I['legno_grezzo'], Mb @ T(xc, -1.5, za - 0.12) @ RY(math.pi / 2))
    _bx(det, Mb, (xc + 0.19, -1.52, 5.2), (xc + 0.21, -1.48, za - 0.12), 'juta')
    sacco(det, xc + 0.2, -1.5, I['juta'], Mb @ T(0, 0, 4.6), 0.4)
    _bx(det, Mb, (xc + 0.17, -1.53, 5.05), (xc + 0.23, -1.47, 5.2), 'juta')
    # merci: casse, sacchi e botti davanti e di lato
    for i in range(4):
        cassa(det, M @ T(0.4 + i * 0.8, -0.1, 0) @ RZ(rr(-0.08, 0.08)))
        if i % 2 == 0:
            cassa(det, M @ T(0.5 + i * 0.8, 0.0, 0.5) @ RZ(rr(-0.1, 0.1)), 0.6, 0.45, 0.45)
    for i in range(5):
        sacco(det, 4.2 + i * 0.55 + rr(-0.1, 0.1), 0.35 + rr(-0.1, 0.1), I['juta'], M, rr(0, 3))
    for i in range(3):
        sacco(det, 4.5 + i * 0.6, 0.55, I['juta'], M @ T(0, 0, 0.45), rr(0, 3))
    xl = xb + Wb + 0.3
    pav.pavimenta(M, xl, yb, W, D)
    for i in range(3):
        botte(det, xl + 0.5 + i * 0.65, yb + 0.6, I['legno_grezzo'], I['ferro'], M)
        botte(det, xl + 0.5 + i * 0.65, yb + 1.25, I['legno_grezzo'], I['ferro'], M, sdraiata=(i == 1))
    for i in range(3):
        for j in range(2):
            cassa(det, M @ T(xl + 0.2 + i * 0.8, yb + 2.4, j * 0.5))
    carretto(det, M @ T(xl + 1.6, yb + 5.0, 0) @ RZ(math.radians(95)))
    ob = oggetto("Casa_del_Mercante_dettagli", det, MB, coll); uv_finale(ob); smussa(ob, 0.008)

def incudine(det, M):
    lathe(det, [(0.32, 0.0), (0.3, 0.55), (0.28, 0.6)], 14, I['legno_grezzo'], M)
    _bx(det, M, (-0.22, -0.12, 0.6), (0.22, 0.12, 0.7), 'ferro')
    _bx(det, M, (-0.12, -0.08, 0.7), (0.12, 0.08, 0.82), 'ferro')
    _bx(det, M, (-0.3, -0.11, 0.82), (0.25, 0.11, 0.95), 'ferro')
    lathe(det, [(0.1, 0.0), (0.01, 0.32)], 10, I['ferro'], M @ T(0.25, 0, 0.88) @ RY(math.pi / 2), liscio=False)

def fabbro(coll, pav):
    M, W, D = lotto(LOTTO_FABBRO, 'O')
    det = nuovo_bm()
    yb = 4.2
    edificio("Fabbro", W - 0.4, D - yb - 0.2, 2, 'pietra', 'lato', M @ T(0.2, yb, 0), coll, lati=(True, True))
    pav.pavimenta(M, 0.0, 0.0, W, yb)
    # tettoia grande sul cortile
    for x in (0.3, W / 2, W - 0.45):
        _bx(det, M, (x, 0.3, 0), (x + 0.16, 0.46, 2.6), 'legno_travi')
    _bx(det, M, (0.2, 0.25, 2.5), (W - 0.2, 0.5, 2.68), 'legno_travi')
    prism(det, [(0.0, 2.62), (yb, 3.25), (yb, 3.37), (0.0, 2.74)], 0.0, W, I['coppi_vecchi'], 'x', M)
    # forgia: focolare in pietra con la brace, cappa e camino
    fx0, fx1, fy0, fy1 = 0.8, 2.4, yb - 1.1, yb
    _bx(det, M, (fx0, fy0, 0), (fx1, fy1, 0.85), 'pietra_muro')
    _bx(det, M, (fx0 + 0.25, fy0 + 0.2, 0.8), (fx1 - 0.25, fy1 - 0.2, 0.9), 'brace')
    luce_calda("Luce_forgia", M @ Vector(((fx0 + fx1) / 2, (fy0 + fy1) / 2, 1.25)), 300.0, coll)
    for _ in range(18):
        sfera(det, (rr(fx0 + 0.3, fx1 - 0.3), rr(fy0 + 0.25, fy1 - 0.25), 0.9), rr(0.03, 0.06), I['brace'], M, sub=1)
    prism(det, [(fx0 - 0.1, fy0 - 0.15), (fx1 + 0.1, fy0 - 0.15), (fx1 - 0.25, fy0 + 0.35), (fx0 + 0.25, fy0 + 0.35)],
          1.9, 2.45, I['mattoni'], 'z', M)
    _bx(det, M, (fx0 + 0.25, fy0 + 0.1, 2.45), (fx1 - 0.25, fy1, 7.4), 'mattoni')
    _bx(det, M, (fx0 + 0.15, fy0, 7.4), (fx1 - 0.15, fy1 + 0.1, 7.6), 'pietra_cornici')
    # mantice di cuoio accanto al focolare
    prism(det, [(fy0 + 0.1, 0.9), (fy1 - 0.1, 0.9), (fy1 - 0.1, 1.25), (fy0 + 0.1, 0.95)], fx1, fx1 + 0.5, I['cuoio'], 'x', M)
    _bx(det, M, (fx1, fy0 + 0.05, 0.85), (fx1 + 0.55, fy1 - 0.05, 0.9), 'legno_travi')
    _bx(det, M, (fx1 + 0.1, fy0 + 0.3, 0), (fx1 + 0.18, fy0 + 0.38, 0.88), 'legno_travi')
    incudine(det, M @ T(3.4, 2.0, 0) @ RZ(0.3))
    botte(det, 4.6, 2.6, I['legno_grezzo'], I['ferro'], M, h=0.7)
    _bx(det, M, (4.38, 2.38, 0.62), (4.82, 2.82, 0.64), 'acqua')
    for i in range(3):   # cerchioni da ruota appoggiati al muro
        Mr = M @ T(5.6 + i * 0.35, yb - 0.25, 0.62) @ RX(math.radians(80))
        lathe(det, [(0.6, -0.025), (0.6, 0.025), (0.56, 0.025), (0.56, -0.025)], 28, I['ferro'], Mr, chiuso=True)
    _bx(det, M, (W - 1.6, yb - 0.4, 0.9), (W - 0.4, yb - 0.05, 1.0), 'legno_travi')   # rastrelliera attrezzi
    for i in range(5):
        _bx(det, M, (W - 1.5 + i * 0.22, yb - 0.25, 0.4), (W - 1.47 + i * 0.22, yb - 0.2, 1.3), 'ferro')
    catasta(det, 0.4, 2.2, 0.6, 1.4, 0.7, M)
    ob = oggetto("Fabbro_dettagli", det, MB, coll); uv_finale(ob); smussa(ob, 0.008)

def falegname(coll, pav):
    M, W, D = lotto(LOTTO_FALEGNAME, 'E')
    det = nuovo_bm()
    yb = 4.0
    edificio("Falegname", W - 0.4, D - yb - 0.2, 2, 'graticcio', 'fronte', M @ T(0.2, yb, 0), coll, lati=(True, True))
    pav.pavimenta(M, 0.0, 0.0, W, yb)
    # cavalletti con un tronco a meta' segato
    for (x, y) in ((1.2, 1.4), (3.0, 1.4)):
        for sx in (-1, 1):
            prism(det, [(y - 0.45 * sx - 0.05, 0), (y - 0.45 * sx + 0.05, 0), (y + 0.05, 0.8), (y - 0.05, 0.8)],
                  x - 0.35, x - 0.28, I['legno_travi'], 'x', M)
            prism(det, [(y - 0.45 * sx - 0.05, 0), (y - 0.45 * sx + 0.05, 0), (y + 0.05, 0.8), (y - 0.05, 0.8)],
                  x + 0.28, x + 0.35, I['legno_travi'], 'x', M)
        _bx(det, M, (x - 0.4, y - 0.06, 0.8), (x + 0.4, y + 0.06, 0.88), 'legno_travi')
    lathe(det, [(0.22, 0.0), (0.2, 3.4)], 14, I['legno_grezzo'], M @ T(0.4, 1.4, 1.1) @ RY(math.pi / 2))
    _bx(det, M, (2.0, 1.15, 1.1), (2.02, 1.65, 1.75), 'ferro')   # sega
    _bx(det, M, (1.98, 1.2, 1.7), (2.04, 1.6, 1.78), 'legno_travi')
    # banco da lavoro
    _bx(det, M, (4.4, yb - 1.0, 0.8), (6.8, yb - 0.3, 0.9), 'assi')
    for x in (4.5, 6.6):
        for y in (yb - 0.95, yb - 0.45):
            _bx(det, M, (x, y, 0), (x + 0.1, y + 0.1, 0.8), 'legno_travi')
    _bx(det, M, (4.9, yb - 0.85, 0.9), (5.6, yb - 0.55, 0.96), 'legno_grezzo')
    # cataste di tavole con i distanziali, tavole appoggiate al muro
    for p in range(2):
        x0 = 4.3 + p * 1.9
        for k in range(7):
            z = k * 0.07
            if k % 3 == 0:
                for yy in (0.4, 1.4, 2.4):
                    _bx(det, M, (x0, yy, z), (x0 + 1.6, yy + 0.06, z + 0.03), 'legno_travi')
                continue
            for t in range(5):
                _bx(det, M, (x0 + t * 0.32, 0.2, z), (x0 + t * 0.32 + 0.29, 2.6, z + 0.04), 'assi')
    for i in range(6):
        prism(det, [(yb - 0.05, 0.0), (yb - 0.02, 0.0), (yb - 0.02, 2.4), (yb - 0.35, 2.4)],
              0.3 + i * 0.32, 0.58 + i * 0.32, I['assi'], 'x', M)
    for (y, z) in ((2.45, 0.24), (2.95, 0.24), (2.7, 0.68)):   # tronchi da squadrare
        lathe(det, [(0.24, 0.0), (0.22, 3.0)], 12, I['legno_grezzo'], M @ T(0.5, y, z) @ RY(math.pi / 2))
    ob = oggetto("Falegname_dettagli", det, MB, coll); uv_finale(ob); smussa(ob, 0.008)

def forno(coll, pav):
    M, W, D = lotto(LOTTO_FORNO, 'E')
    det = nuovo_bm()
    yb = 4.3
    edificio("Forno", W - 0.4, D - yb - 0.2, 2, 'intonaco', 'lato', M @ T(0.2, yb, 0), coll, bottega=True,
             lati=(True, True))
    pav.pavimenta(M, 0.0, 0.0, W, yb)
    # forno esterno a cupola su basamento, bocca ad arco con la brace, comignolo
    cx, cy = W - 2.0, 2.2
    _bx(det, M, (cx - 1.4, cy - 1.4, 0), (cx + 1.4, cy + 1.4, 0.95), 'pietra_muro')
    Mc = M @ T(cx, cy, 0.95)
    lathe(det, [(1.25, 0.0)] + [(1.25 * math.cos(a), 1.15 * math.sin(a)) for a in [math.pi / 2 * i / 8 for i in range(1, 9)]],
          24, I['intonaco_bianco'], Mc, cap0=False)
    prism(det, arco_pts(cx - 0.4, cx + 0.4, 0.95, 1.6), cy - 1.3, cy - 1.18, I['interno_buio'], 'y', M)
    arco_rilievo(det, cx, 1.2, 0.4, 0.55, cy - 1.32, cy - 1.1, I['mattoni'], M=M)
    for _ in range(10):
        sfera(det, (cx + rr(-0.3, 0.3), cy - 1.33, 0.97 + rr(0, 0.05)), rr(0.03, 0.05), I['brace'], M, sub=1)
    _bx(det, M, (cx - 0.55, cy - 1.75, 0.85), (cx + 0.55, cy - 1.3, 0.95), 'pietra_cornici')
    luce_calda("Luce_forno", M @ Vector((cx, cy - 1.45, 1.15)), 40.0, coll)
    _bx(det, M, (cx - 0.15, cy - 0.95, 1.6), (cx + 0.15, cy - 0.65, 2.6), 'mattoni')
    catasta(det, cx - 1.3, cx + 1.3, cy + 1.45, cy + 1.95, 0.9, M)
    # pala da forno appoggiata, tavolo con il pane, ceste
    prism(det, [(cy - 1.5, 0.0), (cy - 1.45, 0.0), (cy - 0.6, 2.3), (cy - 0.65, 2.3)], cx + 1.45, cx + 1.5, I['legno_travi'], 'x', M)
    _bx(det, M, (cx + 1.42, cy - 1.75, 0.0), (cx + 1.52, cy - 1.35, 0.5), 'assi')
    _bx(det, M, (0.6, 1.2, 0.8), (2.8, 2.0, 0.86), 'assi')
    for x in (0.7, 2.6):
        for y in (1.25, 1.85):
            _bx(det, M, (x, y, 0), (x + 0.08, y + 0.08, 0.8), 'legno_travi')
    for i in range(7):
        sfera(det, (0.85 + i * 0.3, 1.6 + rr(-0.1, 0.1), 0.92), 0.08, I['pane'], M, sc=(1.6, 0.9, 0.7), rotz=rr(-0.3, 0.3))
    for (x, y) in ((0.9, 0.5), (1.6, 0.45), (3.2, 1.6)):
        cesta(det, x, y, 'pane', I, M)
    ob = oggetto("Forno_dettagli", det, MB, coll); uv_finale(ob); smussa(ob, 0.008)

def conceria(coll, pav):
    M, W, D = lotto(LOTTO_CONCERIA, 'N')
    det = nuovo_bm()
    yb = 5.4
    edificio("Conceria", W - 0.6, D - yb - 0.2, 2, 'pietra', 'lato', M @ T(0.3, yb, 0), coll, lati=(True, True))
    pav.pavimenta(M, 0.0, 0.0, W, yb)
    # vasche rotonde in pietra con calce, concia e tinture
    liquidi = ['calce', 'conciante', 'conciante', 'tintura_rossa', 'tintura_ocra', 'calce']
    for r_ in range(2):
        for c in range(6):
            x, y = 1.1 + c * 1.85, 0.95 + r_ * 1.75
            Mv = M @ T(x, y, 0)
            lathe(det, [(0.78, 0.0), (0.78, 0.45), (0.62, 0.45), (0.62, 0.05)], 20, I['pietra_muro'], Mv, chiuso=True)
            lathe(det, [(0.63, 0.25), (0.63, 0.32)], 20, I[liquidi[(c + 2 * r_) % len(liquidi)]], Mv)
    # rastrelliere con le pelli stese ad asciugare
    pelle = [(0.0, 0.1), (0.25, 0.0), (0.6, 0.05), (0.95, 0.0), (1.2, 0.12), (1.15, 0.5), (1.25, 0.85), (0.9, 0.95),
             (0.55, 0.88), (0.2, 0.95), (-0.05, 0.8), (0.05, 0.45)]
    for (x0, x1) in ((0.4, 5.6), (6.2, W - 0.4)):
        yr = yb - 0.8
        for x in (x0, x1):
            _bx(det, M, (x - 0.06, yr - 0.06, 0), (x + 0.06, yr + 0.06, 2.3), 'legno_travi')
        _bx(det, M, (x0, yr - 0.05, 2.2), (x1, yr + 0.05, 2.3), 'legno_travi')
        x = x0 + 0.15
        while x < x1 - 1.3:
            s = rr(0.85, 1.05)
            prism(det, [(x + u * s, 2.2 - v * 1.6 * s) for u, v in pelle], yr + 0.06, yr + 0.08, I['cuoio'], 'y', M)
            x += 1.35
    ob = oggetto("Conceria_dettagli", det, MB, coll); uv_finale(ob); smussa(ob, 0.008)

def pozzo(coll):
    """Pozzo degli artigiani: gradino ottagonale, vera in pietra con l'acqua, castello di legno con tettuccio,
    verricello con manovella, secchio; accanto un abbeveratoio e una panca."""
    det = nuovo_bm(); M = T(POZZO[0], POZZO[1], 0); f8 = math.pi / 8
    pc, lg = I['pietra_cornici'], I['legno_travi']
    lathe(det, [(1.6, 0.0), (1.6, 0.18), (1.25, 0.18)], 8, pc, M, liscio=False, fase=f8)
    lathe(det, [(1.0, 0.18), (1.0, 1.0), (1.08, 1.05), (1.08, 1.15), (0.78, 1.15), (0.78, 0.25)], 20, pc, M, chiuso=False)
    lathe(det, [(0.79, 0.55), (0.79, 0.6)], 20, I['acqua'], M)
    for sx in (-1, 1):
        _bx(det, M, (sx * 1.0 - 0.1, -0.1, 1.0), (sx * 1.0 + 0.1, 0.1, 3.0), 'legno_travi')
    _bx(det, M, (-1.2, -0.12, 3.0), (1.2, 0.12, 3.15), 'legno_travi')
    for sy in (-1, 1):   # tettuccio a due falde, colmo lungo la trave
        prism(det, [(sy * 0.9, 2.95), (0.0, 3.6), (0.0, 3.72), (sy * 0.9, 3.07)], -1.45, 1.45, I['coppi'], 'x', M)
    lathe(det, [(0.13, -0.9), (0.13, 0.9)], 14, I['legno_grezzo'], M @ T(0, 0, 2.45) @ RY(math.pi / 2))
    _bx(det, M, (1.0, -0.03, 2.42), (1.25, 0.03, 2.48), 'ferro')
    _bx(det, M, (1.22, -0.03, 2.2), (1.28, 0.03, 2.48), 'ferro')
    _bx(det, M, (-0.01, -0.01, 1.55), (0.01, 0.01, 2.33), 'juta')
    lathe(det, [(0.13, 1.25), (0.16, 1.55), (0.17, 1.57)], 12, I['legno_grezzo'], M, cap1=False)
    _bx(det, M, (1.9, -1.2, 0), (2.5, 0.9, 0.65), 'pietra_muro')
    _bx(det, M, (2.0, -1.1, 0.45), (2.4, 0.8, 0.58), 'acqua')
    _bx(det, M, (-2.6, -1.0, 0.42), (-2.25, 1.0, 0.5), 'pietra_cornici')
    for y in (-0.8, 0.7):
        _bx(det, M, (-2.55, y, 0), (-2.3, y + 0.12, 0.42), 'pietra_cornici')
    ob = oggetto("Pozzo_degli_Artigiani", det, MB, coll); uv_finale(ob); smussa(ob, 0.008)

def edifici_ruolo(coll):
    """Passo 4: gli edifici con un ruolo sui lotti riservati della pianta."""
    pav = Interno(coll, 999, "Ruoli", "Lastricati_ruoli")
    locanda(coll, pav); casa_mercante(coll, pav); fabbro(coll, pav)
    falegname(coll, pav); forno(coll, pav); conceria(coll, pav); pozzo(coll)
    pav.chiudi()

# ----------------------------------------------------------------------
#  MURA, TORRI E PORTE
#  Sistema locale di ogni tratto: x lungo le mura, +y verso l'esterno (mura in senso orario).
# ----------------------------------------------------------------------
def mura_orarie():
    a = sum(MURA[i][0] * MURA[(i + 1) % len(MURA)][1] - MURA[(i + 1) % len(MURA)][0] * MURA[i][1]
            for i in range(len(MURA)))
    return [Vector(p) for p in (MURA if a < 0 else MURA[::-1])]

def scosta_chiusa(pts, d):
    """Poligono chiuso parallelo a distanza d (sulle mura orarie: d > 0 fuori, d < 0 dentro)."""
    P = [Vector((p[0], p[1])) for p in pts]; n = len(P); out = []
    perp = lambda v: Vector((-v.y, v.x)).normalized()
    for k in range(n):
        n1 = perp(P[k] - P[k - 1]); m = (n1 + perp(P[(k + 1) % n] - P[k])).normalized()
        out.append(P[k] + m * (d / max(0.5, m.dot(n1))))
    return out

def _incrocio(p, q, a, b):
    """Parametri (t su pq, u su ab) dell'incrocio tra due segmenti, o None."""
    r = q - p; s = b - a; den = r.x * s.y - r.y * s.x
    if abs(den) < 1e-9:
        return None
    t = ((a.x - p.x) * s.y - (a.y - p.y) * s.x) / den
    u = ((a.x - p.x) * r.y - (a.y - p.y) * r.x) / den
    return (t, u) if 0 <= t <= 1 and 0 <= u <= 1 else None

def calcola_porte():
    """Dove le strade di PORTE attraversano le mura: nome, punto, tratto, ascissa, angolo, verso della strada."""
    MC = mura_orarie(); n = len(MC); res = []
    for (nome, larg, punti, _) in STRADE:
        if nome not in PORTE:
            continue
        P = [Vector(p) for p in punti]
        for p, q in zip(P, P[1:]):
            trovata = None
            for k in range(n):
                tu = _incrocio(p, q, MC[k], MC[(k + 1) % n])
                if tu:
                    trovata = (k, tu); break
            if trovata:
                k, (t, u) = trovata
                A, B = MC[k], MC[(k + 1) % n]
                res.append(dict(nome=PORTE[nome][0], stile=PORTE[nome][1], X=4.6 if PORTE[nome][1] == 'grande' else 3.6,
                                strada=nome, punto=p.lerp(q, t), k=k, s=u * (B - A).length,
                                ang=math.atan2(B.y - A.y, B.x - A.x), dir=(q - p).normalized()))
                break
    return res

def torre_angolo(det, c):
    """Torre rotonda a un vertice delle mura: scarpa, beccatelli, parapetto merlato, feritoie."""
    M = T(c.x, c.y, 0); R = 3.4; H = MURA_ALTEZZA + 3.4
    pb, pc = I['pietra_mura'], I['pietra_cornici']
    lathe(det, [(R + 0.7, -1.6), (R, 2.6), (R, H)], 28, pb, M, cap0=False)
    lathe(det, [(R + 0.36, H - 0.1), (R + 0.36, H + 0.25)], 28, pc, M)
    lathe(det, [(R + 0.3, H + 0.25), (R + 0.3, H + 1.0), (R - 0.3, H + 1.0), (R - 0.3, H + 0.25)], 28, pb, M,
          chiuso=True)
    for i in range(14):
        box(det, (R - 0.3, -0.42, H + 1.0), (R + 0.3, 0.42, H + 1.9), pb, M @ RZ(2 * math.pi * i / 14))
    for i in range(28):
        box(det, (R - 0.1, -0.12, H - 0.65), (R + 0.32, 0.12, H - 0.1), pc, M @ RZ(2 * math.pi * (i + 0.5) / 28))
    for i in range(6):   # feritoie (finte)
        for z in (3.4, 6.8):
            box(det, (R - 0.05, -0.06, z), (R + 0.02, 0.06, z + 1.1), I['interno_buio'],
                M @ RZ(2 * math.pi * i / 6 + 0.3 + z * 0.1))

def scala_mura(det, x0, M):
    """Scala addossata al lato interno delle mura, dalla strada di ronda al camminamento."""
    n = 25; h = MURA_ALTEZZA / n
    for i in range(n):
        box(det, (x0 + i * 0.42, -2.5, 0.0), (x0 + (i + 1) * 0.42, -1.2, (i + 1) * h), I['pietra_mura'], M)

def mura(coll, porte):
    """Cortina con scarpa, cornice, parapetto merlato e camminamento; torri ai vertici; varchi per le porte."""
    MC = mura_orarie(); n = len(MC); Z = MURA_ALTEZZA
    pm, pc = I['pietra_mura'], I['pietra_cornici']
    det = nuovo_bm()
    corpo = [(-1.2, -1.6), (2.1, -1.6), (1.3, 2.4), (1.3, Z), (-1.2, Z)]
    for k in range(n):
        A, B = MC[k], MC[(k + 1) % n]; L = (B - A).length
        M = T(A.x, A.y, 0) @ RZ(math.atan2(B.y - A.y, B.x - A.x))
        tratti = [(0.0, L)]
        for g in porte:
            if g['k'] == k:
                tratti = [(0.0, g['s'] - g['X']), (g['s'] + g['X'], L)]
        for (a, b) in tratti:
            prism(det, corpo, a, b, pm, 'x', M)
            prism(det, [(1.3, Z - 0.25), (1.5, Z - 0.25), (1.5, Z), (1.3, Z)], a, b, pc, 'x', M)
            prism(det, [(0.8, Z), (1.3, Z), (1.3, Z + 0.9), (0.8, Z + 0.9)], a, b, pm, 'x', M)
            x = a + 0.3
            while x + 0.9 < b - 0.3:   # merli guelfi
                box(det, (x, 0.8, Z + 0.9), (x + 0.9, 1.3, Z + 1.7), pm, M); x += 1.5
        if L > 30 and k % 2 == 0 and not any(g['k'] == k for g in porte):
            scala_mura(det, L / 2 - 5.0, M)
        torre_angolo(det, A)
    ob = oggetto("Mura", det, MB, coll); uv_finale(ob); smussa(ob)
    return ob

def ghiera(det, xa, zc, yf, verso, larg=0.5, mi=None):
    """Conci dell'arco e stipiti in pietra sulla facciata yf (verso = +1 fuori, -1 dentro)."""
    pc = I['pietra_cornici'] if mi is None else mi; zs = zc - xa; y1 = yf + verso * 0.15
    for i in range(12):
        a0, a1 = math.pi * i / 12, math.pi * (i + 1) / 12
        r1 = xa + larg + (0.12 if i in (5, 6) else 0.0)   # chiave di volta
        prism(det, [(xa * math.cos(a0), zs + xa * math.sin(a0)), (r1 * math.cos(a0), zs + r1 * math.sin(a0)),
                    (r1 * math.cos(a1), zs + r1 * math.sin(a1)), (xa * math.cos(a1), zs + xa * math.sin(a1))],
              yf, y1, pc, 'y')
    for sx in (-1, 1):
        box(det, (sx * xa, yf, 0.0), (sx * (xa + larg), y1, zs), pc)

def coronamento(det, x0, y0, x1, y1, H, mi):
    """Beccatelli, parapetto aggettante e merli guelfi sopra un corpo rettangolare alto H."""
    pc = I['pietra_cornici']; zb = H - 0.6
    for i in range(int((x1 - x0 - 0.4) / 0.6) + 1):
        xx = x0 + 0.3 + 0.6 * i
        box(det, (xx - 0.12, y1 - 0.02, zb), (xx + 0.12, y1 + 0.4, H), pc)
        box(det, (xx - 0.12, y0 - 0.4, zb), (xx + 0.12, y0 + 0.02, H), pc)
    for i in range(int((y1 - y0 - 0.4) / 0.6) + 1):
        yy = y0 + 0.3 + 0.6 * i
        box(det, (x1 - 0.02, yy - 0.12, zb), (x1 + 0.4, yy + 0.12, H), pc)
        box(det, (x0 - 0.4, yy - 0.12, zb), (x0 + 0.02, yy + 0.12, H), pc)
    for (a, b) in [((x0 - 0.45, y0 - 0.45), (x1 + 0.45, y0 + 0.1)), ((x0 - 0.45, y1 - 0.1), (x1 + 0.45, y1 + 0.45)),
                   ((x0 - 0.45, y0 - 0.45), (x0 + 0.1, y1 + 0.45)), ((x1 - 0.1, y0 - 0.45), (x1 + 0.45, y1 + 0.45))]:
        box(det, (a[0], a[1], H), (b[0], b[1], H + 0.8), mi)
    x = x0 - 0.45
    while x < x1 + 0.4:
        xb = min(x + 0.85, x1 + 0.45)
        box(det, (x, y1 - 0.1, H + 0.8), (xb, y1 + 0.45, H + 1.7), mi)
        box(det, (x, y0 - 0.45, H + 0.8), (xb, y0 + 0.1, H + 1.7), mi)
        x += 1.4
    y = y0 - 0.45 + 1.4
    while y < y1 - 0.5:
        for (xa, xb) in ((x1 - 0.1, x1 + 0.45), (x0 - 0.45, x0 + 0.1)):
            box(det, (xa, y, H + 0.8), (xb, min(y + 0.85, y1 - 0.1), H + 1.7), mi)
        y += 1.4

def porta(g, coll):
    """Torre-porta. 'grande': alta, beccatelli e merli, stemma a pali e stendardi, padiglione dentro i merli.
    'sobria': piu' bassa e stretta, tetto a falde in coppi, stemma crociato. Entrambe con portone aperto,
    saracinesca sollevata e ponte di legno sul fossato."""
    G = g['punto']; M = T(G.x, G.y, 0) @ RZ(g['ang'])
    pm, pc, fe, lg = I['pietra_mura'], I['pietra_cornici'], I['ferro'], I['legno_travi']
    grande = g['stile'] == 'grande'
    X = g['X']
    Y0, Y1, H = (-3.2, 3.6, 13.5) if grande else (-2.6, 3.0, 10.4)
    xa, zc = (2.3, 6.4) if grande else (1.9, 5.4)
    det = nuovo_bm(); parti = []
    tg = [(arco_pts(-xa, xa, -0.3, zc), Y0 - 0.5, Y1 + 0.5, 'y', pm)]
    parti.append(guscio(g['nome'] + "_corpo", lambda bm: box(bm, (-X, Y0, -1.6), (X, Y1, H), pm), tg, coll))
    for (yf, verso) in ((Y1, 1), (Y0, -1)):
        ghiera(det, xa, zc, yf, verso, 0.5 if grande else 0.4)
    box(det, (-X - 0.15, Y0 - 0.15, MURA_ALTEZZA - 0.25), (X + 0.15, Y1 + 0.15, MURA_ALTEZZA), pc)
    # saracinesca sollevata: si vedono le punte sotto la volta
    yp = Y1 - (0.9 if grande else 0.8); zp = zc - 1.5
    x = -xa + 0.15
    while x < xa:
        box(det, (x - 0.045, yp - 0.045, zp), (x + 0.045, yp + 0.045, zp + 4.1), fe)
        lathe(det, [(0.05, zp), (0.006, zp - 0.35)], 4, fe, T(x, yp, 0), liscio=False)
        x += 0.38
    for k in range(4):
        z = zp + 0.25 + 0.5 * k
        box(det, (-xa - 0.1, yp - 0.05, z), (xa + 0.1, yp + 0.05, z + 0.08), fe)
    for sx in (-1, 1):   # gargami della saracinesca
        xs = sorted((sx * xa, sx * (xa - 0.03)))
        box(det, (xs[0], yp - 0.12, 0.0), (xs[1], yp + 0.12, zp), I['interno_buio'])
    # portone a due battenti, aperto verso l'interno contro le pareti del passaggio
    yc = yp - 0.4; hb = zc - xa - 0.1; lb = xa - 0.05
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (xa - 0.04), sx * (xa - 0.16)))
        box(det, (x0, yc - lb, 0.02), (x1, yc, hb), I['assi'])
        xi0, xi1 = sorted((sx * (xa - 0.16), sx * (xa - 0.2)))
        for z in (0.6, hb / 2, hb - 0.6):
            box(det, (xi0, yc - lb + 0.05, z), (xi1, yc - 0.05, z + 0.1), fe)
    if grande:
        coronamento(det, -X, Y0, X, Y1, H, pm)
        ap = piramide(det, -X + 0.15, Y0 + 0.15, X - 0.15, Y1 - 0.15, H + 0.05, 3.2, I['coppi'])
        lathe(det, [(0.04, ap.z - 0.3), (0.04, ap.z + 2.4)], 8, fe, T(ap.x, ap.y, 0))
        stendardo(det, ap.x + 0.65, ap.y, ap.z + 2.35, larg=1.2, alt=0.75, onda=0.12)
        # stemma a pali sopra l'arco e due stendardi appesi
        scudo = [(-0.8, 10.4), (0.8, 10.4), (0.8, 9.2), (0.5, 8.6), (0.0, 8.3), (-0.5, 8.6), (-0.8, 9.2)]
        prism(det, [(x * 1.18, 9.35 + (z - 9.35) * 1.18) for x, z in scudo], Y1, Y1 + 0.1, pc, 'y')
        prism(det, scudo, Y1 + 0.1, Y1 + 0.16, I['stendardo'], 'y')
        box(det, (-1.2, Y1, 10.75), (1.2, Y1 + 0.28, 10.95), pc)
        for xb in (-2.7, 2.7):
            stendardo(det, xb, Y1 + 0.55, 12.4, larg=0.9, alt=3.2)
            box(det, (xb - 0.04, Y1, 12.4), (xb + 0.04, Y1 + 0.55, 12.48), fe)
        fuori = [(3.4, 0.22, 8.0, 9.4), (-3.4, 0.22, 8.0, 9.4)]
        dentro = [(1.8, 0.8, 9.0, 10.4), (-1.8, 0.8, 9.0, 10.4)]
    else:
        # gronda e tetto a due falde in coppi, col timpano verso la campagna
        box(det, (-X - 0.2, Y0 - 0.2, H - 0.22), (X + 0.2, Y1 + 0.2, H), pc)
        CM[0] = T(-X, 0, 0)
        try:
            zr = tetto_fronte(det, 2 * X, Y0 + 0.2, Y1 - 0.2, H, math.radians(33), 'coppi', False)
            for (y0, y1) in ((Y0, Y0 + 0.3), (Y1 - 0.3, Y1)):
                prism(det, [(0, H), (2 * X, H), (X, zr)], y0, y1, pm, 'y')
        finally:
            CM[0] = None
        # stemma sannitico, crema con croce rossa
        scudo = [(-0.65, 8.9), (0.65, 8.9)] + [(0.65 * math.cos(-math.pi * i / 8), 7.8 + 0.7 * math.sin(-math.pi * i / 8))
                                               for i in range(9)]
        prism(det, [(x * 1.2, 8.0 + (z - 8.0) * 1.2) for x, z in scudo], Y1, Y1 + 0.08, pc, 'y')
        prism(det, scudo, Y1 + 0.08, Y1 + 0.14, I['festone_crema'], 'y')
        box(det, (-0.1, Y1 + 0.14, 7.25), (0.1, Y1 + 0.18, 8.75), I['festone_rosso'])
        box(det, (-0.55, Y1 + 0.14, 8.05), (0.55, Y1 + 0.18, 8.25), I['festone_rosso'])
        fuori = [(2.5, 0.2, 7.2, 8.3), (-2.5, 0.2, 7.2, 8.3)]
        dentro = [(0.0, 0.7, 7.3, 8.5)]
    # feritoie verso fuori, finestre verso il borgo
    for (Mf, aperture_) in ((T(0, Y1, 0) @ RZ(math.pi), fuori), (T(0, Y0, 0), dentro)):
        CM[0] = Mf
        try:
            for (xc, w, zA, zB) in aperture_:
                finestra_finta(det, xc, w, zA, zB, 'assi' if w > 0.5 else None)
        finally:
            CM[0] = None
    if FOSSATO:   # ponte di legno sul fossato
        bw = 2.5 if grande else 2.0; bt = bw - 0.7
        y = Y1
        while y < 14.2:
            box(det, (-bw, y, 0.0), (bw, y + 0.28, 0.12 + rr(-0.012, 0.012)), I['assi']); y += 0.3
        for sx in (-1, 1):
            box(det, (sx * bt - 0.15, Y1, -0.45), (sx * bt + 0.15, 14.2, 0.0), lg)
            for yy in (6.2, 8.7, 11.2):
                box(det, (sx * bt - 0.15, yy - 0.15, -1.7), (sx * bt + 0.15, yy + 0.15, -0.45), lg)
            for yy in (Y1 + 0.4, 6.2, 8.7, 11.2, 13.9):
                box(det, (sx * (bw - 0.08) - 0.07, yy - 0.07, 0.12), (sx * (bw - 0.08) + 0.07, yy + 0.07, 1.1), lg)
            box(det, (sx * (bw - 0.08) - 0.06, Y1 + 0.3, 1.0), (sx * (bw - 0.08) + 0.06, 14.0, 1.12), lg)
    parti.append(oggetto(g['nome'] + "_det", det, MB, coll))
    ob = unisci(parti, g['nome'])
    uv_finale(ob); ob.matrix_world = M; smussa(ob)
    return ob

def dist_mura(p):
    MC = mura_orarie(); best = 1e9
    for k in range(len(MC)):
        a, b = MC[k], MC[(k + 1) % len(MC)]; ab = b - a
        t = max(0.0, min(1.0, (Vector(p) - a).dot(ab) / ab.length_squared))
        best = min(best, (Vector(p) - a - ab * t).length)
    return best

def vegetazione(coll, porte):
    """Alberi e cespugli in campagna, piu' fitti lungo le strade sterrate; un cono libero davanti a ogni
    porta perche' nessun albero la copra."""
    MC = mura_orarie()
    blocchi = []; stato = {'det': nuovo_bm(), 'n': 0}
    def pianta(fn, M, scala):
        # mesh piccole: la creazione delle sfere rallenta man mano che la mesh cresce
        fn(stato['det'], M, scala); stato['n'] += 1
        if stato['n'] % 25 == 0:
            blocchi.append(oggetto(f"Vegetazione_{len(blocchi):02d}", stato['det'], MB, coll)); stato['det'] = nuovo_bm()
    strade = []
    for g in porte:
        n = Vector((-math.sin(g['ang']), math.cos(g['ang'])))
        strade.append((g['punto'], n, g['punto'] + n * 14.0, g['dir']))
    def posto_ok(p, alto):
        if dentro_poligono(p, MC) or dist_mura(p) < (18.0 if alto else 16.0):
            return False
        for (G, n, s0, d) in strade:
            v = Vector(p) - G
            lungo = v.dot(n); lato = abs(v.dot(Vector((-n.y, n.x))))
            if 0 < lungo < (110 if alto else 45) and lato < 8.0 + lungo * 0.4:   # cono di vista della porta
                return False
            w = Vector(p) - s0; t = max(0.0, min(60.0, w.dot(d)))
            if (w - d * t).length < 3.6:                                 # carreggiata
                return False
        return True
    xs = [p.x for p in MC]; ys = [p.y for p in MC]
    box_ = (min(xs) - 70, min(ys) - 70, max(xs) + 70, max(ys) + 70)
    for _ in range(420):   # sparsi
        p = (rr(box_[0], box_[2]), rr(box_[1], box_[3]))
        alto = RNG.random() < 0.3
        if posto_ok(p, alto):
            pianta(albero if alto else cespuglio, T(p[0], p[1], 0) @ RZ(rr(0, 6.3)), rr(1.1, 1.6) if alto else 1.0)
    for _ in range(5):   # oliveti a filari
        c = Vector((rr(box_[0], box_[2]), rr(box_[1], box_[3]))); a = rr(0, math.pi)
        e = Vector((math.cos(a), math.sin(a))); f = Vector((-e.y, e.x))
        for i in range(-3, 4):
            for j in range(-2, 3):
                q = c + e * (i * 7.5 + rr(-0.6, 0.6)) + f * (j * 7.5 + rr(-0.6, 0.6))
                if posto_ok(tuple(q), True):
                    albero(None, T(q.x, q.y, 0), rr(1.0, 1.3), 'island_tree_02')
    for (G, n, s0, d) in strade:   # lungo le strade sterrate
        for t in [6.0 + 3.2 * i for i in range(17)]:
            for lato in (-1, 1):
                q = s0 + d * t + Vector((-d.y, d.x)) * lato * rr(3.8, 6.5)
                alto = t > 30 and RNG.random() < 0.45
                if RNG.random() < 0.75 and posto_ok(tuple(q), alto):
                    pianta(albero if alto else cespuglio, T(q.x, q.y, 0) @ RZ(rr(0, 6.3)), rr(1.0, 1.4) if alto else 1.0)
    # niente UV: chiome a tinta unita, tronchi a colore medio
    blocchi.append(oggetto(f"Vegetazione_{len(blocchi):02d}", stato['det'], MB, coll))
    return blocchi

# ----------------------------------------------------------------------
#  PIAZZA, FONTANA, MERCATO, OGGETTI
# ----------------------------------------------------------------------
def nastro(bm, punti, hw, z, rng):
    """Striscia lastricata lungo una polilinea, con i bordi leggermente irregolari."""
    sx = [Vector(p) for p in scosta(punti, hw)]; dx = [Vector(p) for p in scosta(punti, -hw)]
    prec = None
    for k in range(len(punti) - 1):
        n = max(1, int((Vector(punti[k + 1]) - Vector(punti[k])).length / 1.2))
        for i in range(0 if k == 0 else 1, n + 1):
            t = i / n
            a = sx[k].lerp(sx[k + 1], t); b = dx[k].lerp(dx[k + 1], t)
            u = (a - b).normalized()
            a = a + u * rng.uniform(-0.08, 0.2); b = b - u * rng.uniform(-0.08, 0.2)
            cur = (bm.verts.new((a.x, a.y, z)), bm.verts.new((b.x, b.y, z)))
            if prec:
                bm.faces.new((prec[1], cur[1], cur[0], prec[0]))
            prec = cur

def anello(bm, A, B, zA, zB, rng=None, jit=0.0, passo=None):
    """Striscia chiusa tra due poligoni con lo stesso numero di vertici; bordo A irregolare se rng."""
    n = len(A); prec = primo = None
    for k in range(n):
        a0, a1, b0, b1 = A[k], A[(k + 1) % n], B[k], B[(k + 1) % n]
        m = max(1, int((a1 - a0).length / passo)) if passo else 1
        for i in range(m):
            a = a0.lerp(a1, i / m); b = b0.lerp(b1, i / m)
            if rng:
                a = a + (a - b).normalized() * rng.uniform(-0.4 * jit, jit)
            cur = (bm.verts.new((a.x, a.y, zA)), bm.verts.new((b.x, b.y, zB)))
            if prec:
                bm.faces.new((prec[0], prec[1], cur[1], cur[0]))
            else:
                primo = cur
            prec = cur
    bm.faces.new((prec[0], prec[1], primo[1], primo[0]))

def in_su(bm):
    for f in bm.faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()

def fino_alle_mura(punti, oltre):
    """La polilinea fino al punto in cui attraversa le mura, piu' 'oltre' metri."""
    MC = mura_orarie(); P = [Vector(p) for p in punti]; out = [P[0]]
    for p, q in zip(P, P[1:]):
        for k in range(len(MC)):
            tu = _incrocio(p, q, MC[k], MC[(k + 1) % len(MC)])
            if tu:
                out.append(p.lerp(q, tu[0]) + (q - p).normalized() * oltre)
                return [tuple(v) for v in out]
        out.append(q)
    return [tuple(v) for v in out]

def terreno(coll, porte):
    """Selciato su piazza, sagrato, piazzetta e strade; suolo erboso dentro le mura con la strada di ronda
    in terra battuta; fuori una fascia di terra, il fossato asciutto, la campagna e le strade sterrate."""
    rng = random.Random(SEED + 1)    # generatore a parte: non altera la sequenza delle case
    MC = mura_orarie()
    bm = nuovo_bm()
    for (x0, y0, x1, y1) in [(-PIAZZA_X - 0.5, -PIAZZA_Y - 0.5, PIAZZA_X + 0.5, PIAZZA_Y + 0.5),
                             SAGRATO, PIAZZETTA_POZZO]:
        bm.faces.new([bm.verts.new((x, y, 0.02)) for (x, y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))])
    for k, (nome, larg, punti, _) in enumerate(STRADE):
        nastro(bm, fino_alle_mura(punti, 3.0), larg / 2, 0.021 + 0.001 * k, rng)
    ob = oggetto("Selciato", bm, ['selciato'], coll, ricalcola=False)
    uv_finale(ob)
    # suolo dentro le mura
    bm = nuovo_bm()
    bm.faces.new([bm.verts.new((p.x, p.y, 0.0)) for p in scosta_chiusa(MC, -3.0)])
    in_su(bm); uv_finale(oggetto("Suolo", bm, ['terra_erbosa'], coll, ricalcola=False))
    # strada di ronda (bordo interno irregolare), sotto le mura e fascia esterna di 1-2 m
    bm = nuovo_bm()
    est = 3.4 if FOSSATO else 5.0
    anello(bm, scosta_chiusa(MC, -5.0), scosta_chiusa(MC, est), 0.008, 0.008, rng, 0.6, 1.0)
    for g in porte:   # strada sterrata verso la campagna
        n = Vector((-math.sin(g['ang']), math.cos(g['ang'])))
        p0 = g['punto'] + n * (14.0 if FOSSATO else est)
        nastro(bm, [tuple(p0), tuple(p0 + g['dir'] * 60.0)], 2.4, 0.012, rng)
    in_su(bm); uv_finale(oggetto("Strada_di_ronda", bm, ['terra'], coll, ricalcola=False))
    # fossato asciutto e campagna
    bm = nuovo_bm()
    anelli = [(est, 0.0)] + ([(6.0, -1.4), (11.0, -1.4), (13.5, 0.0)] if FOSSATO else [])
    for (d0, z0), (d1, z1) in zip(anelli, anelli[1:]):
        anello(bm, scosta_chiusa(MC, d0), scosta_chiusa(MC, d1), z0, z1)
    in_su(bm)
    if len(bm.faces):
        uv_finale(oggetto("Fossato", bm, ['terra_fossato'], coll, ricalcola=False))
    else:
        bm.free()
    bm = nuovo_bm()
    bordo = scosta_chiusa(MC, anelli[-1][0])
    c = sum(bordo, Vector((0, 0))) / len(bordo)
    anello(bm, bordo, [c + (p - c).normalized() * 2500.0 for p in bordo], 0.0, 0.0)
    in_su(bm); uv_finale(oggetto("Campagna", bm, ['prato'], coll, ricalcola=False))
    return ob

def curva(nome, tratti, raggio, mat, coll):
    cu = bpy.data.curves.new(nome, 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = raggio; cu.bevel_resolution = 2
    for pts in tratti:
        sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
        for p, c in zip(sp.points, pts):
            p.co = (c[0], c[1], c[2], 1.0)
    cu.materials.append(MAT[mat])
    ob = bpy.data.objects.new(nome, cu); coll.objects.link(ob)
    return ob

def getto(p0, p1, alza=0.1, n=14):
    out = []
    for i in range(n + 1):
        t = i / n
        x = p0[0] + (p1[0] - p0[0]) * t; y = p0[1] + (p1[1] - p0[1]) * t
        z = p0[2] + alza * t - (p0[2] - p1[2] + alza) * t * t
        out.append((x, y, z))
    return out

def fontana(coll):
    mats = ['pietra_cornici', 'pietra_blocchi', 'acqua', 'ferro']
    bm = nuovo_bm(); f8 = math.pi / 8
    lathe(bm, [(3.6, -0.05), (3.6, 0.14), (3.25, 0.14), (3.25, 0.28)], 8, 0, liscio=False, fase=f8)
    lathe(bm, [(2.75, 0.27), (2.8, 0.75), (2.92, 0.8), (2.92, 0.92), (2.42, 0.92), (2.42, 0.8),
               (2.48, 0.75), (2.45, 0.27)], 8, 0, chiuso=True, liscio=False, fase=f8)
    lathe(bm, [(2.47, 0.6), (2.47, 0.66)], 8, 2, liscio=False, fase=f8)
    lathe(bm, [(0.6, 0.27), (0.6, 0.45), (0.45, 0.55), (0.32, 0.7), (0.26, 0.9), (0.24, 1.7), (0.3, 1.8),
               (0.5, 1.9), (0.9, 2.05), (1.15, 2.15), (1.18, 2.25), (1.1, 2.27), (1.05, 2.27)], 32, 0)
    lathe(bm, [(1.07, 2.24), (1.07, 2.29)], 32, 2)
    lathe(bm, [(0.22, 2.27), (0.16, 2.4), (0.14, 2.9), (0.2, 3.0), (0.26, 3.05), (0.14, 3.12), (0.1, 3.3)], 24, 0)
    sfera(bm, (0, 0, 3.42), 0.16, 0)
    tratti = []
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        c, s = math.cos(a), math.sin(a)
        box(bm, (0, -0.025, 2.82), (0.38, 0.025, 2.87), 3, RZ(a))
        tratti.append(getto((0.38 * c, 0.38 * s, 2.84), (0.85 * c, 0.85 * s, 2.28), 0.06))
    for i in range(8):
        a = i * math.pi / 4
        c, s = math.cos(a), math.sin(a)
        tratti.append(getto((1.18 * c, 1.18 * s, 2.24), (1.55 * c, 1.55 * s, 0.64), 0.02))
        a2 = a + math.pi / 8; c2, s2 = math.cos(a2), math.sin(a2)
        tratti.append(getto((1.17 * c2, 1.17 * s2, 2.24), (1.5 * c2, 1.5 * s2, 0.64), 0.015))
    ob = oggetto("Fontana", bm, mats, coll); uv_finale(ob); smussa(ob, 0.01)
    curva("Fontana_getti", tratti, 0.014, 'acqua_getto', coll)
    return ob

def cassetta(bm, w, d, h, mi, M):
    t = 0.02
    box(bm, (0, 0, 0), (w, d, t), mi, M)
    box(bm, (0, 0, 0), (w, t, h), mi, M); box(bm, (0, d - t, 0), (w, d, h), mi, M)
    box(bm, (0, 0, 0), (t, d, h), mi, M); box(bm, (w - t, 0, 0), (w, d, h), mi, M)

RAGGI = {'mela': 0.042, 'arancia': 0.046, 'limone': 0.04, 'cavolo': 0.085, 'pane': 0.07,
         'zucca': 0.1, 'uva': 0.03, 'formaggio': 0.13}

def riempi(bm, w, d, prod, mi, M):
    if prod == 'formaggio':
        for k in range(2):
            for xx in (w * 0.27, w * 0.73):
                lathe(bm, [(0.12, 0.02 + k * 0.09), (0.12, 0.1 + k * 0.09)], 20, mi, M @ T(xx, d / 2, 0))
        return
    r = RAGGI[prod]
    nx = max(1, int((w - 0.04) / (2 * r))); ny = max(1, int((d - 0.04) / (2 * r)))
    for layer in range(2):
        for ix in range(nx - layer):
            for iy in range(ny - layer):
                if layer and RNG.random() < 0.35:
                    continue
                x = 0.02 + r + ix * 2 * r + layer * r + rr(-0.15, 0.15) * r
                y = 0.02 + r + iy * 2 * r + layer * r + rr(-0.15, 0.15) * r
                z = 0.02 + r * 0.9 + layer * r * 1.45
                if prod == 'pane':
                    sfera(bm, (x, y, z), r, mi, M, sc=(1.6, 0.85, 0.7), rotz=rr(-0.4, 0.4))
                elif prod == 'cavolo':
                    sfera(bm, (x, y, z), r, mi, M, sc=(1, 1, 0.85))
                else:
                    sfera(bm, (x, y, z), r, mi, M, sc=(1, 1, rr(0.88, 1.0)))

def cesta(bm, x, y, prod, Il, M=None):
    Mb = T(x, y, 0) if M is None else M @ T(x, y, 0)
    lathe(bm, [(0.16, 0.0), (0.21, 0.12), (0.24, 0.22), (0.25, 0.24)], 18, Il['vimini'], Mb, cap1=False)
    r = RAGGI.get(prod, 0.045)
    for _ in range(int(0.1 / (r * r)) // 3 + 4):
        a = rr(0, 2 * math.pi); d = rr(0, 0.2 - r)
        sfera(bm, (d * math.cos(a), d * math.sin(a), 0.17 + rr(0, 0.05)), r, Il[prod], Mb)

def botte(bm, x, y, mi_l, mi_f, M=None, h=0.9, sdraiata=False):
    Mb = T(x, y, 0)
    if sdraiata:
        Mb = Mb @ T(0, 0, 0.31) @ RY(math.pi / 2) @ T(0, 0, -h / 2)
    if M is not None:
        Mb = M @ Mb
    prof = [(0.26 + 0.045 * math.sin(math.pi * k / 8), h * k / 8) for k in range(9)]
    lathe(bm, prof, 20, mi_l, Mb)
    for zz in (0.1, 0.28, h - 0.33, h - 0.15):
        r = 0.26 + 0.045 * math.sin(math.pi * zz / h)
        lathe(bm, [(r + 0.004, zz), (r + 0.014, zz), (r + 0.014, zz + 0.05), (r + 0.004, zz + 0.05)],
              20, mi_f, Mb, chiuso=True)

def sacco(bm, x, y, mi, M=None, rot=0.0):
    """Sacco di juta: fondo piatto, pancia, collo legato."""
    Mb = T(x, y, 0) @ RZ(rot) @ Matrix.Diagonal((1.0, 0.82, 1.0, 1.0))
    if M is not None:
        Mb = M @ Mb
    h = rr(0.5, 0.65)
    prof = [(0.2, 0.0), (0.27, 0.05), (0.29, 0.18), (0.28, h * 0.55), (0.23, h * 0.8), (0.14, h * 0.94),
            (0.03, h)]
    seg = 16
    anelli = []
    for (r, z) in prof:
        anello = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            rj = r * (1 + 0.1 * math.sin(3 * a + z * 9 + rot) + 0.05 * math.sin(7 * a - z * 13) + rr(-0.04, 0.04))
            anello.append(bm.verts.new(Mb @ Vector((rj * math.cos(a), rj * math.sin(a), z))))
        anelli.append(anello)
    fs = []
    for A, B in zip(anelli, anelli[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            fs.append(bm.faces.new((A[i], A[j], B[j], B[i])))
    fs.append(bm.faces.new(anelli[0][::-1])); fs.append(bm.faces.new(anelli[-1]))
    for f in fs:
        f.material_index = mi; f.smooth = True

def bancarella(nome, M, telo, coll):
    L, P = 2.6, 1.5
    prodotti = ['mela', 'arancia', 'limone', 'cavolo', 'pane', 'zucca', 'uva', 'formaggio']
    mats = ['assi', 'legno_travi', 'legno_grezzo', telo, 'ferro', 'juta', 'vimini'] + prodotti
    Il = {n: i for i, n in enumerate(mats)}
    bm = nuovo_bm(); lt = Il['legno_travi']
    for (x, y, h) in [(0, 0, 2.15), (L - 0.09, 0, 2.15), (0, P - 0.09, 2.5), (L - 0.09, P - 0.09, 2.5)]:
        box(bm, (x, y, 0), (x + 0.09, y + 0.09, h), lt)
    box(bm, (0, 0, 2.05), (L, 0.09, 2.15), lt); box(bm, (0, P - 0.09, 2.42), (L, P, 2.5), lt)
    box(bm, (0.05, 0.0, 0.84), (L - 0.05, 1.05, 0.9), Il['assi'])
    box(bm, (0.05, -0.02, 0.25), (L - 0.05, 0.02, 0.84), Il['assi'])
    box(bm, (0.05, 0.9, 0.3), (L - 0.05, 0.95, 0.84), Il['assi'])
    scelta = RNG.sample(prodotti, 3)
    nc = 4; cw = 0.56; gap = (L - 0.1 - nc * cw) / (nc + 1)
    for c in range(nc):
        x0 = 0.05 + gap + c * (cw + gap)
        Mc = T(x0, 0.22, 0.9) @ RX(math.radians(12))
        cassetta(bm, cw, 0.42, 0.15, Il['legno_grezzo'], Mc)
        riempi(bm, cw, 0.42, scelta[c % 3], Il[scelta[c % 3]], Mc)
    # telo
    nu, nv = 16, 6; zb, zf = 2.62, 2.12; yb, yf = P + 0.2, -0.55
    grid = []
    for i in range(nu + 1):
        u = i / nu; x = -0.15 + u * (L + 0.3); col = []
        for jv in range(nv + 1):
            v = jv / nv; y = yb + (yf - yb) * v
            z = zb + (zf - zb) * v - 0.07 * math.sin(math.pi * u) * (0.4 + 0.6 * math.sin(math.pi * v))
            col.append(bm.verts.new((x, y, z)))
        grid.append(col)
    for i in range(nu):
        for jv in range(nv):
            f = bm.faces.new((grid[i][jv], grid[i + 1][jv], grid[i + 1][jv + 1], grid[i][jv + 1]))
            f.material_index = Il[telo]; f.smooth = True
    basso = []
    for i in range(nu + 1):
        u = i / nu; t = grid[i][nv].co
        basso.append(bm.verts.new((t.x, t.y, t.z - 0.2 - 0.06 * abs(math.sin(math.pi * u * 7)))))
    for i in range(nu):
        f = bm.faces.new((grid[i][nv], grid[i + 1][nv], basso[i + 1], basso[i]))
        f.material_index = Il[telo]; f.smooth = True
    # oggetti a terra
    cesta(bm, rr(0.3, 0.7), -0.45, rc(['mela', 'arancia', 'limone', 'cavolo']), Il)
    if RNG.random() < 0.6:
        cesta(bm, rr(1.8, 2.3), -0.5, rc(['mela', 'arancia', 'pane']), Il)
    for _ in range(RNG.randint(1, 3)):
        sacco(bm, rr(L + 0.25, L + 0.5), rr(0.2, 1.2), Il['juta'], rot=rr(0, 3))
    if RNG.random() < 0.6:
        botte(bm, -0.4, rr(0.4, 1.1), Il['legno_grezzo'], Il['ferro'])
    if 'zucca' in scelta:
        for _ in range(4):
            sfera(bm, (rr(0.2, L - 0.2), rr(0.2, 0.8), 0.15), 0.17, Il['zucca'], sc=(1, 1, 0.75))
    ob = oggetto(nome, bm, mats, coll)
    uv_finale(ob); ob.matrix_world = M; smussa(ob, 0.008)
    return ob

def mercato(coll):
    ang0 = rr(0, 0.3); pos = []
    for i in range(N_BANCARELLE):
        a = ang0 + 2 * math.pi * i / N_BANCARELLE + rr(-0.05, 0.05)
        p = Vector((10.3 * math.cos(a), 7.6 * math.sin(a), 0))
        r = Vector((p.x / 10.3 ** 2, p.y / 7.6 ** 2, 0)).normalized()
        x = r.cross(Vector((0, 0, 1)))
        Mw = Matrix.Translation(p - x * 1.3) @ RZ(math.atan2(x.y, x.x))
        c1, c2 = TELI[i % len(TELI)]
        nome_t = f"telo_{i:02d}"
        tessuto(nome_t, c1, c2)
        bancarella(f"Bancarella_{i:02d}", Mw, nome_t, coll)
        pos.append((p, r))
    return pos

def in_piazza(M, W, margine=1.0):
    c = M @ Vector((W / 2, 0, 0))
    return abs(c.x) < PIAZZA_X + 0.5 - margine and abs(c.y) < PIAZZA_Y + 0.5 - margine or \
        (abs(abs(c.x) - PIAZZA_X) < 0.6 and abs(c.y) < PIAZZA_Y - margine) or \
        (abs(abs(c.y) - PIAZZA_Y) < 0.6 and abs(c.x) < PIAZZA_X - margine)

def vaso(bm, x, y, Il, M):
    Mv = M @ T(x, y, 0)
    s = rr(0.8, 1.25)
    lathe(bm, [(0.14 * s, 0.0), (0.18 * s, 0.05), (0.22 * s, 0.38 * s), (0.25 * s, 0.42 * s),
               (0.25 * s, 0.47 * s), (0.21 * s, 0.47 * s)], 18, Il['terracotta'], Mv)
    fiore = Il[rc(['fiori_rossi', 'fiori_viola'])] if RNG.random() < 0.5 else Il['foglie']
    zc = 0.47 * s + 0.25 * s
    for _ in range(int(40 * s)):
        a = rr(0, 2 * math.pi); r = rr(0, 0.27 * s); h = rr(-0.22, 0.25) * s
        mi = fiore if (h > 0.1 * s and RNG.random() < 0.4) else Il['foglie']
        sfera(bm, (r * math.cos(a), r * math.sin(a), zc + h), rr(0.06, 0.11) * s, mi, Mv, sub=1)

def oggetti_scena(coll, facciate):
    mats = ['legno_grezzo', 'ferro', 'juta', 'vimini', 'assi', 'legno_travi', 'mela', 'cavolo', 'arancia', 'pane',
            'terracotta', 'foglie', 'fiori_rossi', 'fiori_viola']
    Il = {n: i for i, n in enumerate(mats)}
    bm = nuovo_bm()
    facciate = [f for f in facciate if in_piazza(f[0], f[1])]
    for (M, W, stile, bottega, n) in facciate:
        if RNG.random() < 0.55:
            for q in range(RNG.randint(1, 2)):
                vaso(bm, rr(0.4, W - 0.4), -0.45, Il, M)
        if RNG.random() < (0.7 if bottega else 0.3):
            x = rr(0.6, W - 0.6)
            k = RNG.randint(1, 3)
            for q in range(k):
                botte(bm, x + q * 0.62, -0.55 - rr(0, 0.15), Il['legno_grezzo'], Il['ferro'], M)
            if RNG.random() < 0.6:
                xx = x + k * 0.62 + 0.2
                box(bm, (xx, -0.95, 0), (xx + 0.6, -0.5, 0.42), Il['legno_grezzo'], M)
                if RNG.random() < 0.5:
                    box(bm, (xx + 0.05, -0.92, 0.42), (xx + 0.55, -0.53, 0.8), Il['legno_grezzo'], M)
            if RNG.random() < 0.5:
                sacco(bm, x - 0.5, -0.6, Il['juta'], M, rr(0, 3))
    # carretto
    Mc = T(PIAZZA_X - 3.2, -5.0, 0) @ RZ(math.radians(rr(60, 80)))
    box(bm, (-1.1, -0.6, 0.62), (1.1, 0.6, 0.7), Il['assi'], Mc)
    for (a, b) in [((-1.1, -0.6), (1.1, -0.56)), ((-1.1, 0.56), (1.1, 0.6)), ((-1.1, -0.6), (-1.06, 0.6)), ((1.06, -0.6), (1.1, 0.6))]:
        box(bm, (a[0], a[1], 0.7), (b[0], b[1], 1.05), Il['assi'], Mc)
    for sy in (-0.72, 0.72):
        Mw = Mc @ T(0.1, sy, 0.55) @ RX(math.radians(90))
        lathe(bm, [(0.55, -0.04), (0.55, 0.04), (0.48, 0.04), (0.48, -0.04)], 28, Il['legno_travi'], Mw, chiuso=True)
        lathe(bm, [(0.1, -0.07), (0.1, 0.07)], 12, Il['legno_travi'], Mw)
        for s in range(8):
            Ms = Mw @ RZ(s * math.pi / 4)
            box(bm, (0.08, -0.02, -0.02), (0.5, 0.02, 0.02), Il['legno_travi'], Ms)
    box(bm, (-0.15, -0.8, 0.53), (0.35, 0.8, 0.6), Il['legno_travi'], Mc)
    for sy in (-0.5, 0.5):
        prism(bm, [(1.1, 0.62), (2.6, 0.05), (2.6, 0.13), (1.1, 0.7)], sy - 0.03, sy + 0.03, Il['legno_travi'], 'y', Mc)
    for q in range(4):
        sacco(bm, rr(-0.8, 0.2), rr(-0.35, 0.35), Il['juta'], Mc @ T(0, 0, 0.45), rr(0, 3))
    cassetta(bm, 0.56, 0.42, 0.18, Il['legno_grezzo'], Mc @ T(0.35, -0.3, 0.7))
    riempi(bm, 0.56, 0.42, 'cavolo', Il['cavolo'], Mc @ T(0.35, -0.3, 0.7))
    # tavoli della locanda (casa sul lato nord piu' vicina al centro)
    nord = [f for f in facciate if (f[0] @ Vector((f[1] / 2, 0, 0))).y > PIAZZA_Y - 1]
    nord.sort(key=lambda f: abs((f[0] @ Vector((f[1] / 2, 0, 0))).x + 2.0))
    for (M, W, stile, bottega, n) in nord[:1]:
        for q in range(2):
            Mt = M @ T(W * (0.3 + 0.4 * q), -2.0, 0)
            box(bm, (-0.9, -0.4, 0.72), (0.9, 0.4, 0.78), Il['assi'], Mt)
            for (lx, ly) in ((-0.8, -0.3), (0.72, -0.3), (-0.8, 0.22), (0.72, 0.22)):
                box(bm, (lx, ly, 0), (lx + 0.08, ly + 0.08, 0.72), Il['legno_travi'], Mt)
            for by in (-0.75, 0.6):
                box(bm, (-0.9, by, 0.42), (0.9, by + 0.15, 0.46), Il['assi'], Mt)
                for lx in (-0.8, 0.72):
                    box(bm, (lx, by + 0.03, 0), (lx + 0.07, by + 0.12, 0.42), Il['legno_travi'], Mt)
            box(bm, (-0.2, -0.1, 0.78), (-0.1, 0.0, 0.92), Il['legno_grezzo'], Mt)
            cesta(bm, 0.3, 0.05, 'pane', Il, Mt @ T(0, 0, 0.78))
        break
    ob = oggetto("Oggetti_scena", bm, mats, coll)
    uv_finale(ob); smussa(ob, 0.008)
    return ob

def festoni(coll):
    # la prima corda parte lontana da Camera_Piazza: vista di punta sembrerebbe una riga verticale nel cielo
    linee = [((-14.0, -PIAZZA_Y + 1.0, 5.6), (-9.0, PIAZZA_Y - 1.0, 5.8)),
             ((1.0, -PIAZZA_Y + 1.0, 5.7), (4.0, PIAZZA_Y - 1.0, 5.5)),
             ((12.0, -PIAZZA_Y + 1.0, 5.5), (12.5, PIAZZA_Y - 1.0, 5.8))]
    colori = ['festone_rosso', 'festone_ocra', 'festone_blu', 'festone_crema']
    mats = ['ferro'] + colori
    bm = nuovo_bm(); corde = []
    for (a, b) in linee:
        a = Vector(a); b = Vector(b)
        for p, verso in ((a, 1), (b, -1)):
            box(bm, (p.x - 0.025, p.y - verso * 1.05, p.z - 0.025), (p.x + 0.025, p.y, p.z + 0.025), 0)
        n = 60; pts = []
        for i in range(n + 1):
            t = i / n; q = a.lerp(b, t); q.z -= 1.1 * 4 * t * (1 - t); pts.append(q)
        corde.append([tuple(p) for p in pts])
        L = (b - a).length; k = int(L / 0.45)
        for i in range(1, k):
            t = i / k; t2 = min(1.0, t + 0.3 / L)
            p0 = a.lerp(b, t); p0.z -= 1.1 * 4 * t * (1 - t)
            p1 = a.lerp(b, t2); p1.z -= 1.1 * 4 * t2 * (1 - t2)
            mid = (p0 + p1) / 2; mid.z -= 0.38
            vs = [bm.verts.new(p0), bm.verts.new(p1), bm.verts.new(mid)]
            f = bm.faces.new(vs); f.material_index = 1 + i % 4
    ob = oggetto("Festoni", bm, mats, coll)
    curva("Festoni_corde", corde, 0.01, 'juta', coll)
    return ob

# ----------------------------------------------------------------------
#  LUCE, CIELO, CAMERE, RENDER
# ----------------------------------------------------------------------
def cielo_e_sole(coll):
    import numpy as np
    sc = bpy.context.scene
    w = bpy.data.worlds.get('Cielo') or bpy.data.worlds.new('Cielo')
    sc.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld'); bg = nt.nodes.new('ShaderNodeBackground')
    nt.links.new(bg.outputs[0], out.inputs[0])
    hdr = None
    if os.path.isdir(TEXTURE):
        for f in os.listdir(TEXTURE):
            if f.lower().endswith('.hdr'):
                hdr = os.path.join(TEXTURE, f)
    phi_sole = math.radians(SOLE_AZIMUT); theta = math.radians(35)
    if hdr:
        img = bpy.data.images.load(hdr, check_existing=True)
        wd, ht = img.size
        px = np.empty(wd * ht * 4, dtype=np.float32); img.pixels.foreach_get(px)
        lum = px[0::4] * 0.2126 + px[1::4] * 0.7152 + px[2::4] * 0.0722
        i = int(lum.argmax()); row, col = divmod(i, wd)
        u, v = (col + 0.5) / wd, (row + 0.5) / ht
        phi_tex = (0.5 - u) * 2 * math.pi; theta = (v - 0.5) * math.pi
        tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Rotation'].default_value = (0, 0, phi_tex - phi_sole)
        env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = img
        nt.links.new(tc.outputs['Generated'], mp.inputs['Vector']); nt.links.new(mp.outputs[0], env.inputs['Vector'])
        nt.links.new(env.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = CIELO_FORZA
        print(f"HDRI: sole a {math.degrees(theta):.1f} gradi, picco {float(lum.max()):.0f}")
    else:
        bg.inputs['Color'].default_value = (0.45, 0.6, 0.85, 1); bg.inputs['Strength'].default_value = 1.0
    if FOSCHIA > 0:   # volume finito attorno alla citta' (un volume nel mondo spegnerebbe il cielo)
        m, mt_, bsdf, mout = nuovo_mat('foschia')
        mt_.nodes.remove(bsdf)
        vs = mt_.nodes.new('ShaderNodeVolumeScatter')
        vs.inputs['Density'].default_value = FOSCHIA
        vs.inputs['Color'].default_value = (0.85, 0.9, 1.0, 1)
        try:
            vs.inputs['Anisotropy'].default_value = 0.5
        except KeyError:
            pass
        mt_.links.new(vs.outputs[0], mout.inputs['Volume'])
        bmf = nuovo_bm(); box(bmf, (-250, -250, -1), (250, 250, 70), 0)
        oggetto("Foschia", bmf, ['foschia'], coll)
    ld = bpy.data.lights.new("Sole", 'SUN')
    ld.energy = SOLE_EXTRA; ld.angle = math.radians(0.8); ld.color = (1.0, 0.93, 0.84)
    sun = bpy.data.objects.new("Sole", ld); coll.objects.link(sun)
    sun.rotation_euler = (math.pi / 2 - theta, 0, phi_sole + math.pi / 2)

def camera(nome, pos, mira, lente, coll, fuoco=None, fstop=None, shift=0.0):
    cd = bpy.data.cameras.new(nome); cd.lens = lente; cd.clip_end = 500; cd.shift_y = shift
    ob = bpy.data.objects.new(nome, cd); coll.objects.link(ob)
    ob.location = pos
    d = Vector(mira) - Vector(pos)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if fuoco:
        cd.dof.use_dof = True; cd.dof.focus_distance = fuoco; cd.dof.aperture_fstop = fstop or 2.8
    return ob

def impostazioni_render():
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.get_devices()
        for t in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
            try:
                prefs.compute_device_type = t; break
            except TypeError:
                continue
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = 'GPU'
    except Exception:
        pass
    sc.cycles.samples = CAMPIONI
    sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8
    sc.render.resolution_x, sc.render.resolution_y = RISOLUZIONE
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    sc.view_settings.exposure = ESPOSIZIONE

# ----------------------------------------------------------------------
#  MAIN
# ----------------------------------------------------------------------
def main():
    t0 = time.time()
    FACCIATE.clear(); OSTACOLI.clear(); GRIGLIA.clear(); APERTURE.clear(); RIMESSE.clear()
    INFO_AP.clear(); DET_ID.clear(); PALAZZI.clear()
    svuota_scena()
    crea_materiali()
    COLL_PIANTE[0] = collezione("Piante"); carica_piante()
    print("Modelli di piante:", {k: len(v) for k, v in PIANTE.items()}, round(time.time() - t0, 1))
    c_piazza = collezione("Piazza"); c_ed = collezione("Edifici"); c_mer = collezione("Mercato")
    c_ogg = collezione("Oggetti"); c_luci = collezione("Luci_Camere")
    PX, PY = PIAZZA_X, PIAZZA_Y
    porte = calcola_porte()
    terreno(c_piazza, porte); fontana(c_piazza)
    # suolo gia' impegnato: piazza, strade, lotti per gli edifici con un ruolo
    for (nome, larg, punti, _) in STRADE:
        occupa_strada(punti, larg)
    for (x0, y0, x1, y1) in [(-PX, -PY, PX, PY)] + RISERVATI:
        occupa([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    print("Piazza pronta", round(time.time() - t0, 1))
    # prima fila (affaccio sulla piazza): i varchi per le strade si aprono da soli
    palazzo(Matrix.Translation((-PX, -8.0, 0)) @ RZ(math.pi / 2), c_ed)
    for (nome, punti, par) in linee_prima_fila():
        fila(nome, punti, c_ed, **par)
    prima_fila = list(FACCIATE)
    print("Prima fila pronta", round(time.time() - t0, 1))
    torre(Matrix.Translation((-1.4, 49.0, 0)), c_ed)   # campanile accanto alla chiesa, sul sagrato
    c_zone = collezione("Zone")
    acc = Interno(c_zone, 60, "Accessori", "Lastricati_zone")   # tettoie, orti, giardini, alberi
    if CASE_STRADE:
        # case su entrambi i lati di ogni strada, con la facciata sulla strada; stile secondo la zona
        for (nome, larg, punti, par) in STRADE:
            for lato, P in (("_a", punti), ("_b", punti[::-1])):
                fila(nome + lato, scosta(P, larg / 2), c_ed, per_zona=True, fronte=larg * 0.28, accessori=acc, **par)
    print("Edifici pronti", round(time.time() - t0, 1), "-", len(FACCIATE), "case")
    edifici_zone(c_zone, acc)
    print("Chiesa, torre, palazzetto, giardini e orti pronti", round(time.time() - t0, 1))
    edifici_ruolo(collezione("Edifici_ruolo"))
    print("Edifici con un ruolo pronti", round(time.time() - t0, 1))
    if RIEMPI_ISOLATI:
        isolati(collezione("Isolati"))
        print("Isolati pronti", round(time.time() - t0, 1))
    c_mura = collezione("Mura")
    mura(c_mura, porte)
    for g in porte:
        porta(g, c_mura)
    print("Mura e porte pronte", round(time.time() - t0, 1))
    banc = mercato(c_mer)
    oggetti_scena(c_ogg, prima_fila)
    if FESTONI:
        festoni(c_ogg)
    print("Mercato e oggetti pronti", round(time.time() - t0, 1))
    acc.chiudi()
    print("Accessori delle zone pronti", round(time.time() - t0, 1))
    if CONTROLLA_APERTURE:
        sb = []
        for _ in range(3):   # togliere un'apertura puo' cambiare di poco il muro accanto: si ricontrolla
            nuove = controlla_aperture()
            sb += nuove
            if not nuove:
                break
        conta = {}
        for s_ in sb:
            tipo, motivo, nome = s_[:3]
            chi = 'case interne' if nome.startswith('Interno') else 'case sulle vie'
            conta[(tipo, motivo, chi)] = conta.get((tipo, motivo, chi), 0) + 1
        print("Aperture tolte:", len(sb), "su", len(APERTURE), dict(sorted(conta.items())), round(time.time() - t0, 1))
        cieche, aggiunte = riapri_facciate({s_[6] for s_ in sb})
        per_luogo = {}
        for (_, luogo, _, _, np_) in cieche:
            per_luogo.setdefault(luogo, [0, 0]); per_luogo[luogo][0] += 1; per_luogo[luogo][1] += np_ > 0
        print("Facciate rimaste senza aperture (quante, riaperte):", per_luogo, "- finestre aggiunte:", aggiunte,
              round(time.time() - t0, 1))
        for (nome, luogo, c, n, np_) in cieche:
            if luogo != 'altro':
                print("   ", luogo, nome, "centro", tuple(round(v, 1) for v in c), "verso", tuple(round(v, 2) for v in n),
                      "finestre rimesse:", np_)
    print("Balconi con porta-finestra:", len(BALCONI))
    for (c, n) in BALCONI:
        print("    balcone", tuple(round(v, 1) for v in c), "verso", tuple(round(v, 2) for v in n))
    vegetazione(collezione("Campagna"), porte)   # per ultima: non altera la sequenza casuale del resto
    print("Vegetazione pronta", round(time.time() - t0, 1))
    cielo_e_sole(c_luci)
    impostazioni_render()
    # camere definitive: piazza, una per zona, la campagna con la porta e l'aerea con la pianta intera
    cam = camera("Camera_Piazza", (-9.5, -11.8, 1.65), (-1.0, 19.4, 7.0), 20, c_luci, shift=0.05)
    pe = next(g for g in porte if g['nome'] == 'Porta_Est'); G = pe['punto']; p = G - pe['dir'] * 36.0
    camera("Camera_Via_Maestra", (p.x, p.y, 1.7), (G.x, G.y, 6.0), 28, c_luci)       # verso la Porta Est
    camera("Camera_Chiesa", (-13.0, 30.2, 1.7), (-8.0, 47.0, 8.8), 20, c_luci, shift=0.08)
    camera("Camera_Artigiani", (12.2, -39.5, 1.75), (9.6, -84.0, 5.5), 24, c_luci)   # forno e Porta Sud
    camera("Camera_Nobili", (-40.0, 16.0, 1.7), (-45.25, -3.0, 3.7), 14, c_luci, shift=0.33)  # Torre dei Nobili intera
    camera("Camera_Campagna", (140.0, 2.0, 3.5), (110.0, 14.5, 7.0), 28, c_luci)    # Porta Est da fuori
    camera("Camera_Aerea", (11.0, -190.0, 250.0), (11.0, -12.0, 0.0), 35, c_luci)    # tutto il borgo
    p, r = banc[N_BANCARELLE // 2]
    cpos = p - r * 2.7 + Vector((0, 0, 1.75))
    camera("Camera_Mercato", tuple(cpos), tuple(p + r * 0.5 + Vector((0, 0, 0.85))), 35, c_luci,
           fuoco=(cpos - p).length - 0.3, fstop=4.0)
    bpy.context.scene.camera = cam
    print("Scena completata in", round(time.time() - t0, 1), "secondi")
    if SALVA:
        os.makedirs(CARTELLA, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(CARTELLA, "quartiere_mercato.blend"))
    if RENDER:
        rendi_camere()

def rendi_camere():
    """Render a piena qualita' di tutte le CAMERE_FINALI nella cartella CARTELLA_RENDER (PNG)."""
    sc = bpy.context.scene
    os.makedirs(CARTELLA_RENDER, exist_ok=True)
    sc.render.image_settings.file_format = 'PNG'
    for nome in CAMERE_FINALI:
        t = time.time()
        sc.camera = bpy.data.objects[nome]
        sc.render.filepath = os.path.join(CARTELLA_RENDER, nome.replace("Camera_", "").lower() + ".png")
        bpy.ops.render.render(write_still=True)
        print("Render", nome, round(time.time() - t, 1), "s ->", sc.render.filepath)

if __name__ == "__main__":
    main()
