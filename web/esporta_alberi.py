# Alberi veri per il web (livello di dettaglio vicino, entro ~30 m; oltre restano gli impostori di esporta_borgo.py).
# Si apre la scena di Blender e NON la si salva: per ogni variante instanziata (island_tree_02_0, jacaranda_tree_0,
# shrub_02_0..3) scrive in _esportazione/alberi/<variante>.glb la geometria nello spazio dell'istanza (come gli
# impostori: origine nell'offset della collezione) e in public/citta/alberi/alberi.json la descrizione.
#  - alberi: tronco e rami dei modelli Poly Haven decimati (corteccia in 3D), chioma fatta di "ciuffi": carte piccole
#    sparse nel volume della chioma dove stanno le foglie vere, orientate un po' a caso e un po' verso l'esterno, con
#    la texture presa da un render delle foglie vere (atlante 2 x 2 di ciuffi diversi, sfondo trasparente).
#    Normali delle carte "a sfera" dal centro della chioma e occlusione nei colori dei vertici (piu' scuro dentro e
#    sotto la chioma): da sotto non si vedono piu' due piani incrociati ma tante foglie a strati.
#  - cespugli: la mesh vera (foglie modellate, opache) decimata.
# Uso:
#   "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background "D:\Quartiere_Mercato\Blender\quartiere_mercato.blend" --python web\esporta_alberi.py
#   poi: npm run alberi   (meshopt, texture WebP 1k e 512 px)
import bpy, bmesh, os, json, math, random, time, shutil
import numpy as np
from mathutils import Vector, Matrix

# ============================== PARAMETRI ==============================
QUI = os.path.dirname(os.path.abspath(__file__))
ESPORT = os.path.join(QUI, "_esportazione", "alberi")
PUBBLICO = os.path.join(QUI, "public", "citta", "alberi")
SEME = 7
# per specie: triangoli di tronco+rami, numero di ciuffi, raggio del ciuffo (unita' del modello), quanto le carte
# guardano verso l'esterno (0 = a caso), grandezza delle carte rispetto al ciuffo
SPECIE = {
    'island_tree_02': dict(corteccia=5000, carte=520, raggio=0.30, fuori=0.7, grandezza=(0.9, 1.3)),
    'jacaranda_tree': dict(corteccia=20000, carte=1150, raggio=1.15, fuori=0.7, grandezza=(0.9, 1.3)),
    'shrub_02': dict(riduzione=0.5),
}
LATO_TILE = 512           # un ciuffo dell'atlante (l'atlante e' 2 x 2)
COPERTURA_MIN = 0.30      # frazione minima di pixel di foglia in un ciuffo (altrimenti si sceglie un altro punto)
# =======================================================================

rng = random.Random(SEME)
sc = bpy.context.scene
os.makedirs(ESPORT, exist_ok=True); os.makedirs(PUBBLICO, exist_ok=True)

def specie_di(v):
    return v.rsplit('_', 1)[0]

def mesh_collezione(col):
    """Tutte le mesh della collezione unite in un bmesh, nello spazio dell'istanza (meno instance_offset)."""
    bm = bmesh.new(); mats = []
    off = Matrix.Translation(-Vector(col.instance_offset))
    for o in col.all_objects:
        if o.type != 'MESH':
            continue
        tmp = bmesh.new(); tmp.from_mesh(o.data); tmp.transform(off @ o.matrix_world)
        base = len(mats); mats += [s.material for s in o.material_slots]
        for f in tmp.faces:
            f.material_index += base
        me = bpy.data.meshes.new("_tmp"); tmp.to_mesh(me); tmp.free()
        bm.from_mesh(me); bpy.data.meshes.remove(me)
    return bm, mats

def oggetto_da_bm(nome, bm, mats):
    me = bpy.data.meshes.new(nome); bm.to_mesh(me)
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(nome, me); sc.collection.objects.link(ob)
    return ob

def tieni(bm, test):
    """Copia del bmesh con le sole facce che passano il test (materiale)."""
    c = bm.copy()
    bmesh.ops.delete(c, geom=[f for f in c.faces if not test(f)], context='FACES')
    return c

def decima(ob, triangoli):
    tri = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    if tri <= triangoli:
        return tri
    mo = ob.modifiers.new("d", 'DECIMATE'); mo.ratio = triangoli / tri; mo.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.remove(mo); vecchia = ob.data; ob.data = me; bpy.data.meshes.remove(vecchia)
    tri = sum(len(p.vertices) - 2 for p in me.polygons)
    if tri > triangoli * 1.15:
        # la decimazione non scende sotto i pezzi staccati (migliaia di rametti): si tolgono i piu' piccoli,
        # che stanno dentro la chioma, finche' non si torna sotto la quota
        bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
        isole = []; visto = set()
        for f in bm.faces:
            if f.index in visto:
                continue
            pila = [f]; isola = []; visto.add(f.index)
            while pila:
                g = pila.pop(); isola.append(g)
                for e in g.edges:
                    for h in e.link_faces:
                        if h.index not in visto:
                            visto.add(h.index); pila.append(h)
            isole.append((sum(g.calc_area() for g in isola), isola))
        isole.sort(key=lambda x: x[0])
        via = []
        for area, isola in isole:
            if tri <= triangoli:
                break
            via += isola; tri -= sum(len(g.verts) - 2 for g in isola)
        bmesh.ops.delete(bm, geom=via, context='FACES')
        bm.to_mesh(me); bm.free()
        print(f"    tolti {len(via)} poligoni di rametti piccoli")
    return tri

def immagine_diff(m):
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image and '_diff' in n.image.name:
            return n.image
    return None

def tinta_corteccia(m):
    """Tinta lineare che il generatore moltiplica sul colore della corteccia (TINTA_CORTECCIA in genera_quartiere.py:
    nodo Mix MULTIPLY fra la texture e il Base Color); 1, 1, 1 se non c'e'. Il sito la usa uguale."""
    b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b and b.inputs['Base Color'].links:
        n = b.inputs['Base Color'].links[0].from_node
        if n.type == 'MIX' and n.blend_type == 'MULTIPLY':
            sock = next((s for s in n.inputs if s.name == 'B' and s.type == 'RGBA'), None)
            if sock is not None and not sock.links:
                return [round(c, 4) for c in sock.default_value[:3]]
    return [1.0, 1.0, 1.0]

def copia_texture(img, nome):
    """Texture originale (jpg 1k) nella cartella di esportazione: npm run alberi la converte in WebP."""
    src = bpy.path.abspath(img.filepath)
    dst = os.path.join(ESPORT, nome + os.path.splitext(src)[1].lower())
    shutil.copyfile(src, dst)
    return os.path.basename(dst)

# --- atlante dei ciuffi: render ortografico delle foglie vere in un cubo attorno a un punto della chioma ---------
def prepara_render():
    s2 = bpy.data.scenes.new("_ciuffi")
    motori = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    s2.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in motori else 'CYCLES'
    if s2.render.engine == 'CYCLES':
        s2.cycles.samples = 16
    s2.render.film_transparent = True
    s2.render.resolution_x = s2.render.resolution_y = LATO_TILE
    s2.render.image_settings.file_format = 'PNG'; s2.render.image_settings.color_mode = 'RGBA'
    s2.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new("_ciuffi"); w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
    s2.world = w
    cd = bpy.data.cameras.new("_cam"); cd.type = 'ORTHO'
    cam = bpy.data.objects.new("_cam", cd); s2.collection.objects.link(cam); s2.camera = cam
    return s2, cam

def solo_colore(m):
    """Materiale delle foglie in emissione del solo colore della texture: l'atlante e' l'albedo (la luce la mette three)."""
    nt = m.node_tree; out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    img = next(n for n in nt.nodes if n.type == 'TEX_IMAGE' and n.image and '_diff' in n.image.name)
    em = nt.nodes.new('ShaderNodeEmission'); nt.links.new(img.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])

def atlante(ob_foglie, centri, R, nome):
    s2, cam = prepara_render()
    e = ob_foglie.copy(); s2.collection.objects.link(e)
    tiles = []; prove = 0
    while len(tiles) < 4 and prove < 40:
        prove += 1
        c = Vector(centri[rng.randrange(len(centri))])
        a = rng.uniform(0, 2 * math.pi); el = rng.uniform(-0.35, 0.5)
        d = Vector((math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el)))
        cam.data.ortho_scale = 2 * R
        cam.location = c + d * (R + 5.0); cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        cam.data.clip_start = 5.0; cam.data.clip_end = 5.0 + 2 * R
        f = os.path.join(ESPORT, f"_tile_{nome}_{len(tiles)}.png")
        s2.render.filepath = f
        bpy.ops.render.render(write_still=True, scene=s2.name)
        img = bpy.data.images.load(f); px = np.array(img.pixels[:], np.float32).reshape(LATO_TILE, LATO_TILE, 4)
        bpy.data.images.remove(img)
        cop = float((px[..., 3] > 0.5).mean())
        if cop >= COPERTURA_MIN:
            # bordo sfumato: le foglie tagliate dal cubo spariscono verso il bordo del ciuffo (niente spigoli dritti)
            yy, xx = np.mgrid[0:LATO_TILE, 0:LATO_TILE] / (LATO_TILE - 1) * 2 - 1
            r = np.sqrt(xx * xx + yy * yy)
            px[..., 3] *= np.clip((1.0 - r) / 0.25, 0.0, 1.0)
            tiles.append(px)
        os.remove(f)
    if len(tiles) < 4:
        raise RuntimeError(f"atlante {nome}: solo {len(tiles)} ciuffi con copertura sufficiente")
    A = np.zeros((2 * LATO_TILE, 2 * LATO_TILE, 4), np.float32)
    for k, t in enumerate(tiles):   # pixels di Blender: riga 0 in basso; tile k: colonna k % 2, riga k // 2 (dal basso)
        A[(k // 2) * LATO_TILE:(k // 2 + 1) * LATO_TILE, (k % 2) * LATO_TILE:(k % 2 + 1) * LATO_TILE] = t
    # colore dei pixel trasparenti = colore medio delle foglie (niente aloni scuri con il filtro della texture)
    m = A[..., 3] > 0.5; medio = A[m][:, :3].mean(0)
    A[~m, :3] = medio
    im = bpy.data.images.new("_atlante", 2 * LATO_TILE, 2 * LATO_TILE, alpha=True)
    im.pixels.foreach_set(A.ravel()); im.filepath_raw = os.path.join(ESPORT, f"{nome}_foglie.png"); im.file_format = 'PNG'
    im.save()
    bpy.data.objects.remove(e); bpy.data.scenes.remove(s2)
    return os.path.basename(im.filepath_raw)

def chioma(nome, centri, aree, R, n, fuori, grandezza):
    """Carte dei ciuffi: centro su una foglia vera (scelta in proporzione all'area), orientamento misto
    (a caso + verso l'esterno), un ciuffo dell'atlante a caso; normali a sfera e occlusione nei colori dei vertici."""
    C = centri.mean(0); lo = np.percentile(centri, 3, axis=0); hi = np.percentile(centri, 97, axis=0)
    semi = np.maximum((hi - lo) / 2, 1e-3); cc = (hi + lo) / 2
    p_area = aree / aree.sum()
    scelti = np.random.default_rng(SEME).choice(len(centri), size=n, p=p_area)
    bm = bmesh.new(); uv = bm.loops.layers.uv.new("UVMap"); col = bm.loops.layers.float_color.new("AO")
    normali = []
    for i in scelti:
        p = Vector(centri[i]); s = 2 * R * rng.uniform(*grandezza)
        est = Vector(((p.x - cc[0]) / semi[0], (p.y - cc[1]) / semi[1], (p.z - cc[2]) / semi[2]))
        est = est.normalized() if est.length > 1e-4 else Vector((0, 0, 1))
        rnd = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized()
        nrm = (rnd + est * fuori * 1.6).normalized()
        t = nrm.cross(Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)))).normalized()
        b = nrm.cross(t)
        k = rng.randrange(4); u0, v0 = (k % 2) * 0.5, (k // 2) * 0.5; flip = rng.random() < 0.5
        vs = []
        for (a, c, uu, vv) in ((-1, -1, 0, 0), (1, -1, 1, 0), (1, 1, 1, 1), (-1, 1, 0, 1)):
            vs.append((bm.verts.new(p + t * (a * s / 2) + b * (c * s / 2)), (u0 + 0.5 * ((1 - uu) if flip else uu), v0 + 0.5 * vv)))
        f = bm.faces.new([v for v, _ in vs])
        for l, (_, (uu, vv)) in zip(f.loops, vs):
            l[uv].uv = (uu, vv)
            q = l.vert.co
            e = math.sqrt(sum(((q[j] - cc[j]) / semi[j]) ** 2 for j in range(3)))
            altezza = min(1.0, max(0.0, (q.z - lo[2]) / max(hi[2] - lo[2], 1e-3)))
            ao = (0.42 + 0.58 * min(1.0, max(0.0, (e - 0.25) / 0.75))) * (0.72 + 0.28 * altezza)
            l[col] = (ao, ao, ao, 1.0)
    bm.verts.ensure_lookup_table()
    ob = oggetto_da_bm(nome, bm, []); bm.free()
    # normali a sfera dal centro della chioma (come gli impostori): luce e ombra danno volume alla chioma
    me = ob.data
    ns = []
    for v in me.vertices:
        d = Vector(((v.co.x - cc[0]) / semi[0], (v.co.y - cc[1]) / semi[1], (v.co.z - cc[2]) / semi[2]))
        ns.append((d.normalized() * 0.8 + Vector((0, 0, 0.35))).normalized())
    me.normals_split_custom_set_from_vertices(ns)
    me.color_attributes.active_color = me.color_attributes["AO"]
    return ob, dict(centro=[float(x) for x in cc], semi=[float(x) for x in semi])

def esporta(nome_file, oggetti):
    for o in sc.objects:
        o.select_set(False)
    for o in oggetti:
        o.select_set(True)
    bpy.context.view_layer.objects.active = oggetti[0]
    bpy.ops.export_scene.gltf(filepath=os.path.join(ESPORT, nome_file), export_format='GLB', use_selection=True,
                              export_materials='NONE', export_vertex_color='ACTIVE', export_cameras=False,
                              export_lights=False, export_yup=True, export_normals=True, export_texcoords=True)

def main():
    t0 = time.time()
    istanze = [o for o in sc.objects if o.instance_type == 'COLLECTION' and o.instance_collection]
    varianti = sorted({o.instance_collection.name for o in istanze})
    info = {}
    texture_specie = {}
    for v in varianti:
        col = bpy.data.collections[v]; sp = specie_di(v); P = SPECIE[sp]
        bm, mats = mesh_collezione(col)
        nomi = [m.name if m else '' for m in mats]
        zs = [vv.co.z for vv in bm.verts]; base, cima = max(0.0, min(zs)), max(zs)
        parti = []; oggetti = []
        if sp == 'shrub_02':
            ob = oggetto_da_bm(v + "_cespuglio", tieni(bm, lambda f: True), [])
            tri = decima(ob, int(sum(len(f.verts) - 2 for f in bm.faces) * P['riduzione']))
            img = immagine_diff(mats[0])
            tex = texture_specie.setdefault(sp + '_cespuglio', copia_texture(img, sp + "_cespuglio"))
            parti.append(dict(mesh=ob.name, tipo='cespuglio', tex=tex, triangoli=tri)); oggetti.append(ob)
        else:
            foglia = lambda f: 'leaves' in nomi[f.material_index]
            # corteccia: un oggetto per materiale (tronco e rami hanno texture diverse)
            for k, m in enumerate(mats):
                if 'leaves' in nomi[k]:
                    continue
                b2 = tieni(bm, lambda f, k=k: f.material_index == k)
                if not b2.faces:
                    b2.free(); continue
                tri0 = len(b2.faces)
                ob = oggetto_da_bm(f"{v}_{'rami' if 'branches' in nomi[k] else 'tronco'}", b2, []); b2.free()
                quota = P['corteccia'] * (0.6 if 'branches' in nomi[k] else 0.4)
                tri = decima(ob, int(quota))
                tex = texture_specie.setdefault(nomi[k], copia_texture(immagine_diff(m), nomi[k]))
                parti.append(dict(mesh=ob.name, tipo='corteccia', tex=tex, triangoli=tri, tinta=tinta_corteccia(m))); oggetti.append(ob)
                print(f"  {v} {nomi[k]}: {tri0} -> {tri} triangoli")
            # foglie vere: centri e aree delle facce, poi atlante dei ciuffi e carte
            bf = tieni(bm, foglia)
            ob_f = oggetto_da_bm(v + "_foglie_vere", bf, [mats[next(k for k, n in enumerate(nomi) if 'leaves' in n)]]); bf.free()
            me = ob_f.data
            centri = np.empty(len(me.polygons) * 3, np.float32); me.polygons.foreach_get('center', centri); centri = centri.reshape(-1, 3)
            aree = np.empty(len(me.polygons), np.float32); me.polygons.foreach_get('area', aree)
            if sp + '_foglie' not in texture_specie:
                solo_colore(ob_f.data.materials[0])
                texture_specie[sp + '_foglie'] = atlante(ob_f, centri, P['raggio'], sp)
            ob_c, chi = chioma(v + "_chioma", centri, aree, P['raggio'], P['carte'], P['fuori'], P['grandezza'])
            parti.append(dict(mesh=ob_c.name, tipo='foglie', tex=texture_specie[sp + '_foglie'], triangoli=2 * P['carte'], **chi))
            oggetti.append(ob_c)
            bpy.data.objects.remove(ob_f)
        bm.free()
        esporta(v + ".glb", oggetti)
        info[v] = dict(file="alberi/" + v + ".glb", base=round(base, 3), altezza=round(cima - base, 3), parti=parti)
        print("Variante", v, [(p['tipo'], p['triangoli']) for p in parti], round(time.time() - t0, 1), "s")
    with open(os.path.join(PUBBLICO, "alberi.json"), "w", encoding="utf-8") as f:
        json.dump(dict(varianti=info), f, indent=1)
    print("Alberi fatti in", round(time.time() - t0, 1), "s")

main()
