// Il borgo nel browser (Fase 2, passo 2): citta' intera caricata a zone, prima persona.
// Coordinate: il glTF di Blender ha Y in alto, quindi (x, y, z) Blender -> (x, z, -y) qui.
import * as THREE from 'three';
import { HDRLoader } from 'three/examples/jsm/loaders/HDRLoader.js';
import { SunLight } from 'three/examples/jsm/lights/SunLight.js';
import { OmbraSole } from './ombre.js';
import { Citta, uniformiAO, opzioniTexture, uniformiVento, VENTO } from './citta.js';
import { uniformiAcqua, creaSchizzi } from './fontana.js';
import { Giocatore } from './giocatore.js';
import { creaComposer } from './post.js';
import { Segnalazioni } from './segnalazioni.js';

// ============================== PARAMETRI ==============================
const BASE = import.meta.env.BASE_URL;                 // './' su GitHub Pages / Netlify
const CIELO = BASE + 'cielo/qwantani_mid_morning_puresky_1k.hdr';
const SOLE_AZIMUT = -15, SOLE_ALTEZZA = 40;          // come in genera_quartiere.py (0 = est, 90 = nord)
const ALTEZZA_OCCHI = 1.7;
const PARTENZA = [127, 15.6];                         // sul ponte fuori dalla Porta Est (Blender x, y)
// tarata sul render Cycles via_maestra.png; rimbalzo = luce calda riflessa dai muri al sole
const LUCE = { sole: 4.0, cielo: 0.45, rimbalzo: 0.8, esposizione: 1.0 };
const PRESET = {                                      // ?q=basso | medio | alto
  // alberi = distanza (m) entro cui gli alberi sono modelli veri (oltre: impostori); ?alberi=0 solo impostori
  // ombra = lato in pixel di OGNUNA delle due cascate del sole (vedi OMBRE)
  basso: { pixel: 1.0, ombra: 1024, msaa: 0, n8ao: false, tex512: true, alberi: 15 },
  medio: { pixel: 1.25, ombra: 2048, msaa: 4, n8ao: false, tex512: false, alberi: 30 },
  alto:  { pixel: 2.0, ombra: 3072, msaa: 4, n8ao: true, tex512: false, alberi: 45 },
};
// ombre del sole (src/ombre.js): cascata vicina fino a 'vicino' m di profondita' di vista, cascata lontana = quadrato
// di 'lontano' m spostato 'avanti' m verso lo sguardo; raggio = morbidezza del bordo in texel (filtro PCF);
// bias in profondita' e lungo la normale contro le striature sulle superfici in luce (tele comprese)
const OMBRE = { vicino: 10, lontano: 100, avanti: 20, raggio: 2.5, bias: -0.0002, normalBias: 0.02 };
// vento: tutti i parametri (direzione, VENTO.forza che scala tutte le ampiezze, riduzioni) stanno in citta.js
// =======================================================================

const parametri = new URLSearchParams(location.search);
const BENCH = parametri.has('bench');
const TOUCH = matchMedia('(pointer: coarse)').matches;
const Q = PRESET[parametri.get('q')] ? parametri.get('q') : (TOUCH ? 'basso' : 'medio');
const qualita = PRESET[Q];
const daBlender = (x, y, z = 0) => new THREE.Vector3(x, z, -y);

// --- renderer, scena, camera, luce --------------------------------------
const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, qualita.pixel));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.AgXToneMapping; renderer.toneMappingExposure = LUCE.esposizione;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.info.autoReset = false;   // con la post-produzione: statistiche dell'intero fotogramma
document.body.appendChild(renderer.domElement);

const scena = new THREE.Scene();
scena.fog = new THREE.FogExp2(0xcbd5df, 0.0018);
const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, 0.1, 2500);
const az = THREE.MathUtils.degToRad(SOLE_AZIMUT), al = THREE.MathUtils.degToRad(SOLE_ALTEZZA);
const dirSole = daBlender(Math.cos(al) * Math.cos(az), Math.cos(al) * Math.sin(az), Math.sin(al)).normalize();
// SunLight: luce direzionale (dalla sua posizione verso l'origine) con ombre a cascate, vedi OmbraSole
const sole = new SunLight(0xffecd2, LUCE.sole);
sole.position.copy(dirSole).multiplyScalar(100);
sole.castShadow = true; sole.shadow.dispose(); sole.shadow = new OmbraSole(OMBRE);
sole.shadow.mapSize.set(qualita.ombra, qualita.ombra);
Object.assign(sole.shadow, { radius: OMBRE.raggio, bias: OMBRE.bias, normalBias: OMBRE.normalBias });
scena.add(sole);
const rimbalzo = new THREE.HemisphereLight(0xdfe6ee, 0xb08a62, LUCE.rimbalzo);   // cielo chiaro, terra calda
scena.add(rimbalzo);
const { composer, gradazione } = creaComposer(renderer, scena, camera, qualita);
// piano color prato sotto il terreno: chiude le fessure fra fossato e campagna (vertici aggiunti per l'AO)
const fondo = new THREE.Mesh(new THREE.PlaneGeometry(5000, 5000).rotateX(-Math.PI / 2),
  new THREE.MeshStandardMaterial({ color: 0x4d5a2b, roughness: 1 }));
fondo.position.y = -1.6; fondo.receiveShadow = true; scena.add(fondo);   // sotto il fondo del fossato (-1,4 m)

// --- vento ---------------------------------------------------------------
const azVento = THREE.MathUtils.degToRad(VENTO.azimut);
uniformiVento.uVentoDir.value.set(Math.cos(azVento), -Math.sin(azVento));   // Blender (x, y) -> three (x, -z)
const riduciMovimento = matchMedia('(prefers-reduced-motion: reduce)');
let fpsBassi = false, fpsForzati = null, finestreLente = 0, finestreSvelte = 0, controllaDa = Infinity;   // durante il caricamento gli fps non contano
let schizzi = null;   // particelle della fontana (preset medio e alto)
function aggiornaVento(dt) {
  let forza = VENTO.forza, foglie = 1, acqua = 1;
  if (riduciMovimento.matches) { forza *= VENTO.ridotto; foglie = 0; acqua = VENTO.ridotto; }
  else if (fpsBassi) {
    acqua = VENTO.bassoLento;                                          // fontana: in ogni preset
    if (Q === 'basso') { forza *= VENTO.bassoLento; foglie = 0; }      // vento: solo nel preset basso
  }
  const u = uniformiVento, k = Math.min(1, dt * 0.8);                  // passaggio graduale, niente scatti
  u.uVento.value += (forza - u.uVento.value) * k;
  u.uFoglie.value += (foglie - u.uFoglie.value) * k;
  if (u.uFoglie.value < 0.01 && foglie === 0) u.uFoglie.value = 0;      // 0 = calcolo delle foglie saltato
  uniformiAcqua.uAcqua.value += (acqua - uniformiAcqua.uAcqua.value) * k;
  if (schizzi) schizzi.material.uniforms.uScala.value = renderer.domElement.height / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)));
}
// fps bassi: sotto VENTO.fpsLento per 2 s si riducono il vento (preset basso) e la fontana; tornano dopo 5 s sopra fpsRipresa
function controllaFps(fps) {
  if (fpsForzati !== null) { fpsBassi = fpsForzati; return; }   // test: stato imposto con __vento({ lento })
  if (performance.now() < controllaDa) return;
  if (fps < VENTO.fpsLento) { finestreLente++; finestreSvelte = 0; } else if (fps > VENTO.fpsRipresa) { finestreSvelte++; finestreLente = 0; }
  if (!fpsBassi && finestreLente >= 4) fpsBassi = true;
  if (fpsBassi && finestreSvelte >= 10) fpsBassi = false;
}

// --- interfaccia --------------------------------------------------------
const $ = (id) => document.getElementById(id);
const riempimento = $('riempimento'), stato = $('stato'), ingresso = $('ingresso'), mirino = $('mirino');
const zoneTesto = $('zone'), hud = $('hud');
if (TOUCH) $('istruzioni').textContent = 'Levetta a sinistra per camminare, trascina a destra per guardare. Segnala salva posizione e screenshot.';

// --- cielo HDRI: allineato al sole, disco del sole tolto dalla luce ambiente ---
function caricaCielo() {
  return new Promise((ok, ko) => new HDRLoader().load(CIELO, (tex) => {
    const { data, width, height } = tex.image;
    const leggi = data instanceof Uint16Array ? THREE.DataUtils.fromHalfFloat : (v) => v;
    const scrivi = data instanceof Uint16Array ? THREE.DataUtils.toHalfFloat : (v) => v;
    let max = -1, imax = 0;
    for (let i = 0; i < width * height; i++) {
      const l = leggi(data[4 * i]) * 0.2126 + leggi(data[4 * i + 1]) * 0.7152 + leggi(data[4 * i + 2]) * 0.0722;
      if (l > max) { max = l; imax = i; }
    }
    for (let i = 0; i < data.length; i++) if ((i & 3) !== 3 && leggi(data[i]) > 24) data[i] = scrivi(24);
    tex.needsUpdate = true; tex.mapping = THREE.EquirectangularReflectionMapping;
    const rot = Math.atan2(dirSole.z, dirSole.x) - (((imax % width) + 0.5) / width - 0.5) * 2 * Math.PI;
    scena.background = tex; scena.environment = tex;
    scena.backgroundRotation.set(0, rot, 0); scena.environmentRotation.set(0, rot, 0);
    scena.environmentIntensity = LUCE.cielo;
    ok();
  }, undefined, ko));
}

// --- avvio: centro subito, il resto in background ----------------------
opzioniTexture.anisotropia = Math.min(renderer.capabilities.getMaxAnisotropy(), qualita.tex512 ? 4 : 8);
const citta = new Citta(scena, BASE + 'citta/', qualita.tex512);
// le copie per le ombre a tessere (citta.ombre) esistono solo per le mappe delle ombre, non per la vista
const disegnaOmbre = renderer.shadowMap.render.bind(renderer.shadowMap);
renderer.shadowMap.render = (...a) => { citta.ombre.visible = true; disegnaOmbre(...a); citta.ombre.visible = false; };
const giocatore = new Giocatore(camera, renderer.domElement, ALTEZZA_OCCHI, daBlender(...PARTENZA, ALTEZZA_OCCHI));
giocatore.collisori = citta.collisori;
camera.position.copy(giocatore.pos); camera.rotation.set(0, Math.PI / 2, 0, 'YXZ');   // verso la porta
let attivo = false;

// porta il giocatore in un punto (coordinate Blender) con lo sguardo dato (yaw, pitch in gradi)
function vaiA(pos, sguardo = [0, 0]) {
  giocatore.pos.copy(daBlender(pos[0], pos[1], pos[2] ?? ALTEZZA_OCCHI)); giocatore.vel.set(0, 0, 0);
  camera.position.copy(giocatore.pos);
  camera.rotation.set(THREE.MathUtils.degToRad(sguardo[1]), THREE.MathUtils.degToRad(sguardo[0]), 0, 'YXZ');
}
// ?pos=x,y,z,yaw,pitch : si parte dal punto di una segnalazione
if (parametri.get('pos')) {
  const v = parametri.get('pos').split(',').map(Number);
  if (v.length >= 2 && v.every(Number.isFinite)) vaiA([v[0], v[1], v[2] ?? ALTEZZA_OCCHI], [v[3] ?? 0, v[4] ?? 0]);
}
const segnalazioni = new Segnalazioni({ renderer, camera, vaiA, qualita: Q,
  sbloccaPuntatore: () => giocatore.controlli.isLocked && giocatore.controlli.unlock() });

function entra() {
  if (TOUCH) { attivo = true; ingresso.style.display = 'none'; }
  else giocatore.controlli.lock();
}
ingresso.addEventListener('click', entra);
giocatore.controlli.addEventListener('lock', () => { attivo = true; ingresso.style.display = 'none'; mirino.style.display = 'block'; });
giocatore.controlli.addEventListener('unlock', () => { attivo = false; if (!BENCH) ingresso.style.display = 'flex'; mirino.style.display = 'none'; });
if (TOUCH) giocatore.attivaTouch($('levetta'), $('pomello'));
addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight);
});

async function avvia() {
  const info = await citta.dati();
  const centro = info.zone[0], altre = info.zone.slice(1);
  let pc = 0, pz = 0;
  const barra = () => { riempimento.style.width = `${Math.round((pz * 0.88 + pc * 0.12) * 100)}%`; };
  await Promise.all([caricaCielo().then(() => { pc = 1; barra(); }), citta.caricaZona(centro, (f) => { pz = f; barra(); })]);
  if (Q !== 'basso') { schizzi = creaSchizzi(uniformiVento); scena.add(schizzi); }   // fontana: niente schizzi nel preset basso
  $('caricamento').style.display = 'none';
  if (!BENCH) ingresso.style.display = 'flex';
  window.__pronto = { gpu: GPU, qualita: Q };
  ciclo();
  // resto del borgo in background, una zona alla volta
  zoneTesto.style.display = 'block';
  zoneTesto.textContent = 'Il resto del borgo: alberi';
  await citta.impostori();
  await citta.alberiVeri(parametri.has('alberi') ? Number(parametri.get('alberi')) : qualita.alberi);
  for (const [i, z] of altre.entries()) {
    zoneTesto.textContent = `Il resto del borgo: ${i}/${altre.length}`;
    await citta.caricaZona(z);
  }
  zoneTesto.textContent = 'Il resto del borgo: rifinitura';
  await new Promise((r) => setTimeout(r, 50));
  const oggetti = citta.finalizza();
  zoneTesto.style.display = 'none';
  window.__tutto = { zone: citta.zoneCaricate, oggetti };
  window.__alberi = () => ({ vicini: citta.alberiVicini, distanza: citta.distanzaAlberi });
  // ?trappole: controllo automatico dei punti da cui il giocatore non esce (src/trappole.js), risultato in __trappole
  if (parametri.has('trappole')) {
    const { cercaTrappole } = await import('./trappole.js');
    window.__trappole = await cercaTrappole(citta.collisori, giocatore.partenza, (t) => { zoneTesto.style.display = 'block'; zoneTesto.textContent = 'Trappole: ' + t; });
    zoneTesto.style.display = 'none';
  }
  controllaDa = performance.now() + 3000;
}

// --- ciclo, HUD ---------------------------------------------------------
const gl = renderer.getContext(), dbg = gl.getExtension('WEBGL_debug_renderer_info');
const GPU = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : 'sconosciuta';
const orologio = new THREE.Timer();
let fotogrammi = 0, tHud = performance.now(), percorso = null, tBench = 0, tempiBench = [];
function ciclo(t) {
  orologio.update(t);
  const dt = Math.max(0, Math.min(orologio.getDelta(), 0.05));   // il primo fotogramma puo' dare un intervallo negativo
  if (percorso) {
    tBench += dt; const u = Math.min(tBench / 30, 1);
    const p = percorso.getPointAt(u), q = percorso.getPointAt(Math.min(u + 0.01, 1));
    camera.position.copy(p); camera.lookAt(q.x, p.y, q.z);
    if (u >= 1) finisciBench();
  } else if (attivo || (BENCH && !fermo)) giocatore.aggiorna(dt);
  citta.aggiornaAlberi(camera.position, dt);
  if (registra) uniformiVento.uTempo.value += registra.passo;   // test: tempo a passo fisso fra i fotogrammi salvati
  else if (!ventoFermo) uniformiVento.uTempo.value += dt;
  aggiornaVento(registra ? registra.passo : dt);
  renderer.info.reset();
  const q = misuraGPU ? iniziaMisuraGPU() : null;
  composer.render(dt);
  if (q) finisciMisuraGPU(q);
  if (registra) {
    registra.fotogrammi.push(renderer.domElement.toDataURL('image/jpeg', registra.qualita));
    if (registra.fotogrammi.length >= registra.n) { registra.ok(registra.fotogrammi); registra = null; }
  }
  segnalazioni.dopoRender();
  const ora = performance.now();
  if (percorso) tempiBench.push(ora);
  fotogrammi++;
  if (ora - tHud > 500) {
    const r = renderer.info.render;
    controllaFps(fotogrammi * 1000 / (ora - tHud));
    hud.textContent = `${(fotogrammi * 1000 / (ora - tHud)).toFixed(0)} fps | ${(r.triangles / 1e3).toFixed(0)}k tri | ${r.calls} draw call | ${Q}`;
    fotogrammi = 0; tHud = ora;
  }
  requestAnimationFrame(ciclo);
}
let fermo = false;   // nei test: camera ferma su un'inquadratura data
// test: tempo GPU del fotogramma intero (EXT_disjoint_timer_query_webgl2), mediana su n fotogrammi
const extTempo = gl.getExtension('EXT_disjoint_timer_query_webgl2');
let misuraGPU = null;
function iniziaMisuraGPU() {
  if (!extTempo) return null;
  const q = gl.createQuery(); gl.beginQuery(extTempo.TIME_ELAPSED_EXT, q); return q;
}
function finisciMisuraGPU(q) {
  gl.endQuery(extTempo.TIME_ELAPSED_EXT); const m = misuraGPU; m.attese.push(q);
  const disgiunto = gl.getParameter(extTempo.GPU_DISJOINT_EXT);
  m.attese = m.attese.filter((x) => {
    if (!gl.getQueryParameter(x, gl.QUERY_RESULT_AVAILABLE)) return true;
    if (!disgiunto) m.tempi.push(gl.getQueryParameter(x, gl.QUERY_RESULT) / 1e6);
    gl.deleteQuery(x); return false;
  });
  if (m.tempi.length >= m.n) {
    const t = [...m.tempi].sort((a, b) => a - b);
    misuraGPU = null; m.ok({ mediana: t[t.length >> 1], p90: t[Math.floor(t.length * 0.9)], n: t.length });
  }
}
window.__tempoGPU = (n = 120) => new Promise((ok) => {
  if (!extTempo) { ok(null); return; }
  misuraGPU = { n, attese: [], tempi: [], ok };
});
let registra = null, ventoFermo = false;   // nei test: fotogrammi a passo fisso; vento fermo (misure prima/dopo)

function finisciBench() {
  const dts = []; for (let i = 1; i < tempiBench.length; i++) dts.push(tempiBench[i] - tempiBench[i - 1]);
  dts.sort((a, b) => a - b);
  const medio = dts.reduce((a, b) => a + b, 0) / dts.length;
  window.__risultati = { fpsMedi: 1000 / medio, fps1pcBassi: 1000 / dts[Math.floor(dts.length * 0.99)], gpu: GPU, qualita: Q,
    triangoli: renderer.info.render.triangles, drawCall: renderer.info.render.calls, pixelRatio: renderer.getPixelRatio() };
  percorso = null;
}

// funzioni per i test automatici (Playwright)
window.__vista = (bx, by, bz, yaw, pitch = 0, fissa = false, fov = 70) => {   // fissa: camera ferma a mezz'aria
  fermo = fissa; camera.fov = fov; camera.updateProjectionMatrix();
  giocatore.pos.copy(daBlender(bx, by, bz)); giocatore.vel.set(0, 0, 0); camera.position.copy(giocatore.pos);
  camera.rotation.set(THREE.MathUtils.degToRad(pitch), THREE.MathUtils.degToRad(yaw), 0, 'YXZ');
};
window.__camera = (nome) => {                          // stessa inquadratura di una camera di Blender
  const c = citta.info.camere[nome];
  percorso = null; fermo = true;
  camera.fov = c.fov; camera.updateProjectionMatrix();
  camera.position.fromArray(c.p); camera.lookAt(new THREE.Vector3().fromArray(c.m));
};
window.__bench = () => {
  fermo = false; tempiBench = []; tBench = 0; camera.fov = 70; camera.updateProjectionMatrix();
  percorso = new THREE.CatmullRomCurve3([[127, 15.6], [104, 14.4], [80, 9.9], [55, 5.2], [32, 0.6], [16, 0.2], [7, -8],
    [-8, -7], [-11, 6], [-10, 22], [-10, 35], [5, 38], [12, -20], [10, -45], [11, -62]]
    .map(([x, y]) => daBlender(x, y, ALTEZZA_OCCHI)));
};
window.__materiali = () => {                          // diagnosi: materiali degli oggetti della citta'
  const r = {};
  scena.traverse((o) => { if (o.isMesh && o.material && !o.isInstancedMesh) {
    const k = o.material.name; r[k] = r[k] || { mesh: 0, tri: 0, mappa: !!o.material.map, trasparente: o.material.transparent };
    r[k].mesh++; r[k].tri += (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3; } });
  return r;
};
window.__sonda = (x, y) => {                           // diagnosi: cosa c'e' sotto un punto dello schermo (-1..1)
  const r = new THREE.Raycaster(); r.setFromCamera(new THREE.Vector2(x, y), camera);
  const h = r.intersectObjects(scena.children, true).find((i) => i.object.isMesh && !i.object.isInstancedMesh);
  if (!h) return null;
  const g = h.object.geometry, f = h.face, ao = g.attributes.ao, col = g.attributes.color, m = h.object.material;
  return { mesh: h.object.name, mat: m.name, dist: h.distance, colore: m.color.getHexString(), mappa: m.map ? (m.map.image?.currentSrc || m.map.image?.src || '?').split('/').pop() : null,
    ao: ao ? [f.a, f.b, f.c].map((i) => ao.getX(i).toFixed(2)) : null,
    tinta: col ? [col.getX(f.a), col.getY(f.a), col.getZ(f.a)].map((v) => v.toFixed(2)) : null,
    normale: f.normal.toArray().map((v) => v.toFixed(2)), lato: h.face.normal.dot(r.ray.direction) > 0 ? 'retro' : 'fronte' };
};
if (BENCH) window.__scena = scena;   // test: accesso diretto alla scena
// test: n fotogrammi JPEG (data URL) a passo fisso di 'passo' secondi del vento
window.__registra = (n, passo = 1 / 15, qualita = 0.88) => new Promise((ok) => { registra = { n, passo, qualita, fotogrammi: [], ok }; });
// test: forza del vento (0 = fermo), tempo fermo, stato delle riduzioni
window.__vento = (o = {}) => {
  if (o.forza !== undefined) { VENTO.forza = o.forza; uniformiVento.uVento.value = o.forza; }
  if (o.fermo !== undefined) ventoFermo = o.fermo;
  if (o.lento !== undefined) { fpsForzati = o.lento; if (o.lento !== null) fpsBassi = o.lento; }   // null = di nuovo automatico
  return { forza: uniformiVento.uVento.value, foglie: uniformiVento.uFoglie.value, tempo: uniformiVento.uTempo.value,
    acqua: uniformiAcqua.uAcqua.value, schizzi: schizzi ? schizzi.userData.quante : 0,
    riduciMovimento: riduciMovimento.matches, lento: fpsBassi };
};
// test: tempo del vento impostato a mano (con __vento({ fermo: true }) resta fermo li': fotogrammi per le GIF)
window.__tempoVento = (t) => { uniformiVento.uTempo.value = t; };
window.__distanzaAlberi = (d) => { citta.distanzaAlberi = d; citta.tAlberi = 1; };   // 0.001 = tutti impostori
window.__chioma = (specie, tinta) => {                  // taratura: tinta lineare della chioma vera di una specie
  const m = citta.matChioma[specie]; if (!m) return null;
  if (tinta) m.color.setRGB(...tinta, THREE.LinearSRGBColorSpace);
  return m.color.toArray();   // lineare
};
window.__statistiche = () => ({ drawCall: renderer.info.render.calls, triangoli: renderer.info.render.triangles });
window.__luce = (o) => {                                 // per tarare la luce dai test
  if (o.sole !== undefined) sole.intensity = o.sole;
  if (o.cielo !== undefined) scena.environmentIntensity = o.cielo;
  if (o.rimbalzo !== undefined) rimbalzo.intensity = o.rimbalzo;
  if (o.esposizione !== undefined) renderer.toneMappingExposure = o.esposizione;
  if (o.ao !== undefined) uniformiAO.forza.value = o.ao;
  if (o.mostraAO !== undefined) uniformiAO.mostra.value = o.mostraAO;
  if (o.minima !== undefined) uniformiAO.minima.value = o.minima;
  for (const k of ['uCaldo', 'uContrasto', 'uSaturazione', 'uVignetta', 'uNeri']) if (o[k] !== undefined) gradazione.uniforms[k].value = o[k];
};

avvia().catch((e) => { stato.textContent = 'Errore di caricamento: ' + e.message; console.error(e); });
