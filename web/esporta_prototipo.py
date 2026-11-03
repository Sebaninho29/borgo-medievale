# -*- coding: utf-8 -*-
"""
esporta_prototipo.py  -  Fase 2, passo 1: esporta piazza e Via Maestra in glTF (.glb) per il prototipo web.

Apre il .blend del borgo in sola lettura (non lo salva mai) e scrive web/_esportazione/prototipo.glb;
poi "npm run modello" lo comprime (meshopt) in web/public/modelli/prototipo.glb:
    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" --background
        "%USERPROFILE%\\Documents\\Blender\\Quartiere_Mercato\\quartiere_mercato.blend" --python web\\esporta_prototipo.py

Cosa fa:
- tiene solo gli oggetti della zona (piazza + corridoio della Via Maestra fino alla Porta Est);
  gli oggetti grandi (selciato, suolo, mura, isolati interni) vengono ritagliati faccia per faccia;
- toglie gli smussi (troppi triangoli per il web), salta alberi, campagna e foschia;
- converte i materiali procedurali in materiali glTF semplici: texture 1k con tinta e saturazione gia'
  applicate ai pixel, mappa normale, rugosita' costante; righe dei teli come piccola texture generata;
- unisce tutto in un'unica mesh (una draw call per materiale) ed esporta il .glb.
"""
import bpy, os, math, time
import numpy as np
from mathutils import Vector

# ============================== PARAMETRI ==============================
LATO_TEX   = 1024          # lato delle texture esportate
QUALITA_JPG = 82
MARGINE    = 2.0           # margine (m) per il ritaglio faccia per faccia
# =======================================================================

QUI = os.path.dirname(os.path.abspath(__file__))
USCITA = os.path.join(QUI, "_esportazione")        # .glb grezzo; "npm run modello" lo comprime in public/
TEX_TMP = os.path.join(QUI, "_tex_esportazione")     # texture intermedie (rigenerabili)
os.makedirs(USCITA, exist_ok=True); os.makedirs(TEX_TMP, exist_ok=True)

def nella_zona(x, y, m=0.0):
    """Piazza del mercato e corridoio della Via Maestra (fino al ponte fuori dalla Porta Est)."""
    if -32 - m <= x <= 32 + m and -28 - m <= y <= 28 + m:
        return True
    if 14 - m <= x <= 128 + m:
        return abs(y - (0.6 + (x - 32) * 0.186)) <= 26 + m
    return False

DA_RITAGLIARE = ('Selciato', 'Suolo', 'Strada_di_ronda', 'Fossato', 'Mura', 'Interno_', 'Vicoli_e_cortili',
                 'Accessori_', 'Lastricati_')
DA_SALTARE = ('Foschia', 'Campagna', 'Vegetazione')

# ----------------------------------------------------------------------
#  TEXTURE E MATERIALI PER IL WEB
# ----------------------------------------------------------------------
def srgb_lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def lin_srgb(c): return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0), 1 / 2.4) - 0.055)

_IMMAGINI = {}
def immagine_web(img, tinta=None, sat=1.0, dati=False):
    """Copia ridotta a LATO_TEX dell'immagine, con tinta e saturazione applicate (in lineare), salvata in JPEG."""
    chiave = (img.name, tinta, round(sat, 3))
    if chiave in _IMMAGINI:
        return _IMMAGINI[chiave]
    nuova = img.copy()
    nuova.scale(LATO_TEX, LATO_TEX)
    if not dati and (tinta is not None or sat != 1.0):
        px = np.empty(LATO_TEX * LATO_TEX * 4, np.float32); nuova.pixels.foreach_get(px); px = px.reshape(-1, 4)
        rgb = srgb_lin(px[:, :3])
        if sat != 1.0:
            lum = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
            rgb = lum[:, None] + (rgb - lum[:, None]) * sat
        if tinta is not None:
            rgb = rgb * np.array(tinta, np.float32)
        px[:, :3] = lin_srgb(np.clip(rgb, 0.0, 1.0)); nuova.pixels.foreach_set(px.ravel())
    nome = os.path.splitext(os.path.basename(img.filepath))[0] + ("_t%d" % len(_IMMAGINI) if (tinta or sat != 1.0) else "")
    nuova.filepath_raw = os.path.join(TEX_TMP, nome + ".jpg"); nuova.file_format = 'JPEG'
    nuova.save()
    if dati:
        nuova.colorspace_settings.name = 'Non-Color'
    _IMMAGINI[chiave] = nuova
    return nuova

def immagine_righe(c1, c2):
    """Texture 64x4 a due bande per i teli a righe (stessa resa del materiale 'tessuto')."""
    img = bpy.data.images.new("righe_%d" % len(_IMMAGINI), 64, 4)
    px = np.zeros((4, 64, 4), np.float32)
    px[:, :32, :3] = lin_srgb(np.array(c1, np.float32)); px[:, 32:, :3] = lin_srgb(np.array(c2, np.float32)); px[..., 3] = 1
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = os.path.join(TEX_TMP, img.name + ".png"); img.file_format = 'PNG'; img.save()
    _IMMAGINI[img.name] = img
    return img

def _collegato_da(sock, tipo):
    return sock.is_linked and sock.links[0].from_node.type == tipo

def leggi_materiale(m):
    """Ricava dal materiale procedurale: texture, scala UV, tinta, saturazione, colore, righe, emissione."""
    d = dict(diff=None, nor=None, forza_nor=1.0, scala=1.0, tinta=None, sat=1.0, colore=None, righe=None,
             rugo=0.8, metallo=0.0, emissione=None, alfa=1.0)
    if not m.use_nodes or m.node_tree is None:
        d['colore'] = tuple(m.diffuse_color[:3]); return d
    nodi = m.node_tree.nodes
    b = next((n for n in nodi if n.type == 'BSDF_PRINCIPLED'), None)
    for n in nodi:
        if n.type == 'TEX_IMAGE' and n.image:
            f = n.image.filepath.lower()
            if '_diff_' in f: d['diff'] = n.image
            elif '_nor_gl_' in f: d['nor'] = n.image
        elif n.type == 'MAPPING' and _collegato_da(n.inputs['Vector'], 'TEX_COORD'):
            if n.inputs['Vector'].links[0].from_socket.name == 'UV':
                d['scala'] = n.inputs['Scale'].default_value[0]
        elif n.type == 'NORMAL_MAP':
            d['forza_nor'] = n.inputs['Strength'].default_value
        elif n.type == 'MIX' and n.data_type == 'RGBA':
            fa = n.inputs[0]
            A = next(s for s in n.inputs if s.name == 'A' and s.type == 'RGBA')
            B = next(s for s in n.inputs if s.name == 'B' and s.type == 'RGBA')
            if n.blend_type == 'MULTIPLY' and not fa.is_linked and fa.default_value > 0.99 and not B.is_linked \
                    and _collegato_da(A, 'HUE_SAT'):
                d['tinta'] = tuple(B.default_value[:3])          # la tinta di pbr()
            if n.blend_type == 'MIX' and fa.is_linked and fa.links[0].from_node.type == 'MATH' \
                    and fa.links[0].from_node.operation == 'GREATER_THAN':
                d['righe'] = (tuple(A.default_value[:3]), tuple(B.default_value[:3]))   # tessuto a righe
        elif n.type == 'HUE_SAT' and not n.inputs['Saturation'].is_linked and n.inputs['Saturation'].default_value < 0.99:
            d['sat'] = n.inputs['Saturation'].default_value                            # desatura()
        elif n.type == 'RGB':
            d['colore'] = tuple(n.outputs[0].default_value[:3])
        elif n.type == 'MATH' and n.operation == 'MULTIPLY' and d['righe'] is None and not n.inputs[1].is_linked:
            d['passo_righe'] = 1.0 / max(1e-3, n.inputs[1].default_value)
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

_MAT_WEB = {}
def materiale_web(m):
    if m.name in _MAT_WEB:
        return _MAT_WEB[m.name]
    d = leggi_materiale(m)
    w = bpy.data.materials.new(m.name + "_web"); w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear(); L = nt.links
    out = nt.nodes.new('ShaderNodeOutputMaterial'); b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    L.new(b.outputs[0], out.inputs['Surface'])
    b.inputs['Roughness'].default_value = min(1.0, d['rugo']); b.inputs['Metallic'].default_value = d['metallo']
    def uv(scala):
        tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (scala[0], scala[1], 1.0)
        L.new(tc.outputs['UV'], mp.inputs['Vector']); return mp.outputs[0]
    if d['diff'] is not None:
        vec = uv((d['scala'], d['scala']))
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = immagine_web(d['diff'], d['tinta'], d['sat'])
        L.new(vec, t.inputs['Vector']); L.new(t.outputs['Color'], b.inputs['Base Color'])
        if d['nor'] is not None:
            tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = immagine_web(d['nor'], dati=True)
            tn.image.colorspace_settings.name = 'Non-Color'
            nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = d['forza_nor']
            L.new(vec, tn.inputs['Vector']); L.new(tn.outputs['Color'], nm.inputs['Color']); L.new(nm.outputs['Normal'], b.inputs['Normal'])
    elif d['righe'] is not None:
        passo = d.get('passo_righe', 0.22)
        vec = uv((1.0 / (2 * passo), 1.0))
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = immagine_righe(*d['righe'])
        L.new(vec, t.inputs['Vector']); L.new(t.outputs['Color'], b.inputs['Base Color'])
    else:
        c = d['colore'] or (0.5, 0.5, 0.5)
        b.inputs['Base Color'].default_value = (*c, 1.0)
    if d['emissione']:
        b.inputs['Emission Color'].default_value = (*d['emissione'][0], 1.0)
        b.inputs['Emission Strength'].default_value = d['emissione'][1]
    if d['alfa'] < 0.99:
        b.inputs['Alpha'].default_value = d['alfa']
    _MAT_WEB[m.name] = w
    return w

# ----------------------------------------------------------------------
#  SELEZIONE, RITAGLIO, UNIONE, ESPORTAZIONE
# ----------------------------------------------------------------------
def ritaglia(ob):
    """Tiene solo le facce con il centro nella zona (coordinate di mondo)."""
    import bmesh
    me = ob.data; bm = bmesh.new(); bm.from_mesh(me)
    Mw = ob.matrix_world
    via = [f for f in bm.faces if not nella_zona(*(Mw @ f.calc_center_median()).xy, MARGINE)]
    bmesh.ops.delete(bm, geom=via, context='FACES')
    bm.to_mesh(me); bm.free()
    return len(me.polygons) > 0

def main():
    t0 = time.time()
    dg = bpy.context.evaluated_depsgraph_get()
    scelti = []
    for ob in list(bpy.context.scene.objects):
        if ob.type not in ('MESH', 'CURVE') or not ob.visible_get() or ob.name.startswith(DA_SALTARE):
            continue
        for mo in [mo for mo in ob.modifiers if mo.type == 'BEVEL']:
            ob.modifiers.remove(mo)
        if ob.type == 'CURVE':   # getti della fontana, corde dei festoni: in mesh
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
            nuovo = bpy.data.objects.new(ob.name + "_mesh", me); bpy.context.scene.collection.objects.link(nuovo)
            nuovo.matrix_world = ob.matrix_world; ob = nuovo
        if ob.name.startswith(DA_RITAGLIARE):
            if ritaglia(ob):
                scelti.append(ob)
        else:
            c = ob.matrix_world @ (sum((Vector(v) for v in ob.bound_box), Vector()) / 8.0)
            if nella_zona(c.x, c.y):
                scelti.append(ob)
    print("Oggetti nella zona:", len(scelti))
    bpy.context.view_layer.update()
    for ob in scelti:   # controllo: nessun oggetto deve uscire molto dalla zona (il Suolo e' un solo poligono: esce)
        pts = [ob.matrix_world @ Vector(v) for v in ob.bound_box]
        if min(p.x for p in pts) < -45 or max(p.x for p in pts) > 140 or max(abs(p.y) for p in pts) > 55:
            print("  fuori zona:", ob.name, [round(min(p.x for p in pts)), round(max(p.x for p in pts)),
                                              round(min(p.y for p in pts)), round(max(p.y for p in pts))])
    for ob in scelti:
        if ob.data.users > 1:
            ob.data = ob.data.copy()
        for s in ob.material_slots:
            if s.material:
                s.material = materiale_web(s.material)
    print("Materiali web:", len(_MAT_WEB), "texture:", len(_IMMAGINI), round(time.time() - t0, 1), "s")
    for ob in bpy.context.scene.objects:
        ob.select_set(False)
    with bpy.context.temp_override(active_object=scelti[0], object=scelti[0], selected_objects=scelti,
                                   selected_editable_objects=scelti):
        bpy.ops.object.join()
    unico = scelti[0]; unico.name = "Prototipo_Piazza_Via_Maestra"
    tri = sum(len(p.vertices) - 2 for p in unico.data.polygons)
    print("Triangoli:", tri, "materiali:", len(unico.material_slots))
    unico.select_set(True); bpy.context.view_layer.objects.active = unico
    percorso = os.path.join(USCITA, "prototipo.glb")
    bpy.ops.export_scene.gltf(filepath=percorso, export_format='GLB', use_selection=True, export_apply=False,
                              export_image_format='JPEG', export_cameras=False, export_lights=False, export_yup=True)
    print("Esportato", percorso, round(os.path.getsize(percorso) / 1e6, 1), "MB in", round(time.time() - t0, 1), "s")

main()
