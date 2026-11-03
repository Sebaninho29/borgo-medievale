# -*- coding: utf-8 -*-
"""
esporta_borgo.py  -  Fase 2, passo 2: esporta la citta' intera per il web, divisa in zone.

Apre il .blend del borgo senza salvarlo e scrive in web/_esportazione/citta e web/public/citta:
    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" --background
        "D:\\Quartiere_Mercato\\Blender\\quartiere_mercato.blend" --python web\\esporta_borgo.py
poi "npm run citta" comprime (meshopt, WebP) in web/public/citta.

Passi:
1. alberi e cespugli (istanze Poly Haven) -> impostori: un'immagine con trasparenza per variante + posizioni;
2. case interne degli isolati semplificate: via vetri, imposte, davanzali e architravi, finestre dipinte
   in una texture "a cella" (2,6 m x 2,8 m = un modulo di facciata per piano);
3. materiali procedurali -> materiali glTF semplici (texture 1k con tinta gia' applicata, normale);
4. tutto unito e diviso per zone (centro = piazza + Via Maestra, poi nord, sud, est, ovest);
5. occlusione ambientale cotta con Cycles nei colori dei vertici (le facce grandi vengono suddivise);
6. una .gltf per zona (texture esterne condivise) + citta.json con zone, impostori e camere.
"""
import bpy, bmesh, os, math, time, json, hashlib
import numpy as np
from mathutils import Vector, Matrix

# ============================== PARAMETRI ==============================
LATO_TEX     = 1024         # texture dei materiali
LATO_IMPOST  = 1024         # immagini degli impostori (da vicino a 512 px le foglie erano sfocate)
LATO_MAX_AO  = 3.0          # lato massimo (m) dei poligoni prima della cottura dell'AO
CAMPIONI_AO  = 64
DISTANZA_AO  = 4.0          # m: raggio dell'occlusione
CELLA        = (2.6, 2.8)   # modulo di facciata delle finestre dipinte (larghezza, altezza)
LATO_RIQUADRO = 25.0        # m: le zone si dividono in riquadri (precisione della quantizzazione, culling, ombre)
SEMPLIFICA_INTERNI = False  # True = case interne con finestre dipinte (meno triangoli, brutte da vicino)
LATO_TEX_SUOLO = 2048       # suolo vicino al giocatore: texture piu' fini
SUOLO = {'selciato', 'terra', 'terra_erbosa'}   # 2k: strade e cortili; fossato e campagna restano a 1k
CONTRASTO_TERRA = 0.6       # la terra battuta, schiarita, diventava troppo contrastata
TETTI_WEB = {'coppi_web', 'ardesia_web', 'paglia_web', 'coppi_vecchi_web'}
A_RIGHE = ('telo_', 'tenda', 'stendardo', 'festone')   # tessuti a righe: le UV hanno un verso, non riproiettarle
AREA_PENDIO = 0.5           # m2: sotto questa area le facce inclinate tengono le UV del generatore
CORSI_PAGLIA = 4            # corsi di paglia per ripetizione della texture (2,5 m): da lontano la falda si legge
SEGMENTI_TRONCO = 32        # tronchi del falegname ricostruiti lisci, con UV cilindriche
TINTA_ARDESIA = (0.6, 0.66, 0.76)   # lastre di ardesia sul web: grigio-azzurro, non beige
EMISSIONE_BRACE = 2.0       # la brace (30 in Cycles) sul web diventava una macchia bianca
# vento: tipo di tela nel canale B dell'AO (codice / 8); G = liberta', A = dondolio dei festoni (citta.js, VENTO_GLSL)
TELE = {'stendardo': 1, 'banderuola': 2, 'telo': 3, 'tenda': 4, 'festone': 5, 'insegna': 6}
# oggetti rigidi che dondolano a pendolo attorno all'asse Y locale passante per l'origine (tipo 'insegna')
INSEGNE = ('Insegna_Cinghiale',)
# =======================================================================

QUI = os.path.dirname(os.path.abspath(__file__))
ESPORT = os.path.join(QUI, "_esportazione", "citta")
TEX_TMP = os.path.join(QUI, "_tex_esportazione")
PUBBLICO = os.path.join(QUI, "public", "citta")
for d in (ESPORT, TEX_TMP, PUBBLICO, os.path.join(PUBBLICO, "impostori")):
    os.makedirs(d, exist_ok=True)

ZONE = ['centro', 'nord', 'sud', 'est', 'ovest']

def zona_di(x, y):
    """centro = piazza + Via Maestra fino al ponte della Porta Est (da caricare per prima)."""
    if -32 <= x <= 32 and -28 <= y <= 28:
        return 'centro'
    if 14 <= x <= 135 and abs(y - (0.6 + (x - 32) * 0.186)) <= 26:
        return 'centro'
    if x < -32: return 'ovest'
    if y > 24: return 'nord'
    if x < 35: return 'sud'
    return 'est'

def b2t(v):   # Blender (x, y, z) -> three (x, z, -y)
    return [round(v[0], 3), round(v[2], 3), round(-v[1], 3)]

# ----------------------------------------------------------------------
#  TEXTURE E MATERIALI PER IL WEB
# ----------------------------------------------------------------------
def srgb_lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def lin_srgb(c): return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0), 1 / 2.4) - 0.055)

def salva(img, nome, formato='JPEG'):
    img.name = nome
    img.filepath_raw = os.path.join(TEX_TMP, nome + ('.jpg' if formato == 'JPEG' else '.png'))
    img.file_format = formato; img.save()
    return img

_IMMAGINI = {}
def immagine_web(img, tinta=None, sat=1.0, dati=False, lato=LATO_TEX, contrasto=1.0):
    """Copia a 'lato' px con tinta, saturazione e contrasto applicati in lineare; nome deterministico."""
    chiave = (img.filepath, tinta and tuple(round(t, 3) for t in tinta), round(sat, 3), lato, round(contrasto, 3))
    if chiave in _IMMAGINI:
        return _IMMAGINI[chiave]
    nuova = img.copy(); nuova.scale(lato, lato)
    # dal nome dell'immagine: os.path.basename('//textures\x.jpg') in Blender da' '' e tutte le mappe delle normali
    # finivano nello stesso file "Image" (sul web ogni materiale aveva la normale dell'ultimo scritto)
    base = os.path.splitext(img.name)[0].replace('_2k', '').replace('_1k', '')
    if lato != LATO_TEX:
        base += "_%d" % lato
    if not dati and (tinta is not None or sat != 1.0 or contrasto != 1.0):
        px = np.empty(lato * lato * 4, np.float32); nuova.pixels.foreach_get(px); px = px.reshape(-1, 4)
        rgb = srgb_lin(px[:, :3])
        if sat != 1.0:
            lum = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32); rgb = lum[:, None] + (rgb - lum[:, None]) * sat
        if tinta is not None:
            rgb = rgb * np.array(tinta, np.float32)
        if contrasto != 1.0:
            media = rgb.mean(axis=0); rgb = media + (rgb - media) * contrasto
        px[:, :3] = lin_srgb(np.clip(rgb, 0, 1)); nuova.pixels.foreach_set(px.ravel())
        base += "_" + hashlib.md5(repr(chiave).encode()).hexdigest()[:6]
    salva(nuova, base)
    if dati:
        nuova.colorspace_settings.name = 'Non-Color'
    _IMMAGINI[chiave] = nuova
    return nuova

def immagine_righe(c1, c2):
    nome = "righe_" + hashlib.md5(repr((c1, c2)).encode()).hexdigest()[:6]
    if nome in _IMMAGINI:
        return _IMMAGINI[nome]
    img = bpy.data.images.new(nome, 64, 4)
    px = np.zeros((4, 64, 4), np.float32)
    px[:, :32, :3] = lin_srgb(np.array(c1, np.float32)); px[:, 32:, :3] = lin_srgb(np.array(c2, np.float32)); px[..., 3] = 1
    img.pixels.foreach_set(px.ravel()); salva(img, nome, 'PNG')
    _IMMAGINI[nome] = img
    return img

def tetto_leggibile(img, nome, corsi=0, contrasto=1.35, luce=1.0):
    """Tetti leggibili anche da lontano: fili e lastre con piu' contrasto, chiazze larghe (materiale piu' vecchio
    e piu' nuovo) e, per la paglia, corsi sovrapposti con le punte chiare e l'ombra sotto il corso di sopra.
    Le texture originali hanno solo dettagli fini e da 10-20 m diventavano un colore uniforme."""
    lato = img.size[0]
    px = np.empty(lato * lato * 4, np.float32); img.pixels.foreach_get(px); px = px.reshape(lato, lato, 4)
    rgb = srgb_lin(px[..., :3])
    media = rgb.reshape(-1, 3).mean(axis=0); rgb = media + (rgb - media) * contrasto
    x = np.arange(lato)[None, :] / lato; v = np.arange(lato)[:, None] / lato     # v cresce verso il colmo
    f = np.ones((lato, lato), np.float32)
    if corsi:
        rng = np.random.default_rng(7)
        bordo = sum(a * np.sin(2 * np.pi * (k * x + rng.random())) for k, a in ((3, 0.05), (7, 0.03), (17, 0.015)))
        c = (v * corsi + bordo) % 1.0                                           # 0 = punte del corso
        f = np.where(c < 0.1, 1.25 - c, 1.15 - 0.45 * np.clip((c - 0.1) / 0.9, 0, 1) ** 1.6)
    chiazze = 1.0 + 0.16 * np.sin(2 * np.pi * (x + 0.3 * np.sin(2 * np.pi * v))) * np.sin(2 * np.pi * (2 * v + 0.2))         + 0.08 * np.sin(2 * np.pi * (3 * x - 2 * v + 0.6))
    rgb = rgb * (f * chiazze)[..., None] * luce
    px[..., :3] = lin_srgb(np.clip(rgb, 0, 1))
    nuova = bpy.data.images.new(nome, lato, lato); nuova.pixels.foreach_set(px.ravel())
    return salva(nuova, nome)

def _collegato_da(sock, tipo):
    return sock.is_linked and sock.links[0].from_node.type == tipo

def leggi_materiale(m):
    d = dict(diff=None, nor=None, forza_nor=1.0, scala=1.0, tinta=None, sat=1.0, colore=None, righe=None,
             passo_righe=0.22, rugo=0.8, metallo=0.0, emissione=None, alfa=1.0)
    if not m.use_nodes or m.node_tree is None:
        d['colore'] = tuple(m.diffuse_color[:3]); return d
    nodi = m.node_tree.nodes
    b = next((n for n in nodi if n.type == 'BSDF_PRINCIPLED'), None)
    for n in nodi:
        if n.type == 'TEX_IMAGE' and n.image:
            f = n.image.filepath.lower()
            if '_diff_' in f: d['diff'] = n.image
            elif '_nor_gl_' in f: d['nor'] = n.image
        elif n.type == 'MAPPING' and _collegato_da(n.inputs['Vector'], 'TEX_COORD') \
                and n.inputs['Vector'].links[0].from_socket.name == 'UV':
            d['scala'] = n.inputs['Scale'].default_value[0]
        elif n.type == 'NORMAL_MAP':
            d['forza_nor'] = n.inputs['Strength'].default_value
        elif n.type == 'MIX' and n.data_type == 'RGBA':
            fa = n.inputs[0]
            A = next(s for s in n.inputs if s.name == 'A' and s.type == 'RGBA')
            B = next(s for s in n.inputs if s.name == 'B' and s.type == 'RGBA')
            if n.blend_type == 'MULTIPLY' and not fa.is_linked and fa.default_value > 0.99 and not B.is_linked \
                    and _collegato_da(A, 'HUE_SAT'):
                d['tinta'] = tuple(B.default_value[:3])
            if n.blend_type == 'MIX' and fa.is_linked and fa.links[0].from_node.type == 'MATH' \
                    and fa.links[0].from_node.operation == 'GREATER_THAN':
                d['righe'] = (tuple(A.default_value[:3]), tuple(B.default_value[:3]))
        elif n.type == 'HUE_SAT' and not n.inputs['Saturation'].is_linked and n.inputs['Saturation'].default_value < 0.99:
            d['sat'] = n.inputs['Saturation'].default_value
        elif n.type == 'RGB':
            d['colore'] = tuple(n.outputs[0].default_value[:3])
        elif n.type == 'MATH' and n.operation == 'MULTIPLY' and not n.inputs[1].is_linked and n.inputs[1].default_value > 1:
            d['passo_righe'] = 1.0 / n.inputs[1].default_value
    if b:
        if not b.inputs['Roughness'].is_linked: d['rugo'] = b.inputs['Roughness'].default_value
        d['metallo'] = b.inputs['Metallic'].default_value
        if d['colore'] is None and not b.inputs['Base Color'].is_linked:
            d['colore'] = tuple(b.inputs['Base Color'].default_value[:3])
        try:
            if b.inputs['Emission Strength'].default_value > 0:
                d['emissione'] = (tuple(b.inputs['Emission Color'].default_value[:3]), b.inputs['Emission Strength'].default_value)
        except KeyError:
            pass
        d['alfa'] = b.inputs['Alpha'].default_value
    return d

def nuovo_mat_web(nome):
    w = bpy.data.materials.new(nome); w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    return w, nt, b

def _immagine_su(nt, b, img, scala, sock='Base Color'):
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (scala[0], scala[1], 1.0)
    nt.links.new(tc.outputs['UV'], mp.inputs['Vector'])
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img
    nt.links.new(mp.outputs[0], t.inputs['Vector'])
    if sock == 'Normal':
        nm = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(t.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], b.inputs['Normal']); return nm
    nt.links.new(t.outputs['Color'], b.inputs[sock])

_MAT_WEB = {}
def materiale_web(m):
    if m.name in _MAT_WEB:
        return _MAT_WEB[m.name]
    d = leggi_materiale(m)
    w, nt, b = nuovo_mat_web(m.name + "_web")
    b.inputs['Roughness'].default_value = min(1.0, d['rugo']); b.inputs['Metallic'].default_value = d['metallo']
    lato = LATO_TEX_SUOLO if m.name in SUOLO else LATO_TEX
    contrasto = CONTRASTO_TERRA if m.name.startswith('terra') and m.name != 'terracotta' else 1.0
    if m.name == 'interno_buio' and 'tavole' in bpy.data.materials:
        # fondo delle botteghe e delle rimesse: tavole scure invece del nero pieno (il web aggiunge un filo di luce)
        dt = leggi_materiale(bpy.data.materials['tavole'])
        d = dict(d, diff=dt['diff'], nor=None, tinta=tuple(c * 0.75 for c in dt['tinta'] or (0.8, 0.6, 0.42)),
                 sat=dt['sat'], scala=dt['scala'])
        b.inputs['Roughness'].default_value = 0.9
    if m.name == 'brace' and d['emissione']:
        d['emissione'] = (d['emissione'][0], min(d['emissione'][1], EMISSIONE_BRACE))
    if m.name == 'paglia' and d['diff'] is not None:
        _immagine_su(nt, b, tetto_leggibile(immagine_web(d['diff'], d['tinta'], d['sat'], lato=lato), 'paglia_corsi',
                                            corsi=CORSI_PAGLIA, luce=1.7), (d['scala'], d['scala']))
    elif m.name == 'ardesia' and d['diff'] is not None:   # lastre grigio-azzurre (la tinta di Cycles non arrivava)
        _immagine_su(nt, b, tetto_leggibile(immagine_web(d['diff'], TINTA_ARDESIA, d['sat'], lato=lato), 'ardesia_chiazze',
                                            contrasto=1.5), (d['scala'], d['scala']))
    elif d['diff'] is not None:
        _immagine_su(nt, b, immagine_web(d['diff'], d['tinta'], d['sat'], lato=lato, contrasto=contrasto), (d['scala'], d['scala']))
    elif d['righe'] is not None:
        _immagine_su(nt, b, immagine_righe(*d['righe']), (1.0 / (2 * d['passo_righe']), 1.0))
    else:
        b.inputs['Base Color'].default_value = (*(d['colore'] or (0.5, 0.5, 0.5)), 1.0)
    if d['diff'] is not None and d['nor'] is not None:
        # le normali del suolo restano a 1k: a 2k pesavano 1,7 MB l'una e il dettaglio si vede nel colore
        nm = _immagine_su(nt, b, immagine_web(d['nor'], dati=True, lato=min(lato, LATO_TEX)), (d['scala'], d['scala']), 'Normal')
        nm.inputs['Strength'].default_value = d['forza_nor']
    if d['emissione']:
        b.inputs['Emission Color'].default_value = (*d['emissione'][0], 1.0)
        b.inputs['Emission Strength'].default_value = d['emissione'][1]
    if d['alfa'] < 0.99:
        b.inputs['Alpha'].default_value = d['alfa']
    w['_info'] = repr((d['scala'], d['tinta'], d['sat']))
    _MAT_WEB[m.name] = (w, d)
    return w, d

# --- finestre dipinte per le case interne -------------------------------
DA_DIPINGERE = {'pietra_blocchi', 'pietra_muro', 'mattoni', 'intonaco_bianco', 'intonaco_giallo', 'intonaco_rosa', 'tavole'}
_FINESTRE = {}
def materiale_finestre(nome_mat, d):
    """Materiale 'facciata con finestre': il muro (texture gia' tinta) ricampionato su una cella 2,6 x 2,8 m
    con una finestra dipinta: cornice, vetro scuro con croce, davanzale, imposte."""
    if nome_mat in _FINESTRE:
        return _FINESTRE[nome_mat]
    W, H = 512, int(round(512 * CELLA[1] / CELLA[0]))
    src = immagine_web(d['diff'], d['tinta'], d['sat'])
    px = np.empty(LATO_TEX * LATO_TEX * 4, np.float32); src.pixels.foreach_get(px); px = px.reshape(LATO_TEX, LATO_TEX, 4)
    tile = 1.0 / max(1e-3, d['scala'])
    xs = ((np.arange(W) / W * CELLA[0] / tile) % 1.0 * LATO_TEX).astype(int)
    zs = ((np.arange(H) / H * CELLA[1] / tile) % 1.0 * LATO_TEX).astype(int)
    c = px[zs][:, xs].copy()
    m2p = lambda x, z: (int(x / CELLA[0] * W), int(z / CELLA[1] * H))
    def rett(x0, z0, x1, z1, col):
        (a, b_), (c_, d_) = m2p(x0, z0), m2p(x1, z1)
        c[max(0, b_):d_, max(0, a):c_, :3] = col
    legno, vetro, chiaro = (0.2, 0.13, 0.08), (0.05, 0.06, 0.07), (0.72, 0.68, 0.6)
    imp = [(0.27, 0.42, 0.3), (0.5, 0.2, 0.15), (0.3, 0.38, 0.5), (0.35, 0.25, 0.16)][int(hashlib.md5(nome_mat.encode()).hexdigest(), 16) % 4]
    xc, w, za, zb = CELLA[0] / 2, 0.75, 0.35, 1.5          # finestra (piano a partire da 0,5 m)
    if nome_mat.startswith('intonaco'):
        rett(xc - w / 2 - 0.13, za, xc + w / 2 + 0.13, zb + 0.13, chiaro)      # cornice di pietra
    rett(xc - w / 2 - 0.05, za - 0.05, xc + w / 2 + 0.05, zb + 0.05, legno)
    rett(xc - w / 2 + 0.04, za + 0.04, xc + w / 2 - 0.04, zb - 0.04, vetro)
    rett(xc - 0.02, za, xc + 0.02, zb, legno); rett(xc - w / 2, za + 0.62 * (zb - za) - 0.02, xc + w / 2, za + 0.62 * (zb - za) + 0.02, legno)
    rett(xc - w / 2 - 0.1, za - 0.1, xc + w / 2 + 0.1, za - 0.01, chiaro)    # davanzale
    for (a, b_) in ((xc - w - 0.04, xc - w / 2 - 0.06), (xc + w / 2 + 0.06, xc + w + 0.04)):   # imposte aperte
        rett(a, za, b_, zb, imp)
        for k in range(1, 4):
            rett(a, za + k * (zb - za) / 4 - 0.01, b_, za + k * (zb - za) / 4 + 0.01, tuple(v * 0.7 for v in imp))
    c[..., :3] = np.where(c[..., :3] > 1.0, 1.0, c[..., :3])
    img = bpy.data.images.new("finestre_" + nome_mat, W, H); img.pixels.foreach_set(c.ravel())
    salva(img, "finestre_" + nome_mat)
    w_, nt, b = nuovo_mat_web(nome_mat + "_finestre")
    b.inputs['Roughness'].default_value = 0.85
    _immagine_su(nt, b, img, (1.0, 1.0))
    _FINESTRE[nome_mat] = w_
    return w_

# ----------------------------------------------------------------------
#  ALBERI -> IMPOSTORI
# ----------------------------------------------------------------------
def _max_filtro(a, r):
    """Massimo su un quadrato di lato 2r+1 (due passate separabili)."""
    o = a.copy()
    for d in range(1, r + 1):
        o[:, d:] = np.maximum(o[:, d:], a[:, :-d]); o[:, :-d] = np.maximum(o[:, :-d], a[:, d:])
    b = o.copy()
    for d in range(1, r + 1):
        o[d:, :] = np.maximum(o[d:, :], b[:-d, :]); o[:-d, :] = np.maximum(o[:-d, :], b[d:, :])
    return o

def _sfoca(a, r):
    """Media su un quadrato di lato 2r+1 (somme cumulative, bordi ripetuti)."""
    for ax in (0, 1):
        pad = [(r + 1, r) if i == ax else (0, 0) for i in range(a.ndim)]
        c = np.cumsum(np.pad(a, pad, mode='edge'), axis=ax)
        n = c.shape[ax]
        a = (np.take(c, range(2 * r + 1, n), axis=ax) - np.take(c, range(0, n - 2 * r - 1), axis=ax)) / (2 * r + 1)
    return a

def infittisci_chioma(path):
    """Impostore di una pianta: le foglie (pixel verdi) senza buchi - chiusura morfologica; i pixel aggiunti
    prendono il colore delle foglie vicine, piu' scuro come l'interno della chioma - e di un verde piu' vivo.
    Tronco e rami (grigi) restano com'erano. Restituisce quanti pixel sono stati riempiti."""
    im = bpy.data.images.load(path); w, h = im.size
    px = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(px); px = px.reshape(h, w, 4)
    rgb, a = px[..., :3], px[..., 3]
    verde = (a > 0.3) & (rgb[..., 1] > rgb[..., 0] * 1.02) & (rgb[..., 1] > rgb[..., 2] * 1.05)
    r = max(4, w // 40)
    # un pixel vuoto si riempie dove le foglie attorno sono fitte (densita' locale) e dentro la chioma (densita'
    # su un raggio grande): niente direzioni privilegiate, la sagoma esterna resta frastagliata
    vf = verde.astype(np.float32)
    nuovi = (_sfoca(vf, r) > 0.3) & (_sfoca(vf, 3 * r) > 0.3) & (a < 0.5)
    # i pixel nuovi copiano foglie vere da posizioni vicine (piu' scure, come l'interno della chioma): resta la
    # grana delle foglie invece di una macchia uniforme
    rgb2 = rgb.copy(); da_fare = nuovi.copy()
    rng = np.random.default_rng(1)
    for _ in range(40):
        if not da_fare.any():
            break
        dy, dx = (rng.integers(-3 * r, 3 * r + 1) for _ in range(2))
        src_v = np.roll(verde, (dy, dx), axis=(0, 1)); src_c = np.roll(rgb, (dy, dx), axis=(0, 1))
        ok = da_fare & src_v
        rgb2[ok] = src_c[ok] * 0.7; da_fare &= ~ok
    nuovi &= ~da_fare
    a2 = a.copy(); a2[nuovi] = 1.0
    foglie = verde | nuovi
    lum = (rgb2 @ np.array([0.2126, 0.7152, 0.0722], np.float32))[..., None]
    vivo = (lum + (rgb2 - lum) * 1.5) * np.array([0.92, 1.06, 0.82], np.float32)
    rgb2[foglie] = np.clip(vivo[foglie], 0.0, 1.0)
    im.pixels.foreach_set(np.concatenate([rgb2, a2[..., None]], axis=2).astype(np.float32).ravel())
    im.save(); bpy.data.images.remove(im)
    return int(nuovi.sum())

def impostori():
    """Un'immagine per variante (vista di lato, sfondo trasparente, chioma infittita) e la lista delle istanze."""
    istanze = [o for o in bpy.context.scene.objects if o.instance_type == 'COLLECTION' and o.instance_collection]
    varianti = sorted({o.instance_collection.name for o in istanze})
    info = {}
    sc = bpy.data.scenes.new("_impostori")
    sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'CYCLES'
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = LATO_IMPOST
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new("_impostori"); w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.75, 0.82, 0.95, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.9
    sc.world = w
    sol = bpy.data.objects.new("sole", bpy.data.lights.new("sole", 'SUN')); sol.data.energy = 3.5
    sol.rotation_euler = (math.radians(50), 0, math.radians(30)); sc.collection.objects.link(sol)
    cd = bpy.data.cameras.new("cam"); cd.type = 'ORTHO'
    cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
    for v in varianti:
        col = bpy.data.collections[v]
        e = bpy.data.objects.new("ist", None); e.instance_type = 'COLLECTION'; e.instance_collection = col
        sc.collection.objects.link(e)
        pts = [o.matrix_world @ Vector(c) for o in col.all_objects if o.type == 'MESH' for c in o.bound_box]
        off = Vector(col.instance_offset)
        x0, x1 = min(p.x for p in pts) - off.x, max(p.x for p in pts) - off.x
        z0, z1 = max(0.0, min(p.z for p in pts)), max(p.z for p in pts)
        lato = max(x1 - x0, z1 - z0) * 1.04
        cd.ortho_scale = lato
        cam.location = ((x0 + x1) / 2, -50.0, z0 + lato / 2); cam.rotation_euler = (math.radians(90), 0, 0)
        sc.render.filepath = os.path.join(PUBBLICO, "impostori", v + ".png")
        bpy.ops.render.render(write_still=True, scene=sc.name)
        print("  impostore", v, "pixel di chioma riempiti:", infittisci_chioma(sc.render.filepath))
        info[v] = dict(file="impostori/" + v + ".png", lato=round(lato, 3), base=round(z0, 3),
                       cx=round((x0 + x1) / 2, 3))
        bpy.data.objects.remove(e)
    lista = []
    for o in istanze:
        loc, rot, sca = o.matrix_world.decompose()
        lista.append(dict(v=o.instance_collection.name, p=b2t(loc), r=round(rot.to_euler().z, 3),
                          s=[round(sca.x, 3), round(sca.z, 3)]))
    bpy.data.scenes.remove(sc)
    return info, lista

# ----------------------------------------------------------------------
#  CASE INTERNE SEMPLIFICATE
# ----------------------------------------------------------------------
TOGLI_SEMPRE = ('vetro', 'imposte_verdi', 'imposte_rosse', 'imposte_blu', 'interno_buio')
TOGLI_SE_PICCOLI = ('pietra_cornici', 'legno_travi', 'legno_grezzo')

def semplifica_interno(ob):
    """Via finestre finte e minuterie, finestre dipinte sui muri (UV in celle di facciata)."""
    me = ob.data; bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
    nomi = [s.material.name if s.material else '' for s in ob.material_slots]
    via = set(f for f in bm.faces if nomi[f.material_index] in TOGLI_SEMPRE)
    visti = set()
    for f in bm.faces:   # isole piccole (davanzali, architravi, tronchetti)
        if f in visti or nomi[f.material_index] not in TOGLI_SE_PICCOLI:
            continue
        isola, coda = [], [f]; visti.add(f)
        while coda:
            g = coda.pop(); isola.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in visti:
                        visti.add(h); coda.append(h)
        if sum(g.calc_area() for g in isola) < 1.0:
            via.update(isola)
    n0 = len(bm.faces)
    bmesh.ops.delete(bm, geom=list(via), context='FACES')
    uv = bm.loops.layers.uv.verify()
    nuovi = {}
    for f in bm.faces:
        nm = nomi[f.material_index]
        if nm in DA_DIPINGERE and abs(f.normal.z) < 0.2 and f.calc_area() > 1.0:
            t = Vector((-f.normal.y, f.normal.x, 0.0)).normalized()
            for l in f.loops:
                l[uv].uv = (l.vert.co.dot(t) / CELLA[0], (l.vert.co.z - 0.5) / CELLA[1])
            f.material_index = nuovi.setdefault(nm, len(nomi) + len(nuovi))
    bm.to_mesh(me); bm.free()
    for nm in sorted(nuovi, key=nuovi.get):
        me.materials.append(bpy.data.materials[nm])   # segnaposto: sostituito dopo con *_finestre
        ob['_dipinti'] = ob.get('_dipinti', '') + nm + ';'
    return n0, len(me.polygons), nuovi

# ----------------------------------------------------------------------
#  CORREZIONI DI SINGOLI OGGETTI (solo nella copia esportata: la scena non viene salvata)
# ----------------------------------------------------------------------
def _isole(bm, filtro):
    """Isole di facce collegate che passano il filtro (sulla faccia)."""
    visti, res = set(), []
    for f in bm.faces:
        if f in visti or not filtro(f):
            continue
        isola, coda = [], [f]; visti.add(f)
        while coda:
            g = coda.pop(); isola.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in visti and filtro(h):
                        visti.add(h); coda.append(h)
        res.append(isola)
    return res

def _centro(facce):
    vs = {v for f in facce for v in f.verts}
    mn = Vector((min(v.co.x for v in vs), min(v.co.y for v in vs), min(v.co.z for v in vs)))
    mx = Vector((max(v.co.x for v in vs), max(v.co.y for v in vs), max(v.co.z for v in vs)))
    return (mn + mx) / 2, mx - mn

def _slot(ob, nome, crea=None):
    """Indice dello slot del materiale 'nome' (creato con crea() se manca)."""
    for i, s in enumerate(ob.material_slots):
        if s.material and s.material.name == nome:
            return i
    m = bpy.data.materials.get(nome) or crea(nome)
    ob.data.materials.append(m)
    return len(ob.material_slots) - 1

def _mat_semplice(nome, colore, rugo, metallo=0.0, emissione=None):
    m = bpy.data.materials.new(nome); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*colore, 1); b.inputs['Roughness'].default_value = rugo
    b.inputs['Metallic'].default_value = metallo
    if emissione:
        b.inputs['Emission Color'].default_value = (*emissione[0], 1); b.inputs['Emission Strength'].default_value = emissione[1]
    return m

def _in_mondo(ob):
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.transform(ob.matrix_world); bm.normal_update()
    return bm

def _salva_bm(ob, bm):
    bm.transform(ob.matrix_world.inverted()); bm.to_mesh(ob.data); bm.free()

def cilindro_liscio(bm, a, b, r0, r1, seg, mi):
    """Tronco da a a b (raggi r0, r1): facce lisce, UV cilindriche in metri (giro x lunghezza), tappi piani."""
    asse = (b - a); L = asse.length; asse.normalize()
    u = asse.orthogonal().normalized(); w = asse.cross(u)
    uv = bm.loops.layers.uv.verify()
    anelli = [[bm.verts.new(p + (u * math.cos(2 * math.pi * i / seg) + w * math.sin(2 * math.pi * i / seg)) * r)
               for i in range(seg)] for (p, r) in ((a, r0), (b, r1))]
    rm = (r0 + r1) / 2; nuove = []
    for i in range(seg):
        j = (i + 1) % seg
        f = bm.faces.new((anelli[0][i], anelli[0][j], anelli[1][j], anelli[1][i])); f.material_index = mi; f.smooth = True
        nuove.append(f)
        for l, (k, t) in zip(f.loops, ((i, 0), (i + 1, 0), (i + 1, L), (i, L))):
            l[uv].uv = (2 * math.pi * rm * k / seg, t)
    for anello, verso in ((anelli[0], -1), (anelli[1], 1)):
        f = bm.faces.new(anello if verso > 0 else anello[::-1]); f.material_index = mi; f.smooth = False; nuove.append(f)
        c = sum((v.co for v in anello), Vector()) / seg
        for l in f.loops:
            d = l.vert.co - c; l[uv].uv = (d.dot(u) + 0.5, d.dot(w) + 0.5)
    bmesh.ops.recalc_face_normals(bm, faces=nuove)

def correggi_forno(ob):
    """Cupola con UV sferiche; bocca con un bagliore caldo invece del nero."""
    bm = _in_mondo(ob)
    nomi = [s.material.name if s.material else '' for s in ob.material_slots]
    mat = lambda f: nomi[f.material_index]
    bocca = [f for f in bm.faces if mat(f) == 'interno_buio']
    # cupola: UV sferiche (giro all'equatore x arco dal basamento)
    cupola = [f for f in bm.faces if mat(f) == 'intonaco_bianco']
    vs = {v for f in cupola for v in f.verts}
    cc = Vector((sum(v.co.x for v in vs) / len(vs), sum(v.co.y for v in vs) / len(vs), min(v.co.z for v in vs)))
    cc.x = (min(v.co.x for v in vs) + max(v.co.x for v in vs)) / 2; cc.y = (min(v.co.y for v in vs) + max(v.co.y for v in vs)) / 2
    R = (max(v.co.x for v in vs) - min(v.co.x for v in vs)) / 2
    uv = bm.loops.layers.uv.verify()
    for f in cupola:
        az = []
        for l in f.loops:
            d = l.vert.co - cc
            az.append(math.atan2(d.y, d.x))
        if max(az) - min(az) > math.pi:
            az = [a + 2 * math.pi if a < 0 else a for a in az]
        for l, a in zip(f.loops, az):
            d = l.vert.co - cc
            el = math.atan2(d.z, math.hypot(d.x, d.y))
            l[uv].uv = (a * R, el * R)
            f.smooth = True
    # bocca: bagliore del fuoco
    ib = _slot(ob, 'bocca_forno', lambda n: _mat_semplice(n, (0.05, 0.02, 0.01), 0.9, emissione=((1.0, 0.36, 0.09), 0.9)))
    for f in bocca:
        f.material_index = ib
    _salva_bm(ob, bm)

def correggi_falegname(ob):
    """Tronchi a 32 lati con UV cilindriche (a 12-14 lati e UV a scatola sembravano a scalini); la sega
    (un pannello di 2 cm piantato nel tronco) diventa una lama sottile appoggiata sul tronco."""
    bm = _in_mondo(ob)
    nomi = [s.material.name if s.material else '' for s in ob.material_slots]
    mat = lambda f: nomi[f.material_index]
    ilg = nomi.index('legno_grezzo')
    tronchi = []
    for isola in _isole(bm, lambda f: mat(f) == 'legno_grezzo'):
        vs = list({v for f in isola for v in f.verts})
        P = np.array([v.co[:] for v in vs]); m = P.mean(axis=0)
        val, vec = np.linalg.eigh(np.cov((P - m).T))
        asse = Vector(vec[:, 2]); t = (P - m) @ vec[:, 2]
        if t.max() - t.min() < 2.0:
            continue
        rad = np.linalg.norm((P - m) - np.outer(t, vec[:, 2]), axis=1)
        r0 = float(rad[t < t.min() + 0.02].mean()); r1 = float(rad[t > t.max() - 0.02].mean())
        a = Vector(m) + asse * float(t.min()); b = Vector(m) + asse * float(t.max())
        bmesh.ops.delete(bm, geom=isola, context='FACES')
        cilindro_liscio(bm, a, b, r0, r1, SEGMENTI_TRONCO, ilg)
        tronchi.append((a, b, r0, r1))
    bm.normal_update()
    print("  falegname: tronchi ricostruiti", len(tronchi))
    # la sega: lama di ferro e impugnatura sopra il tronco sui cavalletti (il piu' alto)
    a, b, r0, r1 = max(tronchi, key=lambda t: t[0].z)
    asse = (b - a).normalized()
    vecchie = []
    for isola in _isole(bm, lambda f: mat(f) in ('ferro', 'legno_travi')):
        c, dim = _centro(isola)
        tc = (c - a).dot(asse); dist = ((c - a) - asse * tc).length
        if 0 < tc < (b - a).length and dist < 0.75 and c.z > a.z + 0.05 and max(dim) < 0.7:
            vecchie += isola
    bmesh.ops.delete(bm, geom=vecchie, context='FACES')
    # lama appoggiata sul tronco, inclinata di 35 gradi verso est (il lato della strada), lungo l'asse
    th = math.radians(35); su = Vector((0, 0, 1))
    lato = su.cross(asse).normalized()
    if lato.x < 0:
        lato = -lato
    n = (su * math.cos(th) + lato * math.sin(th)).normalized(); giu = asse.cross(n).normalized()
    if giu.z > 0:
        giu = -giu
    L = (b - a).length; r = r0 + (r1 - r0) * 0.6
    base = a + asse * (0.6 * L) + n * (r + 0.004)
    il = _slot(ob, 'lama_sega', lambda nm: _mat_semplice(nm, (0.42, 0.43, 0.45), 0.35, metallo=0.85))
    ig = nomi.index('legno_travi')
    def lastra(pts, sp, mi):
        sotto = [bm.verts.new(p) for p in pts]; sopra = [bm.verts.new(p + n * sp) for p in pts]
        k = len(pts)
        fs = [bm.faces.new(sotto[::-1]), bm.faces.new(sopra)] + \
             [bm.faces.new((sotto[i], sotto[(i + 1) % k], sopra[(i + 1) % k], sopra[i])) for i in range(k)]
        for f in fs:
            f.material_index = mi
        bmesh.ops.recalc_face_normals(bm, faces=fs)
    # lama a trapezio: 0,62 m, alta 0,13 verso l'impugnatura e 0,07 in punta, 2 mm
    p0 = base - asse * 0.31
    lastra([p0 - giu * 0.02, p0 + asse * 0.62 - giu * 0.02, p0 + asse * 0.62 + giu * 0.05, p0 + giu * 0.11], 0.002, il)
    # impugnatura chiusa (anello di legno) all'estremita' larga
    h0 = p0 - asse * 0.13
    lastra([h0 - giu * 0.01, h0 + asse * 0.14 - giu * 0.01, h0 + asse * 0.14 + giu * 0.12, h0 + giu * 0.12], 0.028, ig)
    _salva_bm(ob, bm)

def correggi_festoni(oggetti):
    """La prima corda dei festoni (x -14 -> -9) finiva a nord nel Vicolo della Chiesa, nel vuoto: il capo nord
    va sulla facciata accanto (x -14), con un taglio lineare lungo la corda."""
    for ob in oggetti:
        bm = _in_mondo(ob); k = 0
        for v in bm.verts:
            if v.co.x < -6 and abs(v.co.y) < 13.2:
                t = min(1.0, max(0.0, (v.co.y + 12.0) / 24.0))
                v.co.x -= 5.0 * t; k += 1
        _salva_bm(ob, bm)
        print("  festoni:", ob.name, k, "vertici spostati")

def _isole_di(facce):
    """Gruppi di facce collegate fra loro (per i vertici) dentro l'elenco dato."""
    resto = set(facce); per_vert = {}
    for f in facce:
        for v in f.verts:
            per_vert.setdefault(v, []).append(f)
    isole = []
    while resto:
        pila = [resto.pop()]; isola = []
        while pila:
            f = pila.pop(); isola.append(f)
            for v in f.verts:
                for g in per_vert[v]:
                    if g in resto:
                        resto.remove(g); pila.append(g)
        isole.append(isola)
    return isole

def dondolo(y):
    t = min(1.0, max(0.0, (y + 12.0) / 24.0))   # posizione lungo la corda dei festoni (capi a y = -12 e 12)
    return 4.0 * t * (1.0 - t)

def liberta_tele(scelti):
    """Vento (citta.js): per ogni vertice di tela salva 'liberta' (0 sul bordo fissato ad asta, trave o corda, 1 sul
    bordo libero), 'tela' (tipo: ampiezze e ritmo) e 'oscillo' (festoni: quanto la corda scende sotto la retta fra i
    capi, per il dondolio). Si leggono dalla geometria del generatore:
    - stendardi e banderuole (materiale stendardo, facce lisce; lo stemma della porta e' un prisma piatto e resta
      fermo): appesi alla traversa di ferro in alto, liberta' = discesa dalla cima / altezza. Sotto 1,2 m di
      altezza e' una banderuola in cima a un'asta (torretta del palazzo, porte);
    - teli delle bancarelle e tende delle botteghe: la falda sta sulle travi e resta ferma, si muove solo la balza
      che pende (facce verticali), dal bordo cucito alla falda (0) all'orlo (1);
    - festoni: ogni bandierina e' appesa alla corda per il lato in alto; corde e bandierine dondolano insieme
      attorno alla retta fra i due capi (le corde vanno da y = -12 a y = 12, freccia 1,1 m al centro).
      Solo nell'oggetto "Festoni": i materiali festone_* servono anche per cose rigide (stemma della Porta Sud,
      e la vecchia insegna della locanda, una tavola che il vento piegava come una tela);
    - insegne (INSEGNE): oggetto rigido, tutti i vertici di tipo 'insegna'; citta.js le fa dondolare a pendolo
      attorno al braccio (perno e asse in citta.json, vedi insegne_web)."""
    conta = {}; per_oggetto = {}
    for ob in scelti:
        if ob.type != 'MESH':
            continue
        nomi = [s.material.name if s.material else '' for s in ob.material_slots] or ['']
        festoni = ob.name == 'Festoni'
        tipi = [next((t for p, t in (('stendardo', 'stendardo'), ('telo_', 'telo'), ('tenda_bottega', 'tenda'),
                                      ('festone', 'festone')) if nm.startswith(p) and (t != 'festone' or festoni)), None)
                for nm in nomi]
        corda = ob.name.startswith('Festoni_corde')
        insegna = ob.name in INSEGNE
        if not corda and not insegna and not any(tipi):
            continue
        me = ob.data
        lib = np.zeros(len(me.vertices), np.float32); tela = np.zeros_like(lib); osc = np.zeros_like(lib)
        bm = bmesh.new(); bm.from_mesh(me); bm.transform(ob.matrix_world); bm.normal_update()
        bm.verts.ensure_lookup_table()
        if insegna:   # rigida: niente pieghe, solo il pendolo (lo stesso angolo per tutti i vertici)
            tela[:] = TELE['insegna']; lib[:] = 1.0
            tipi = [None] * len(tipi)
            conta['insegna'] = conta.get('insegna', 0) + 1
        if corda:
            for v in bm.verts:
                tela[v.index] = TELE['festone']; osc[v.index] = dondolo(v.co.y)
            conta['corde festoni'] = conta.get('corde festoni', 0) + 1
        facce = [f for f in bm.faces if tipi[min(f.material_index, len(tipi) - 1)]]
        for isola in _isole_di(facce):
            tipo = tipi[isola[0].material_index]
            vs = {v for f in isola for v in f.verts}
            if tipo in ('stendardo', 'festone'):
                if tipo == 'stendardo' and not all(f.smooth for f in isola):
                    continue
                zmax = max(v.co.z for v in vs); h = zmax - min(v.co.z for v in vs)
                if h < 0.05:
                    continue
                if tipo == 'stendardo' and h < 1.2:
                    tipo = 'banderuola'
                for v in vs:
                    lib[v.index] = (zmax - v.co.z) / h
            else:
                balza = [f for f in isola if abs(f.normal.z) < 0.35]
                if not balza:
                    continue
                fermi = {v for f in isola if abs(f.normal.z) >= 0.35 for v in f.verts}
                vb = {v for f in balza for v in f.verts}
                zmax = max(v.co.z for v in vb); h = zmax - min(v.co.z for v in vb)
                for v in vb - fermi:
                    lib[v.index] = (zmax - v.co.z) / max(h, 0.05)
            for v in vs:
                tela[v.index] = TELE[tipo]
                if tipo == 'festone':
                    osc[v.index] = dondolo(v.co.y)
            conta[tipo] = conta.get(tipo, 0) + 1
        bm.free()
        for nome, val in (('liberta', lib), ('tela', tela), ('oscillo', osc)):
            a = me.attributes.get(nome) or me.attributes.new(nome, 'FLOAT', 'POINT')
            a.data.foreach_set('value', val)
        codici, quanti = np.unique(tela[tela > 0], return_counts=True)
        nome_tipo = {v: k for k, v in TELE.items()}
        per_oggetto[ob.name] = {nome_tipo[int(c)]: int(q) for c, q in zip(codici, quanti)}
    print("Tele per il vento (isole):", conta)
    # controllo: quali oggetti si muovono col vento e con quanti vertici per tipo (rigidi presi per tele?)
    for nome, d in sorted(per_oggetto.items()):
        print("  vento:", nome, d)

def insegne_web(scelti):
    """Perno (origine) e asse del braccio (Y locale) di ogni insegna, in coordinate three, per citta.json."""
    out = []
    for ob in scelti:
        if ob.name in INSEGNE:
            M = ob.matrix_world
            out.append(dict(nome=ob.name, perno=[round(v, 4) for v in b2t(M.translation)],
                            asse=[round(v, 5) for v in b2t(M.col[1].xyz.normalized())]))
    print("Insegne:", out)
    return out

def correzioni(scelti):
    per_nome = {o.name: o for o in scelti}
    if 'Forno_dettagli' in per_nome:
        correggi_forno(per_nome['Forno_dettagli'])
    if 'Falegname_dettagli' in per_nome:
        correggi_falegname(per_nome['Falegname_dettagli'])
    correggi_festoni([o for n, o in per_nome.items() if n.startswith('Festoni')])

# ----------------------------------------------------------------------
#  PRINCIPALE
# ----------------------------------------------------------------------
def uv_pendii(ob):
    """Superfici inclinate (scarpa delle mura, fossato, gradini...): UV proiettate sul piano della faccia, in metri,
    invece della proiezione a scatola che le stira. I tetti hanno gia' le UV lungo la falda."""
    me = ob.data; bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
    uv = bm.loops.layers.uv.verify()
    nomi = [s.material.name if s.material else '' for s in ob.material_slots]
    n = 0
    for f in bm.faces:
        nz = f.normal.z
        nm = nomi[f.material_index]
        # solo le facce grandi: su cupole, tronchi e teli a righe la proiezione faccia per faccia spezzava la texture
        if 0.15 < abs(nz) < 0.95 and nm not in TETTI_WEB and not nm.startswith(A_RIGHE) and f.calc_area() > AREA_PENDIO:
            t = Vector((-f.normal.y, f.normal.x, 0.0)).normalized(); b = f.normal.cross(t)
            for l in f.loops:
                l[uv].uv = (l.vert.co.dot(t), l.vert.co.dot(b))
            n += 1
    bm.to_mesh(me); bm.free()
    return n

def _estrai(me_src, maschera, nome):
    me = me_src.copy(); me.name = nome
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not maschera[f.index]], context='FACES')
    bm.to_mesh(me); bm.free()
    return me

def _chiavi(me, lato):
    c = np.empty(len(me.polygons) * 3, np.float32); me.polygons.foreach_get('center', c); c = c.reshape(-1, 3)
    return np.floor(c[:, 0] / lato).astype(np.int64), np.floor(c[:, 1] / lato).astype(np.int64)

def dividi_in_riquadri(ob, lato, sc):
    """Un oggetto per riquadro di 'lato' m (per centro faccia) + uno per la campagna: ogni mesh resta piccola,
    quindi la quantizzazione delle posizioni e' precisa al millimetro e three puo' scartare cio' che non vede."""
    me = ob.data
    nomi = [s.material.name if s.material else '' for s in ob.material_slots]
    mi = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('material_index', mi)
    prato = np.array(['prato' in n for n in nomi], bool)[mi]
    kx, ky = _chiavi(me, lato)
    pezzi = []
    if prato.any():
        pezzi.append(_estrai(me, prato, ob.name + "_campagna"))
    for r in np.unique(ky[~prato]):
        riga = _estrai(me, (~prato) & (ky == r), ob.name + "_riga")
        kxr, _ = _chiavi(riga, lato)
        for c in np.unique(kxr):
            pezzi.append(_estrai(riga, kxr == c, "%s_%d_%d" % (ob.name, c, r)))
        bpy.data.meshes.remove(riga)
    oggetti = []
    for m in pezzi:
        if len(m.polygons) == 0:
            bpy.data.meshes.remove(m); continue
        o = bpy.data.objects.new(m.name, m); sc.collection.objects.link(o); oggetti.append(o)
    return oggetti

def _convesso(f):
    """Quadrilatero convesso: i prodotti vettoriali dei lati consecutivi vanno tutti nel verso della normale."""
    vs = [v.co for v in f.verts]; n = f.normal
    return all((vs[(i + 1) % 4] - vs[i]).cross(vs[(i + 2) % 4] - vs[(i + 1) % 4]).dot(n) > 1e-9 for i in range(4))

def suddividi(ob, lato):
    me = ob.data; bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
    nomi = [s.material.name if s.material else '' for s in ob.material_slots]
    # prima i triangoli per i poligoni e i quadrilateri concavi: i muri forati dal booleano sono concavi (a U attorno
    # alle finestre) e la suddivisione li riempiva con facce che attraversavano i fori (finestre ridotte a fessure)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4 or (len(f.verts) == 4 and not _convesso(f))],
                          quad_method='BEAUTY', ngon_method='EAR_CLIP')
    for _ in range(5):
        lunghi = [e for e in bm.edges if e.calc_length() > lato and
                  not any(nomi[f.material_index].startswith('prato') for f in e.link_faces)]
        if not lunghi:
            break
        bmesh.ops.subdivide_edges(bm, edges=lunghi, cuts=1, use_grid_fill=True)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(me); bm.free()

def main():
    t0 = time.time(); sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    info_imp, alberi = impostori()
    print("Impostori:", len(info_imp), "varianti,", len(alberi), "alberi", round(time.time() - t0, 1), "s")
    camere = {}
    for o in sc.objects:
        if o.type == 'CAMERA':
            fwd = o.matrix_world.to_quaternion() @ Vector((0, 0, -1))
            vfov = 2 * math.atan((o.data.sensor_width * 9 / 16 / 2) / o.data.lens)
            camere[o.name] = dict(p=b2t(o.matrix_world.translation), m=b2t(o.matrix_world.translation + fwd * 10),
                                  fov=round(math.degrees(vfov), 3), shift=o.data.shift_y)
    # oggetti da esportare
    scelti = []
    for ob in list(sc.objects):
        if ob.type not in ('MESH', 'CURVE') or not ob.visible_get() or ob.name.startswith(('Foschia', 'Vegetazione')):
            continue
        for mo in [mo for mo in ob.modifiers if mo.type == 'BEVEL']:
            ob.modifiers.remove(mo)
        if ob.type == 'CURVE':
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
            nuovo = bpy.data.objects.new(ob.name + "_mesh", me); sc.collection.objects.link(nuovo)
            nuovo.matrix_world = ob.matrix_world; ob.hide_render = True; ob = nuovo
        if ob.data.users > 1:
            ob.data = ob.data.copy()
        scelti.append(ob)
    correzioni(scelti)
    liberta_tele(scelti)
    insegne = insegne_web(scelti)
    tri0 = 0; tri1 = 0
    for ob in scelti:
        if SEMPLIFICA_INTERNI and ob.name.startswith('Interno_'):
            a, b, _ = semplifica_interno(ob); tri0 += a; tri1 += b
    print("Case interne: facce", tri0, "->", tri1, round(time.time() - t0, 1), "s")
    for ob in scelti:
        dip = set(ob.get('_dipinti', '').split(';')) - {''}
        originali = [t.material.name if t.material else '' for t in ob.material_slots]
        for i, s in enumerate(ob.material_slots):
            if not s.material:
                continue
            nm = originali[i]
            primo = originali.index(nm)
            w, d = materiale_web(s.material)
            if nm in dip and i != primo and d['diff'] is not None:   # lo slot aggiunto per i muri dipinti
                s.material = materiale_finestre(nm, d)
            else:
                s.material = w
    print("Materiali web:", len(_MAT_WEB), "+", len(_FINESTRE), "dipinti; immagini:", len(_IMMAGINI), round(time.time() - t0, 1), "s")
    # un solo oggetto, poi uno per zona
    for o in sc.objects:
        o.select_set(False)
    with bpy.context.temp_override(active_object=scelti[0], object=scelti[0], selected_objects=scelti,
                                   selected_editable_objects=scelti):
        bpy.ops.object.join()
    tutto = scelti[0]; tutto.name = "Citta"
    zone = {}
    for z in ZONE:
        me = tutto.data.copy(); ob = bpy.data.objects.new("Zona_" + z, me); sc.collection.objects.link(ob)
        ob.matrix_world = tutto.matrix_world
        bm = bmesh.new(); bm.from_mesh(me)
        nomi = [s.material.name if s.material else '' for s in ob.material_slots]
        via = [f for f in bm.faces if (('prato' in nomi[f.material_index]) and z != 'centro') or
               (not 'prato' in nomi[f.material_index] and zona_di(*(tutto.matrix_world @ f.calc_center_median()).xy) != z)]
        bmesh.ops.delete(bm, geom=via, context='FACES'); bm.to_mesh(me); bm.free()
        suddividi(ob, LATO_MAX_AO)
        uv_pendii(ob)
        zone[z] = ob
    bpy.data.objects.remove(tutto)
    print("Zone:", {z: len(o.data.polygons) for z, o in zone.items()}, round(time.time() - t0, 1), "s")
    # occlusione ambientale cotta nei colori dei vertici (solo le zone e gli alberi fanno ombra)
    for o in sc.objects:
        if o.type in ('MESH', 'CURVE') and not o.name.startswith('Zona_'):
            o.hide_render = True
    sc.render.engine = 'CYCLES'; sc.cycles.samples = CAMPIONI_AO
    try:
        sc.cycles.device = 'GPU'
    except Exception:
        pass
    sc.world.light_settings.distance = DISTANZA_AO
    # terreno: facce girate verso l'alto (alcuni nastri erano rivolti in basso: in Cycles non si vede);
    # durante la cottura gli strati di suolo scendono tutti di 6 cm, cosi' la base dei muri (z = 0) non
    # resta sotto il selciato (z = 0,02) e l'ordine fra gli strati non cambia
    giu = {}
    for z, ob in zone.items():
        me = ob.data; bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
        for f in bm.faces:
            if f.normal.z < -0.9 and f.calc_center_median().z < 0.15:
                f.normal_flip()
        bm.normal_update()
        idx = {v.index for f in bm.faces if f.normal.z > 0.9 and f.calc_center_median().z < 0.06 for v in f.verts}
        bm.to_mesh(me); bm.free()
        giu[z] = sorted(idx)
        for i in giu[z]:
            me.vertices[i].co.z -= 0.06
    for z, ob in zone.items():
        t1 = time.time()
        attr = ob.data.color_attributes.new("AO", 'FLOAT_COLOR', 'CORNER')   # float: resta lineare (byte = sRGB)
        ob.data.color_attributes.active_color = attr
        for o in sc.objects:
            o.select_set(False)
        ob.select_set(True); bpy.context.view_layer.objects.active = ob
        bpy.ops.object.bake(type='AO', target='VERTEX_COLORS', use_clear=True)
        print("  AO", z, round(time.time() - t1, 1), "s")
    for z, ob in zone.items():
        for i in giu[z]:
            ob.data.vertices[i].co.z += 0.06
        # angoli chiusi dentro le minuterie (cornici, imposte): valgono 0 e anneriscono tutta la faccia;
        # se un angolo e' molto piu' scuro degli altri della stessa faccia prende la mediana della faccia
        me = ob.data; col = me.color_attributes['AO']
        dati = np.empty(len(me.loops) * 4, np.float32); col.data.foreach_get('color', dati)
        ao = dati[0::4].copy()
        inizio = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('loop_start', inizio)
        quanti = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('loop_total', quanti)
        corretti = 0
        for s, n in zip(inizio, quanti):
            v = ao[s:s + n]; m = float(np.median(v))
            if m > 0.08:
                basso = v < 0.5 * m
                if basso.any():
                    v[basso] = m; corretti += int(basso.sum())
        # muri: i vertici dei fori delle finestre stanno dentro davanzali e cornici, la cottura li annerisce;
        # sulle facce verticali l'occlusione viene dall'altezza (scura alla base, chiara da 3 m in su)
        nz = np.empty(len(me.polygons) * 3, np.float32); me.polygons.foreach_get('normal', nz); nz = nz[2::3]
        vi = np.empty(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', vi)
        co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co); zv = co[2::3]
        verticali = np.repeat(np.abs(nz) < 0.3, quanti)
        t = np.clip(zv[vi] / 3.0, 0.0, 1.0); t = t * t * (3 - 2 * t)
        ao[verticali] = (0.55 + 0.45 * t)[verticali]
        xv, yv = co[0::3][vi], co[1::3][vi]   # fontana: vasca e getti dentro l'acqua, la cottura li annerisce
        fontana = (np.hypot(xv, yv) < 4.0) & (zv[vi] < 3.8)
        ao[fontana] = np.maximum(ao[fontana], 0.9)
        # vetri (anche delle bifore, incassati 20 cm): l'AO cotta spegneva il riflesso del cielo, nero pieno
        mi = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('material_index', mi)
        nomi = [sl.material.name if sl.material else '' for sl in ob.material_slots] or ['']
        vetro = np.repeat(np.array([nm.startswith('vetro') for nm in nomi], bool)[np.minimum(mi, len(nomi) - 1)], quanti)
        ao[vetro] = np.maximum(ao[vetro], 0.9)
        # R = occlusione; G, B, A = vento (liberta', tipo di tela / 8, dondolio dei festoni)
        dati[0::4] = ao
        for k, nome, scala in ((1, 'liberta', 1.0), (2, 'tela', 1.0 / 8.0), (3, 'oscillo', 1.0)):
            a = me.attributes.get(nome)
            if a is None:
                dati[k::4] = 0.0; continue
            val = np.empty(len(me.vertices), np.float32); a.data.foreach_get('value', val)
            dati[k::4] = val[vi] * scala
        col.data.foreach_set('color', dati)
        print("  AO", z, "angoli corretti:", corretti)
    # esportazione: una .gltf per zona, divisa in riquadri, texture esterne condivise
    voci = []
    for z, ob in zone.items():
        riquadri = dividi_in_riquadri(ob, LATO_RIQUADRO, sc)
        print("  riquadri", z, len(riquadri))
        for o in sc.objects:
            o.select_set(False)
        for o in riquadri:
            o.select_set(True)
        bpy.context.view_layer.objects.active = riquadri[0]
        d = os.path.join(ESPORT, z); os.makedirs(d, exist_ok=True)
        bpy.ops.export_scene.gltf(filepath=os.path.join(d, z + ".gltf"), export_format='GLTF_SEPARATE',
                                  export_texture_dir="tex", use_selection=True, export_image_format='AUTO',
                                  export_vertex_color='ACTIVE', export_cameras=False, export_lights=False, export_yup=True)
        pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        tri = sum(len(p.vertices) - 2 for p in ob.data.polygons)
        voci.append(dict(nome=z, file=z + ".gltf", triangoli=tri,
                         min=b2t((min(p.x for p in pts), max(p.y for p in pts), min(p.z for p in pts))),
                         max=b2t((max(p.x for p in pts), min(p.y for p in pts), max(p.z for p in pts)))))
    dati = dict(zone=voci, impostori=info_imp, alberi=alberi, camere=camere, insegne=insegne)
    with open(os.path.join(PUBBLICO, "citta.json"), "w", encoding="utf-8") as f:
        json.dump(dati, f, separators=(',', ':'))
    print("Triangoli per zona:", {v['nome']: v['triangoli'] for v in voci})
    print("Fatto in", round(time.time() - t0, 1), "s")

main()
