// Caricamento della citta' a zone: occlusione ambientale dai colori dei vertici, texture condivise fra le zone,
// alberi come impostori (piani incrociati instanziati).
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { MeshBVH } from 'three-mesh-bvh';
import { uniformiAcqua, FONTANA_GLSL, GETTO_VERTEX, GETTO_FRAGMENT, VASCA_FRAGMENT } from './fontana.js';

THREE.Cache.enabled = true;   // la stessa immagine scaricata e decodificata una volta sola

// forza dell'occlusione cotta: sulla luce indiretta tutta, su quella diretta solo un poco (come in Cycles)
// minima: luce di base sui materiali in ombra (frazione del colore), al posto della luce rimbalzata che manca
export const uniformiAO = { forza: { value: 1.0 }, sulDiretta: { value: 0.3 }, mostra: { value: 0 }, minima: { value: 0.1 } };

// intonaco vissuto, in coordinate di mondo come in Cycles (genera_quartiere.py, intonaco_vecchio): tono a grandi
// macchie, sporco alla base con il bordo irregolare, qualche crepa sottile
const INTONACO_GLSL = `
varying vec3 vPosMondo;
float h3(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float vn(vec3 x) {
  vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(h3(i), h3(i + vec3(1, 0, 0)), f.x), mix(h3(i + vec3(0, 1, 0)), h3(i + vec3(1, 1, 0)), f.x), f.y),
             mix(mix(h3(i + vec3(0, 0, 1)), h3(i + vec3(1, 0, 1)), f.x), mix(h3(i + vec3(0, 1, 1)), h3(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}
float fbm(vec3 p) { float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * vn(p); p *= 2.03; a *= 0.5; } return s / 0.9375; }
vec3 sporcoBase(vec3 c, vec3 P, vec3 sporco, float forza) {
  float lim = 0.8 + 0.7 * fbm(P * 1.3 + 3.1);
  return mix(c, sporco, clamp(1.0 - (P.y / lim - 0.25) / 0.75, 0.0, 1.0) * forza);
}
vec3 intonacoVissuto(vec3 c, vec3 P) {
  c *= mix(0.82, 1.12, smoothstep(0.35, 0.65, fbm(P * 0.22)));
  c *= mix(vec3(0.97, 0.99, 1.03), vec3(1.03, 1.0, 0.96), smoothstep(0.35, 0.65, fbm(P * 0.11 + 7.3)));
  c = sporcoBase(c, P, vec3(0.16, 0.135, 0.1), 0.6);
  float n = fbm(P * 1.4 + 11.0), w = max(0.012, fwidth(n));
  float linea = (1.0 - smoothstep(0.0, w, abs(n - 0.5))) * 0.012 / w;   // da lontano sbiadisce invece di sfarfallare
  float dove = clamp((fbm(P * 0.3 + 5.0) - 0.6) / 0.08, 0.0, 1.0) * 0.6;
  return c * mix(vec3(1.0), vec3(0.25, 0.22, 0.19), linea * dove);
}
`;

// ============================== VENTO ==============================
// Un'unica brezza leggera per tutto il borgo: il riferimento sono i festoni della piazza. VENTO.forza scala TUTTE le
// ampiezze insieme (tele, festoni, insegna, foglie): 1 = brezza leggera, 0 = aria ferma.
// Regola: piu' un oggetto e' grande e pesante, meno si muove e piu' lento oscilla; nessuno si muove piu' dei festoni
// (dondolio fino a ~15 cm al centro delle corde, periodo ~7 s, bandierine che fremono di 6 cm).
// Tutto nel vertex shader: l'esportatore mette nell'attributo ao g = liberta' (0 sul bordo fissato ad asta, trave o
// corda, 1 sul bordo libero), b = tipo / 8 (1 stendardi, 2 banderuole, 3 teli delle bancarelle, 4 tende delle botteghe,
// 5 festoni, 6 insegna rigida), a = dondolio dei festoni (quanto la corda scende sotto la retta fra i capi).
// Stesso calcolo nel materiale delle ombre.
export const VENTO = {
  forza: 1.0,
  azimut: 20,          // verso in cui soffia (gradi, 0 = verso est, 90 = verso nord, come SOLE_AZIMUT in main.js)
  // riduzioni (main.js): "riduci movimento" del sistema; fps bassi (preset basso)
  ridotto: 0.25, bassoLento: 0.4, fpsLento: 40, fpsRipresa: 55,
  // tele: A piega (m), B spinta sottovento al bordo libero (m), L dondolio laterale del fondo (m),
  // w velocita' dell'onda (rad/s), k numero d'onda (1/m: piccolo = onde lunghe, stoffa pesante), o ritmo del dondolio
  stendardi:  { A: 0.04, B: 0.08, L: 0.07, w: 1.0, k: 1.4, o: 0.45 },   // 3-3,6 m, stoffa pesante (prima 0.12/0.35/0.16)
  banderuole: { A: 0.02, B: 0.04, L: 0.03, w: 1.6, k: 3.0, o: 0.8 },    // piccole, in cima alle aste
  teli:       { A: 0.012, B: 0.012, w: 1.8, k: 5.0 },                   // bancarelle: solo l'orlo della balza
  tende:      { A: 0.01, B: 0.012, w: 1.5, k: 5.0 },                    // botteghe: tela piu' grande e pesante
  festoni:    { th0: 0.04, th1: 0.1, w: 0.9, fremito: 0.06, spinta: 0.05 },   // riferimento: invariati
  // insegna rigida a pendolo attorno al braccio (radianti): inclinazione media sottovento + dondolio, in ritardo
  insegna:    { inclina: 0.03, dondola: 0.025, w: 2.1, ritardo: 0.8 },   // al massimo ~3 gradi: 6 cm al bordo basso
  foglie:     { chioma: 0.05, tremolio: 0.012 },
};
const f = (v) => Number(v).toFixed(4);
const V = VENTO, S = V.stendardi, B = V.banderuole, T = V.teli, D = V.tende, F = V.festoni, N = V.insegna;
export const uniformiVento = { uTempo: { value: 0 }, uVentoDir: { value: new THREE.Vector2(1, 0) },
  uVento: { value: 1 }, uFoglie: { value: 1 },
  uInsPerno: { value: new THREE.Vector3(0, -1000, 0) }, uInsAsse: { value: new THREE.Vector3(0, 0, 1) } };
const VENTO_GLSL = `
uniform float uTempo; uniform vec2 uVentoDir; uniform float uVento; uniform float uFoglie;
uniform vec3 uInsPerno; uniform vec3 uInsAsse;
// raffiche: onde lunghe che attraversano il borgo nel verso del vento, con una modulazione lenta (0.05 - 1)
float rafficaT(vec3 p, float t) {
  float s = dot(p.xz, uVentoDir) * 0.045 - t * 0.35;
  float g = 0.5 + 0.3 * sin(s) + 0.2 * sin(s * 2.3 + 1.7 + t * 0.11);
  g *= 0.75 + 0.25 * sin(t * 0.071 + dot(p.xz, vec2(0.013, 0.021)));
  return clamp(g, 0.05, 1.0);
}
float raffica(vec3 p) { return rafficaT(p, uTempo); }
// rotazione di v attorno al versore a (Rodrigues)
vec3 ruota(vec3 v, vec3 a, float c, float s) { return v * c + cross(a, v) * s + a * dot(a, v) * (1.0 - c); }
// spostamento di un vertice (coordinate del mondo); nv = normale piegata dall'onda o ruotata dal pendolo
vec3 vento(vec3 p, vec3 n, vec4 d, inout vec3 nv) {
  float tipo = floor(d.b * 8.0 + 0.5), l = d.g;
  if (tipo < 0.5 || tipo > 6.5 || uVento <= 0.0) return vec3(0.0);
  vec3 dir = vec3(uVentoDir.x, 0.0, uVentoDir.y), su = vec3(0.0, 1.0, 0.0);
  if (tipo > 5.5) {   // insegna: tavola e catene ruotano rigide attorno al braccio, nessuna piega
    float t = uTempo - ${f(N.ritardo)};                       // la tavola pesante risponde in ritardo alle raffiche
    float g = rafficaT(uInsPerno, t);
    float spinta = dot(cross(uInsAsse, -su), dir);           // quanto il vento spinge sulle facce della tavola
    float th = (${f(N.inclina)} * g * spinta
              + ${f(N.dondola)} * (0.4 + 0.6 * g) * sin(t * ${f(N.w)} + 0.6 * sin(t * 0.37))) * uVento;
    float c = cos(th), s = sin(th);
    vec3 r = p - uInsPerno;
    nv = ruota(n, uInsAsse, c, s);
    return ruota(r, uInsAsse, c, s) - r;
  }
  float g = raffica(p);
  if (tipo > 4.5) {   // festoni: corde e bandierine dondolano piano attorno alla retta fra i capi (corde nord-sud)
    float th = (${f(F.th0)} + ${f(F.th1)} * g) * sin(uTempo * ${f(F.w)} + p.x * 0.15 + 0.6 * sin(uTempo * 0.37));
    float r = d.a * 1.1;   // freccia della corda: 1,1 m al centro
    vec3 s = vec3(r * sin(th), r * (1.0 - cos(th)), 0.0);
    s += vec3(1.0, 0.0, 0.0) * l * ${f(F.fremito)} * sin(uTempo * 5.0 + p.z * 2.1 + p.x) * (0.3 + 0.7 * g)
       + dir * l * ${f(F.spinta)} * g;
    return s * uVento;
  }
  float A, B, w, k;
  if (tipo < 1.5) { A = ${f(S.A)}; B = ${f(S.B)}; w = ${f(S.w)}; k = ${f(S.k)}; }        // stendardi
  else if (tipo < 2.5) { A = ${f(B.A)}; B = ${f(B.B)}; w = ${f(B.w)}; k = ${f(B.k)}; }   // banderuole
  else if (tipo < 3.5) { A = ${f(T.A)}; B = ${f(T.B)}; w = ${f(T.w)}; k = ${f(T.k)}; }   // teli: solo la balza
  else { A = ${f(D.A)}; B = ${f(D.B)}; w = ${f(D.w)}; k = ${f(D.k)}; }                   // tende: la balza
  vec3 h = vec3(n.x, 0.0, n.z), no = dot(h, h) > 1e-4 ? normalize(h) : dir;
  float ph = k * (p.y + dot(p.xz, uVentoDir) * 0.4) - uTempo * w * (0.8 + 0.5 * g) + p.x * 0.7 + p.z * 0.3;
  float a = A * l * (0.35 + 0.65 * g) * uVento;
  nv = normalize(n - su * a * k * cos(ph) * 0.6);
  vec3 s = no * a * sin(ph) + (dir + su * 0.3) * B * l * l * g * uVento;
  if (tipo < 2.5) {   // stendardi e banderuole: il fondo dondola anche di lato, nel piano della tela (non tocca il muro)
    float o = tipo < 1.5 ? ${f(S.o)} : ${f(B.o)};
    s += cross(su, no) * (tipo < 1.5 ? ${f(S.L)} : ${f(B.L)}) * l * l * (0.3 + 0.7 * g) * uVento
       * sin(uTempo * o + p.x * 0.21 + p.z * 0.17 + 1.3 * sin(uTempo * 0.43 + p.x));
  }
  return s;
}
`;
// materiali con il vento nel vertex shader (+ tinta_unita: festoni e pirografia dell'insegna); juta = corde dei festoni;
// ferro = catene e bandelle dell'insegna (in compressione insegna_ferro, identico, viene unito al ferro del borgo:
// si muovono solo i vertici marcati come insegna, il resto del ferro esce subito dalla funzione)
const VENTO_MAT = /^(stendardo|tenda|telo_|juta|insegna|ferro)/;

// ombre delle tele: stesso spostamento nel materiale di profondita' della luce del sole
let profonditaVento = null;
function materialeProfonditaVento() {
  if (!profonditaVento) {
    profonditaVento = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking });
    profonditaVento.onBeforeCompile = (sh) => {
      Object.assign(sh.uniforms, uniformiVento);
      sh.vertexShader = sh.vertexShader
        .replace('#include <common>', '#include <common>\nattribute vec4 ao;\n' + VENTO_GLSL)
        .replace('#include <begin_vertex>', '#include <begin_vertex>\n{ vec3 nv = normal; transformed += vento((modelMatrix * vec4(position, 1.0)).xyz, normal, ao, nv); }');
    };
    profonditaVento.customProgramCacheKey = () => 'profondita_vento';
  }
  return profonditaVento;
}

function conAO(mat) {
  if (mat.userData.conAO) return;
  mat.userData.conAO = true;
  const intonaco = (mat.name || '').startsWith('intonaco');
  const pietra = /^pietra_(muro|blocchi)/.test(mat.name || '');   // muri di pietra delle case: solo lo sporco alla base
  const vento = VENTO_MAT.test(mat.name || '') || mat.name === 'tinta_unita';
  mat.userData.vento = vento;
  const getto = (mat.name || '').startsWith('acqua_getto'), vasca = !getto && (mat.name || '').startsWith('acqua');   // fontana.js
  // tele sottili: visibili e in ombra da entrambi i lati (a una faccia, nella mappa delle ombre three disegna solo il
  // retro e un telo con il dritto verso il sole non faceva ombra; alcune bancarelle sono specchiate)
  if (/^(stendardo|tenda|telo_)/.test(mat.name || '')) { mat.side = THREE.DoubleSide; mat.shadowSide = THREE.DoubleSide; }
  mat.vertexColors = false;          // l'AO non deve tingere il colore di base
  mat.onBeforeCompile = (sh) => {
    if (vento) {
      Object.assign(sh.uniforms, uniformiVento);
      sh.vertexShader = sh.vertexShader
        .replace('#include <common>', '#include <common>\n' + VENTO_GLSL)
        .replace('#include <beginnormal_vertex>', '#include <beginnormal_vertex>\nvec3 spostVento = vento((modelMatrix * vec4(position, 1.0)).xyz, objectNormal, ao, objectNormal);')
        .replace('#include <begin_vertex>', '#include <begin_vertex>\ntransformed += spostVento;');
    }
    if (getto || vasca) {
      Object.assign(sh.uniforms, uniformiAcqua, { uTempo: uniformiVento.uTempo });
      const dich = '\nvarying vec3 vPosMondo;\nvarying vec3 vNormMondo;\nuniform float uTempo;\n' + FONTANA_GLSL;
      sh.vertexShader = sh.vertexShader
        .replace('#include <common>', '#include <common>' + dich)
        .replace('#include <begin_vertex>', '#include <begin_vertex>\n' + (getto ? GETTO_VERTEX : ''))
        .replace('#include <project_vertex>', '#include <project_vertex>\nvPosMondo = (modelMatrix * vec4(transformed, 1.0)).xyz;\nvNormMondo = normalize(mat3(modelMatrix) * objectNormal);');
      sh.fragmentShader = sh.fragmentShader
        .replace('#include <common>', '#include <common>' + dich)
        .replace(getto ? '#include <alphamap_fragment>' : '#include <normal_fragment_maps>',
          (getto ? '#include <alphamap_fragment>\n' + GETTO_FRAGMENT : '#include <normal_fragment_maps>\n' + VASCA_FRAGMENT));
    }
    sh.uniforms.uForzaAO = uniformiAO.forza; sh.uniforms.uAODiretta = uniformiAO.sulDiretta;
    sh.uniforms.uMostraAO = uniformiAO.mostra;   // diagnosi: mostra solo l'occlusione
    sh.uniforms.uLuceMinima = uniformiAO.minima;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nattribute vec4 ao;\nvarying float vAO;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvAO = ao.r;');
    if (intonaco || pietra) {
      sh.vertexShader = sh.vertexShader
        .replace('#include <common>', '#include <common>\nvarying vec3 vPosMondo;')
        .replace('#include <project_vertex>', '#include <project_vertex>\nvPosMondo = (modelMatrix * vec4(transformed, 1.0)).xyz;');
      sh.fragmentShader = sh.fragmentShader
        .replace('#include <common>', '#include <common>\n' + INTONACO_GLSL)
        .replace('#include <map_fragment>', '#include <map_fragment>\ndiffuseColor.rgb = ' + (intonaco
          ? 'intonacoVissuto(diffuseColor.rgb, vPosMondo);' : 'sporcoBase(diffuseColor.rgb, vPosMondo, vec3(0.12, 0.105, 0.08), 0.5);'));
    }
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying float vAO;\nuniform float uForzaAO;\nuniform float uAODiretta;\nuniform float uMostraAO;\nuniform float uLuceMinima;')
      .replace('#include <dithering_fragment>', '#include <dithering_fragment>\nif (uMostraAO > 0.5) gl_FragColor = vec4(vec3(vAO), 1.0);')
      .replace('#include <aomap_fragment>', `#include <aomap_fragment>
        { float a = mix(1.0, max(vAO, 0.4), uForzaAO);
          reflectedLight.indirectDiffuse *= a; reflectedLight.indirectSpecular *= a;
          reflectedLight.directDiffuse *= mix(1.0, a, uAODiretta);
          reflectedLight.indirectDiffuse += diffuseColor.rgb * uLuceMinima; }   // niente nero pieno in ombra`);
  };
  mat.customProgramCacheKey = () => (intonaco ? 'conAO_intonaco' : pietra ? 'conAO_pietra' : vento ? 'conAO_vento'
    : getto ? 'conAO_getto' : vasca ? 'conAO_vasca' : 'conAO');
  // strati di suolo a pochi cm l'uno dall'altro: il selciato vince sulla terra, la terra sul suolo erboso
  const n = mat.name || '';
  if (n.startsWith('selciato')) Object.assign(mat, { polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 });
  else if (n.startsWith('terra_') && !n.startsWith('terra_erbosa')) Object.assign(mat, { polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
  mat.needsUpdate = true;
}

// acqua della fontana: i getti trasparenti e senza scrittura di profondita', la vasca scura e lucida
function acqua(m) {
  const n = m.name || '';
  if (!n.startsWith('acqua')) return;
  if ('transmission' in m) m.transmission = 0;
  if (n.startsWith('acqua_getto')) {
    m.color.set(0xdbeef5); Object.assign(m, { transparent: true, opacity: 0.35, depthWrite: false, roughness: 0.05 });
  } else {
    m.color.set(0x1f3a3c); Object.assign(m, { transparent: true, opacity: 0.9, roughness: 0.04, metalness: 0 });
  }
}

// vetri: scuri, con un riflesso leggero e sfumato. Lisci (rugosita' 0.1 del Principled) riflettevano il cielo
// come uno specchio e a incidenza radente diventavano bianchi
function vetri(m) {
  if (!(m.name || '').startsWith('vetro')) return;
  m.color.setRGB(0.012, 0.016, 0.02); Object.assign(m, { roughness: 0.32, metalness: 0, envMapIntensity: 0.4 });
}

// legni molto scuri (albedo media 0.04-0.06 contro 0.3 della pietra): senza la luce rimbalzata di Cycles in ombra
// diventano neri. Il colore del materiale moltiplica la texture: li porto verso 0.09-0.1, come legno vecchio
const SCHIARISCI = { tavole_web: 2.4, legno_travi_web: 1.9, assi_web: 1.7, vimini_web: 1.4, imposte_blu_web: 1.6,
  imposte_rosse_web: 1.6, imposte_verdi_web: 1.6 };
function schiarisci(m) { const k = SCHIARISCI[m.name]; if (k) m.color.multiplyScalar(k); }

// fondo delle aperture (botteghe, rimesse): tavole scure con un filo di luce propria, leggibili anche in ombra;
// bocca del forno: bagliore del fuoco
function interni(m) {
  if (m.name.startsWith('interno_buio') && m.map) {
    m.emissiveMap = m.map; m.emissive.setRGB(1, 0.9, 0.8); m.emissiveIntensity = 0.45;
  } else if (m.name.startsWith('bocca_forno')) {
    m.color.setRGB(0.02, 0.012, 0.008); m.emissive.setRGB(1.0, 0.36, 0.09); m.emissiveIntensity = 0.05;
  }
}

// filtro anisotropico (main.js lo imposta secondo la qualita'): senza, tetti e strade visti di sbieco si
// sfocavano nel colore medio della texture (la paglia sembrava senza texture)
export const opzioniTexture = { anisotropia: 1 };
const textureCondivise = new Map();
function condividiTexture(mat) {
  for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'emissiveMap']) {
    const t = mat[k];
    if (!t || !t.image) continue;
    const gia = textureCondivise.get(t.image);
    if (gia && gia !== t) { mat[k] = gia; t.dispose(); }
    else { textureCondivise.set(t.image, t); t.anisotropy = opzioniTexture.anisotropia; t.needsUpdate = true; }
  }
}

// geometria in metri per le collisioni (le posizioni meshopt sono quantizzate: si applica matrixWorld)
function geometriaCollisione(radice) {
  const parti = [];
  radice.updateMatrixWorld(true);
  radice.traverse((o) => {
    if (!o.isMesh) return;
    const pos = o.geometry.attributes.position, arr = new Float32Array(pos.count * 3);
    for (let i = 0; i < pos.count; i++) { arr[3 * i] = pos.getX(i); arr[3 * i + 1] = pos.getY(i); arr[3 * i + 2] = pos.getZ(i); }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(arr, 3));
    if (o.geometry.index) g.setIndex(o.geometry.index.clone());
    g.applyMatrix4(o.matrixWorld);
    parti.push(g);
  });
  const geo = mergeGeometries(parti, false);
  geo.boundsTree = new MeshBVH(geo);
  geo.computeBoundingBox();
  return geo;
}

// Nel file ogni zona e' divisa in riquadri di 25 m, cosi' la quantizzazione delle posizioni resta precisa.
// Qui i riquadri si riuniscono (posizioni gia' decodificate in metri, in float) per materiale e per quadrante della
// citta': quando arriva una zona per materiale e quadrante della zona; quando le zone sono tutte caricate
// (finalizza) per materiale e quadrante dell'intera citta'. Pochi oggetti grandi = poche draw call; i quadranti
// permettono alla camera e alle ombre di scartare la parte di citta' che non vedono.
const CENTRO_CITTA = { x: 11, z: 0 };                 // (Blender x = 11, y = 0)
const quadrante = (x, z) => (x < CENTRO_CITTA.x ? 0 : 1) + (z < CENTRO_CITTA.z ? 0 : 2);
// suolo e minuterie non proiettano ombre utili: meno lavoro per la mappa delle ombre
// (stendardi, tende e teli fanno ombra: si muove con loro, vedi materialeProfonditaVento)
const SENZA_OMBRA = ['selciato', 'terra', 'prato', 'vetro', 'interno_buio', 'acqua', 'fiori_', 'mela', 'arancia',
  'limone', 'cavolo', 'pane', 'formaggio', 'zucca', 'uva'];
const fasombra = (mat) => !SENZA_OMBRA.some((p) => (mat.name || '').startsWith(p));

function aFloat(attr, m3, normale) {
  const n = attr.count, k = attr.itemSize, out = new Float32Array(n * k), v = new THREE.Vector3();
  for (let i = 0; i < n; i++) {
    if (m3) {
      v.set(attr.getX(i), attr.getY(i), attr.getZ(i)).applyMatrix3(m3);
      if (normale) v.normalize();
      out[k * i] = v.x; out[k * i + 1] = v.y; out[k * i + 2] = v.z;
    } else for (let j = 0; j < k; j++) out[k * i + j] = attr.getComponent(i, j);
  }
  return new THREE.BufferAttribute(out, k);
}

// unisce geometrie gia' in float e in coordinate del mondo; un attributo che manca in una parte (per esempio le UV
// delle corde nate da curve) viene riempito invece di essere scartato per tutte
function unisci(geos) {
  const forme = new Map();
  for (const g of geos) for (const [a, at] of Object.entries(g.attributes)) if (!forme.has(a)) forme.set(a, at.itemSize);
  for (const g of geos) {
    for (const [a, k] of forme) {
      if (g.attributes[a]) continue;
      const arr = new Float32Array(g.attributes.position.count * k); if (a === 'ao') arr.fill(1);
      g.setAttribute(a, new THREE.BufferAttribute(arr, k));
    }
    if (!g.index) g.setIndex([...Array(g.attributes.position.count).keys()]);
  }
  return mergeGeometries(geos, false);
}

// i materiali a tinta unita (fiori, frutta, foglie, festoni, ferro...) diventano uno solo: il colore passa nei
// vertici. Restano a parte vetro (lucido), brace (emette luce) e acqua (trasparente).
let tintaUnita = null;
function materialeTintaUnita() {
  if (!tintaUnita) {
    tintaUnita = new THREE.MeshStandardMaterial({ name: 'tinta_unita', roughness: 0.7, metalness: 0 });
    conAO(tintaUnita); tintaUnita.vertexColors = true;   // conAO li spegne: qui il colore viene proprio dai vertici
  }
  return tintaUnita;
}
const aTintaUnita = (m) => !m.map && !m.transparent && !m.emissiveMap && m.emissive.getHex() === 0 &&
  !(m.name || '').startsWith('vetro') && m.color;

// Ombre "a tessere": le mesh della citta' sono riunite per materiale e quadrante (poche draw call), ma cosi' ogni cascata
// delle ombre del sole (src/ombre.js) disegnava quasi tutto il borgo anche quando copre 30 m. I materiali fermi e opachi
// fanno ombra con copie della sola geometria riunite per TESSERA_OMBRE m (tutti i materiali insieme, una mesh per
// tessera e lato): ogni cascata disegna solo le tessere che tocca. Il gruppo citta.ombre e' visibile solo mentre si
// disegnano le mappe delle ombre (main.js). Le tele col vento restano mesh normali (si piegano anche nell'ombra).
const TESSERA_OMBRE = 25;
const ombraTessere = (mat) => fasombra(mat) && !mat.transparent && !mat.alphaTest;
// il vento c'e' solo dove l'attributo ao porta un tipo di tela (canale B = tipo / 8, 1-6): il resto della tinta unita
// (frutta, fiori, ferri...) e' fermo e va nelle tessere
function ventosa(g) {
  const ao = g.attributes.ao; if (!ao || ao.itemSize < 4) return false;
  for (let i = 0; i < ao.count; i++) { const t = ao.getZ(i); if (t > 0.06 && t < 0.9) return true; }
  return false;
}
const matOmbra = {};   // lato -> materiale (solo per side/shadowSide: la profondita' la scrive MeshDepthMaterial)
function materialeOmbra(mat) {
  const k = mat.side + '|' + mat.shadowSide;
  return matOmbra[k] || (matOmbra[k] = new THREE.MeshBasicMaterial({ side: mat.side, shadowSide: mat.shadowSide }));
}

function nuovaMesh(geo, mat, nome, tessere = false) {
  const mesh = new THREE.Mesh(geo, mat);
  mesh.castShadow = fasombra(mat) && !tessere; mesh.receiveShadow = true; mesh.name = nome;
  mesh.userData.tessere = tessere;   // l'ombra la fanno le copie in citta.ombre
  if (mat.userData.vento) mesh.customDepthMaterial = materialeProfonditaVento();
  return mesh;
}

function unisciZona(radice, nomeZona, ombre) {
  radice.updateMatrixWorld(true);
  const gruppi = new Map(), mNor = new THREE.Matrix3(), c = new THREE.Vector3();
  radice.traverse((o) => {
    if (!o.isMesh) return;
    const src = o.geometry, g = new THREE.BufferGeometry();
    mNor.getNormalMatrix(o.matrixWorld);
    g.setAttribute('position', aFloat(src.attributes.position)); g.applyMatrix4(o.matrixWorld);   // prima, da sola
    for (const a of Object.keys(src.attributes)) {
      if (a === 'position' || a === 'tangent') continue;
      g.setAttribute(a, a === 'normal' ? aFloat(src.attributes.normal, mNor, true) : aFloat(src.attributes[a]));
    }
    if (src.index) g.setIndex(new THREE.BufferAttribute(Uint32Array.from(src.index.array), 1));
    src.dispose();
    g.computeBoundingBox(); g.boundingBox.getCenter(c);
    const q = o.name.includes('campagna') ? 'c' : quadrante(c.x, c.z);
    let mat = o.material;
    if (aTintaUnita(mat)) {
      const n = g.attributes.position.count, col = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) { col[3 * i] = mat.color.r; col[3 * i + 1] = mat.color.g; col[3 * i + 2] = mat.color.b; }
      g.setAttribute('color', new THREE.BufferAttribute(col, 3));
      mat = materialeTintaUnita();
    }
    const tessere = ombraTessere(mat) && !(mat.userData.vento && ventosa(g));
    const k = mat.uuid + '|' + q + (tessere ? '|t' : '');
    (gruppi.get(k) || gruppi.set(k, { mat, q, tessere, geos: [] }).get(k)).geos.push(g);
    if (tessere) {   // copia per le ombre a tessere (solo posizioni e indici)
      const mo = materialeOmbra(mat);
      const kt = `${Math.floor(c.x / TESSERA_OMBRE)}_${Math.floor(c.z / TESSERA_OMBRE)}|${mo.uuid}`;
      const go = new THREE.BufferGeometry();
      go.setAttribute('position', g.attributes.position);
      go.setIndex(g.index || [...Array(g.attributes.position.count).keys()]);
      (ombre.get(kt) || ombre.set(kt, { mo, geos: [] }).get(kt)).geos.push(go);
    }
  });
  const gruppo = new THREE.Group(); gruppo.name = nomeZona;
  for (const { mat, q, tessere, geos } of gruppi.values()) {
    const m = nuovaMesh(unisci(geos), mat, `${nomeZona}:${q}:${mat.name}`, tessere);
    m.userData.quadrante = q; gruppo.add(m);
    geos.forEach((g) => g.dispose());
  }
  return gruppo;
}

export class Citta {
  constructor(scena, base, texRidotte) {
    this.ombre = new THREE.Group(); this.ombre.name = 'ombre_tessere'; this.ombre.visible = false; scena.add(this.ombre);
    this.scena = scena; this.base = base; this.collisori = []; this.zoneCaricate = 0; this.gruppiZone = [];
    this.materiali = new Map(); this.alberi = new Map(); this.matChioma = {}; this.distanzaAlberi = 0; this.alberiVicini = 0;
    const gestore = new THREE.LoadingManager();
    if (texRidotte) gestore.setURLModifier((u) => u.replace('/tex/', '/tex512/'));
    this.loader = new GLTFLoader(gestore); this.loader.setMeshoptDecoder(MeshoptDecoder);
  }

  async dati() {
    this.info = await (await fetch(this.base + 'citta.json')).json();
    const ins = this.info.insegne?.[0];   // insegna della locanda: perno e asse del pendolo (esporta_borgo.py)
    if (ins) { uniformiVento.uInsPerno.value.fromArray(ins.perno); uniformiVento.uInsAsse.value.fromArray(ins.asse).normalize(); }
    return this.info;
  }

  caricaZona(z, suProgresso) {
    return new Promise((ok, ko) => this.loader.load(this.base + z.file, (gltf) => {
      gltf.scene.traverse((o) => {
        if (!o.isMesh) return;
        const g = o.geometry;
        if (g.attributes.color) { g.setAttribute('ao', g.attributes.color); g.deleteAttribute('color'); }
        else g.setAttribute('ao', new THREE.BufferAttribute(new Float32Array(g.attributes.position.count * 4).fill(1), 4));
        // ogni file crea le sue copie dei materiali: una sola istanza per nome, cosi' le zone si possono riunire
        const unico = this.materiali.get(o.material.name);
        if (unico) { if (unico !== o.material) { o.material.dispose(); o.material = unico; } return; }   // gia' preparato
        this.materiali.set(o.material.name, o.material);
        condividiTexture(o.material); acqua(o.material); vetri(o.material); schiarisci(o.material); interni(o.material); conAO(o.material);
      });
      const tessere = new Map();
      const zona = unisciZona(gltf.scene, z.nome, tessere);
      for (const [k, { mo, geos }] of tessere) {
        const m = new THREE.Mesh(geos.length > 1 ? mergeGeometries(geos, false) : geos[0], mo);
        m.castShadow = true; m.receiveShadow = false; m.name = `ombra:${z.nome}:${k.split('|')[0]}`; m.raycast = () => {};
        m.geometry.computeBoundingSphere(); this.ombre.add(m);
      }
      this.scena.add(zona); this.gruppiZone.push(zona);
      this.collisori.push(geometriaCollisione(zona));
      this.zoneCaricate++;
      ok(zona);
    }, (e) => { if (e.total && suProgresso) suProgresso(e.loaded / e.total); }, ko));
  }

  // a zone tutte caricate: una mesh per materiale e quadrante per l'intera citta'
  finalizza() {
    const gruppi = new Map();
    for (const zona of this.gruppiZone) for (const m of zona.children) {
      const t = m.userData.tessere, k = m.material.uuid + '|' + m.userData.quadrante + (t ? '|t' : '');
      (gruppi.get(k) || gruppi.set(k, { mat: m.material, q: m.userData.quadrante, t, meshes: [] }).get(k)).meshes.push(m);
    }
    const citta = new THREE.Group(); citta.name = 'citta';
    for (const { mat, q, t, meshes } of gruppi.values()) {
      const geo = meshes.length === 1 ? meshes[0].geometry : unisci(meshes.map((m) => m.geometry));
      citta.add(nuovaMesh(geo, mat, `citta:${q}:${mat.name}`, t));
      if (meshes.length > 1) meshes.forEach((m) => m.geometry.dispose());
    }
    for (const zona of this.gruppiZone) this.scena.remove(zona);
    this.gruppiZone = [citta]; this.scena.add(citta);
    return citta.children.length;
  }

  async impostori() {
    const caricatore = new THREE.TextureLoader();
    const perVariante = new Map();
    for (const a of this.info.alberi) (perVariante.get(a.v) || perVariante.set(a.v, []).get(a.v)).push(a);
    const q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
    const su = new THREE.Vector3(0, 1, 0);
    for (const [v, lista] of perVariante) {
      const imp = this.info.impostori[v];
      const tex = await caricatore.loadAsync(this.base + imp.file);
      tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
      // quattro piani incrociati (ogni 45 gradi) attorno al tronco, base a terra; normali "a sfera" dal centro
      // della chioma, piegate verso l'alto: un lato in luce e uno in ombra, la chioma ha volume anche da vicino
      // (i piani girano attorno alla pianta, che sta a cx dall'origine dell'istanza: alcuni cespugli sono spostati)
      const piano = new THREE.PlaneGeometry(imp.lato, imp.lato, 4, 4).translate(0, imp.base + imp.lato / 2, 0);
      const geo = mergeGeometries([0, 1, 2, 3].map((k) => piano.clone().rotateY(k * Math.PI / 4))).translate(imp.cx, 0, 0);
      const centro = new THREE.Vector3(imp.cx, imp.base + imp.lato * 0.55, 0), d = new THREE.Vector3();
      const pos = geo.attributes.position, n = geo.attributes.normal;
      for (let i = 0; i < n.count; i++) {
        d.fromBufferAttribute(pos, i).sub(centro).normalize().multiplyScalar(0.8).add(su).normalize();
        n.setXYZ(i, d.x, d.y, d.z);
      }
      // chioma gia' infittita e ravvivata dall'esportatore; al sole pieno (normali verso l'alto) diventava color
      // crema: albedo piu' bassa e normali piu' a sfera, cosi' resta verde con un lato in luce e uno in ombra
      const mat = new THREE.MeshStandardMaterial({ map: tex, color: 0xbdbdbd, alphaTest: 0.45, side: THREE.DoubleSide, roughness: 0.95 });
      mat.onBeforeCompile = (sh) => { ventoChioma(sh, imp.base, imp.lato); fogliaPiatta(sh); };
      const mesh = new THREE.InstancedMesh(geo, mat, lista.length);
      mesh.customDepthMaterial = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking, map: tex, alphaTest: 0.45 });
      mesh.customDepthMaterial.onBeforeCompile = (sh) => ventoChioma(sh, imp.base, imp.lato);
      const matrici = lista.map((a) => {
        q.setFromAxisAngle(su, a.r); s.set(a.s[0], a.s[1], a.s[0]); p.fromArray(a.p);
        return new THREE.Matrix4().compose(p, q, s);
      });
      matrici.forEach((mm, i) => mesh.setMatrixAt(i, mm));
      mesh.castShadow = true; mesh.receiveShadow = false;
      mesh.name = `impostori:${v}`;
      this.scena.add(mesh);
      this.alberi.set(v, { lista, matrici, imp: mesh, veri: [], vicino: new Uint8Array(lista.length) });
    }
  }

  // alberi veri (esporta_alberi.py + npm run alberi) entro `distanza` metri dal giocatore: tronco e rami in 3D, chioma
  // di ciuffi con l'occlusione nei colori dei vertici; i cespugli con la mesh vera. Oltre restano gli impostori.
  // Da chiamare dopo impostori(); aggiornaAlberi() sposta poi ogni istanza fra le due versioni
  async alberiVeri(distanza) {
    if (!(distanza > 0)) return;
    const info = await (await fetch(this.base + 'alberi/alberi.json')).json();
    const caricatore = new THREE.TextureLoader(this.loader.manager);   // stesso gestore: tex512 nel preset basso
    const texture = new Map();
    const tex = (nome) => {
      if (!texture.has(nome)) texture.set(nome, caricatore.loadAsync(this.base + 'alberi/tex/' + nome).then((t) => {
        t.colorSpace = THREE.SRGBColorSpace; t.flipY = false; t.anisotropy = opzioniTexture.anisotropia; return t;
      }));
      return texture.get(nome);
    };
    for (const [v, d] of Object.entries(info.varianti)) {
      const alb = this.alberi.get(v);
      if (!alb) continue;
      const gltf = await this.loader.loadAsync(this.base + d.file);
      const meshes = [];
      gltf.scene.updateMatrixWorld(true);
      gltf.scene.traverse((o) => { if (o.isMesh) meshes.push(o); });
      for (const pt of d.parti) {
        const nome = THREE.PropertyBinding.sanitizeNodeName(pt.mesh);
        const o = meshes.find((mm) => mm.name === nome) || meshes.find((mm) => mm.name.startsWith(nome));
        if (!o) { console.warn('alberi: manca la parte', pt.mesh); continue; }
        // meshopt: posizioni quantizzate con la scala nel nodo -> attributi in float e trasformazione applicata
        const geo = inFloat(o.geometry).applyMatrix4(o.matrixWorld);
        const map = await tex(pt.tex);
        const foglie = pt.tipo === 'foglie';
        let mat;
        if (foglie) {
          // carte dei ciuffi: come gli impostori (stessa normale sui due lati, niente speculare), piu' l'occlusione
          const sp = v.replace(/_\d+$/, ''), C = CHIOMA[sp] || CHIOMA.island_tree_02;
          chiomaComeImpostore(geo, C, this.info.impostori[v]);
          mat = new THREE.MeshStandardMaterial({ map, color: new THREE.Color().setRGB(...C.tinta, THREE.LinearSRGBColorSpace),
            vertexColors: true, alphaTest: 0.45, side: THREE.DoubleSide, roughness: 0.95 });
          mat.onBeforeCompile = (sh) => { ventoChioma(sh, d.base, d.altezza); fogliaPiatta(sh); };
          this.matChioma[sp] = mat;
        } else {
          // corteccia: la stessa tinta del generatore (TINTA_CORTECCIA, letta dal materiale da esporta_alberi.py: l'olivo
          // e' grigio-bruno come negli impostori, che sono renderizzati dalla scena)
          const colore = pt.tipo === 'cespuglio' ? new THREE.Color(TINTA_CESPUGLI)
            : new THREE.Color().setRGB(...(pt.tinta || [1, 1, 1]), THREE.LinearSRGBColorSpace);
          mat = new THREE.MeshStandardMaterial({ map, color: colore,
            roughness: 0.92, side: pt.tipo === 'cespuglio' ? THREE.DoubleSide : THREE.FrontSide });
          mat.onBeforeCompile = (sh) => ventoChioma(sh, d.base, d.altezza);
        }
        const im = new THREE.InstancedMesh(geo, mat, alb.lista.length);
        im.count = 0;
        im.customDepthMaterial = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking,
          ...(foglie ? { map, alphaTest: 0.45 } : {}) });
        im.customDepthMaterial.onBeforeCompile = (sh) => ventoChioma(sh, d.base, d.altezza);
        im.castShadow = true; im.receiveShadow = !foglie;
        im.name = `alberi:${v}:${pt.tipo}`;
        this.scena.add(im); alb.veri.push(im);
      }
      gltf.scene.traverse((o) => { if (o.isMesh) o.geometry.dispose(); });
    }
    this.distanzaAlberi = distanza;
    this.tAlberi = 1;   // primo aggiornamento subito
  }

  // ogni 0,1 s: entro la distanza l'albero vero, oltre l'impostore (3 m di isteresi: niente sfarfallio sul confine)
  aggiornaAlberi(pos, dt) {
    if (!this.distanzaAlberi) return;
    this.tAlberi += dt;
    if (this.tAlberi < 0.1) return;
    this.tAlberi = 0;
    const D = this.distanzaAlberi, D2 = D * D, Dfuori2 = (D + 3) * (D + 3);
    let vicini = 0;
    for (const alb of this.alberi.values()) {
      if (!alb.veri.length) continue;
      let cambiato = false;
      for (let i = 0; i < alb.lista.length; i++) {
        const a = alb.lista[i].p, dx = a[0] - pos.x, dz = a[2] - pos.z, d2 = dx * dx + dz * dz;
        const ora = alb.vicino[i] ? d2 < Dfuori2 : d2 < D2;
        if (ora !== (alb.vicino[i] === 1)) { alb.vicino[i] = ora ? 1 : 0; cambiato = true; }
      }
      let nv = 0, nl = 0;
      if (cambiato) {
        for (let i = 0; i < alb.lista.length; i++) {
          if (alb.vicino[i]) { for (const mm of alb.veri) mm.setMatrixAt(nv, alb.matrici[i]); nv++; }
          else alb.imp.setMatrixAt(nl++, alb.matrici[i]);
        }
        alb.imp.count = nl;
        for (const mm of alb.veri) mm.count = nv;
        for (const mm of [alb.imp, ...alb.veri]) { mm.instanceMatrix.needsUpdate = true; mm.computeBoundingSphere(); }
      }
      vicini += alb.veri[0].count;
    }
    this.alberiVicini = vicini;
  }
}

// chiome vere, tarate sugli impostori che le sostituiscono oltre la distanza del preset: l'albero non deve cambiare
// colore avvicinandosi. L'impostore e' un render con il sole (luce gia' nell'immagine), l'atlante dei ciuffi e' il solo
// colore delle foglie: la tinta (lineare, moltiplica la texture) e' misurata, stessa vista con l'uno e con l'altro,
// colore medio dei pixel della chioma uguale (anteprime/alberi/taratura_*). su: quanto le normali "a sfera" si piegano
// verso l'alto (1 = come gli impostori; meno = lato in ombra piu' scuro, piu' volume). ao: occlusione dei vertici
// riportata in [ao, 1]
const CHIOMA = {
  // misurate il 2026-11-03 (strumenti/scatta_chiome.js + misura_chiome.mjs, 4 viste al sole e in controluce): colore
  // medio entro il 5% per canale, luminanza del lato in luce e in ombra uguale -> su resta 1 come negli impostori
  island_tree_02: { tinta: [0.563, 0.736, 1.375], su: 1.0, ao: 0.55 },
  jacaranda_tree: { tinta: [0.53, 0.762, 0.81], su: 1.0, ao: 0.55 },
};
const TINTA_CESPUGLI = 0xd8d8d8;

// foglie al vento, appena percettibili: la chioma ondeggia di pochi centimetri (nulla alla base, al massimo in cima)
// nel verso del vento, con un tremolio fine; fase diversa per ogni albero. Uguale nell'ombra, negli impostori e negli
// alberi veri (stessa formula: il passaggio dall'uno all'altro non si vede). base e lato in unita' del modello
function ventoChioma(sh, base, lato) {
  Object.assign(sh.uniforms, uniformiVento);
  sh.uniforms.uBase = { value: base }; sh.uniforms.uLato = { value: lato };
  sh.vertexShader = sh.vertexShader
    .replace('#include <common>', '#include <common>\nuniform float uBase; uniform float uLato;\n' + VENTO_GLSL)
    .replace('#include <begin_vertex>', `#include <begin_vertex>
      if (uFoglie > 0.0) {
        vec3 b = (modelMatrix * instanceMatrix[3]).xyz;
        float h = clamp((position.y - uBase) / uLato, 0.0, 1.0), w = h * h * uVento * uFoglie;
        vec3 dl = normalize(transpose(mat3(instanceMatrix)) * vec3(uVentoDir.x, 0.0, uVentoDir.y));
        transformed += dl * w * ${f(VENTO.foglie.chioma)} * (0.45 * raffica(b) + 0.55 * sin(uTempo * 1.6 + b.x * 0.37 + b.z * 0.23));
        transformed.xz += w * ${f(VENTO.foglie.tremolio)} * vec2(sin(uTempo * 3.3 + position.x * 2.9 + position.y * 2.1 + b.z),
                                           cos(uTempo * 2.9 + position.y * 2.6 + b.x));
      }`);
}

// stessa normale davanti e dietro: con DoubleSide three la capovolge sul retro e mezza chioma finiva in ombra.
// Niente riflesso speculare: su un piano al sole o in controluce copriva le foglie con un velo color crema
function fogliaPiatta(sh) {
  sh.fragmentShader = sh.fragmentShader.replace('#include <normal_fragment_begin>',
    THREE.ShaderChunk.normal_fragment_begin.replace('normal *= faceDirection;', ''))
    .replace('#include <aomap_fragment>', '#include <aomap_fragment>\nreflectedLight.directSpecular = vec3(0.0); reflectedLight.indirectSpecular = vec3(0.0);');
}

// normali come negli impostori: "a sfera" dallo stesso centro (cx, base + 0.55 lato), piegate verso l'alto, cosi' luce
// e ombra cadono sulla chioma vera come sull'impostore; occlusione dei vertici addolcita
function chiomaComeImpostore(geo, C, imp) {
  const c = new THREE.Vector3(imp.cx, imp.base + imp.lato * 0.55, 0);
  const pos = geo.attributes.position, n = geo.attributes.normal, d = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    d.fromBufferAttribute(pos, i).sub(c).normalize().multiplyScalar(0.8);
    d.y += C.su; d.normalize();
    n.setXYZ(i, d.x, d.y, d.z);
  }
  const col = geo.attributes.color;
  if (col) for (let i = 0; i < col.count; i++) {
    const a = C.ao + (1 - C.ao) * col.getX(i);
    col.setXYZ(i, a, a, a);
  }
}

// attributi quantizzati (meshopt: interi normalizzati, a volte interleaved) -> Float32, per poter applicare la matrice
function inFloat(g) {
  const geo = new THREE.BufferGeometry();
  for (const [k, a] of Object.entries(g.attributes)) {
    const n = a.count, s = a.itemSize, arr = new Float32Array(n * s), get = [a.getX, a.getY, a.getZ, a.getW];
    for (let i = 0; i < n; i++) for (let j = 0; j < s; j++) arr[i * s + j] = get[j].call(a, i);
    geo.setAttribute(k, new THREE.BufferAttribute(arr, s));
  }
  if (g.index) geo.setIndex(Array.from(g.index.array));
  return geo;
}
