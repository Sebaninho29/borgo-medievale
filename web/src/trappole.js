// Controllo automatico delle trappole: punti del borgo dove il giocatore arriva camminando ma da cui non torna piu'
// (buche, vani chiusi, gradini troppo alti per risalire). Si carica solo con ?trappole (main.js, a borgo caricato).
//
// 1. Griglia di colonne ogni PASSO m: per ogni colonna i "pavimenti" (facce quasi orizzontali colpite da un raggio
//    verticale) su cui la capsula del giocatore sta in piedi (parte alta libera da muri).
// 2. Grafo: da un pavimento si va alla colonna vicina se il pavimento di arrivo e' al massimo GRADINO piu' su
//    (scendere si puo' sempre: si cade) e a meta' strada la capsula passa.
// 3. F = pavimenti raggiungibili dalla partenza, B = pavimenti da cui si torna alla partenza. Trappole = F \ B,
//    riunite in gruppi vicini.
// 4. Verifica con la fisica vera del giocatore (passoCapsula): da alcuni punti di ogni gruppo si corre e si cammina
//    in 16 direzioni; se un tentativo arriva in B il gruppo e' un falso allarme.
// Coordinate: three (x, y in alto, z = -y Blender); i risultati sono in coordinate Blender.
import * as THREE from 'three';
import { passoCapsula, FISICA } from './giocatore.js';

const PASSO = 0.25;           // m fra le colonne (piu' fine del diametro della capsula: vani stretti compresi)
const ALTO = 1.7;             // occhi sopra i piedi (come ALTEZZA_OCCHI)
const GRADINO = 0.30;         // dislivello che la capsula (raggio 0,32) supera camminando
const LIBERO = 0.5;           // la capsula si controlla da qui in su (gradini e cordoli piu' bassi non bloccano)
const MAX_PIANI = 24;         // pavimenti per colonna (sopra un portale ci sono ghiere, cornici, rosone: 17 facce)
const CADUTA = 3;             // colonne oltre uno spigolo dove si puo' atterrare scendendo
const AREA ={ x0: -106, x1: 140, y0: -101, y1: 104 };   // Blender: mura, fossato e ponti con margine
const R = FISICA.RAGGIO;

export async function cercaTrappole(collisori, partenza, suAvanzamento = () => {}) {
  const t0 = performance.now();
  const nx = Math.floor((AREA.x1 - AREA.x0) / PASSO) + 1, ny = Math.floor((AREA.y1 - AREA.y0) / PASSO) + 1;
  const pavimenti = new Map();            // colonna -> Float32Array delle quote (dall'alto in basso)
  const valido = new Int8Array(nx * ny * MAX_PIANI);   // 0 da calcolare, 1 si', -1 no
  const raggio = new THREE.Ray(new THREE.Vector3(), new THREE.Vector3(0, -1, 0));
  const seg = new THREE.Line3(), box = new THREE.Box3(), p1 = new THREE.Vector3(), p2 = new THREE.Vector3();
  let raggi = 0, capsule = 0;

  const colX = (i) => AREA.x0 + i * PASSO, colY = (j) => AREA.y0 + j * PASSO;   // Blender
  function piani(c) {
    let f = pavimenti.get(c);
    if (f) return f;
    const x = colX(c % nx), z = -colY(Math.floor(c / nx)), q = [];
    raggio.origin.set(x, 120, z); raggi++;
    for (const g of collisori) {
      const bb = g.boundingBox;
      if (x < bb.min.x || x > bb.max.x || z < bb.min.z || z > bb.max.z) continue;
      for (const h of g.boundsTree.raycast(raggio, THREE.DoubleSide)) if (Math.abs(h.face.normal.y) > 0.5) q.push(h.point.y);
    }
    q.sort((a, b) => b - a);
    const u = [];
    for (const y of q) if (!u.length || u[u.length - 1] - y > 0.08) u.push(y);
    f = new Float32Array(u.slice(0, MAX_PIANI));
    pavimenti.set(c, f);
    return f;
  }
  // capsula libera fra base+LIBERO e base+ALTO nel punto (x, z) three
  function libera(x, z, base) {
    capsule++;
    seg.start.set(x, base + ALTO, z); seg.end.set(x, base + LIBERO, z);
    box.makeEmpty(); box.expandByPoint(seg.start); box.expandByPoint(seg.end);
    box.min.addScalar(-R); box.max.addScalar(R);
    for (const g of collisori) {
      if (!g.boundingBox.intersectsBox(box)) continue;
      const urto = g.boundsTree.shapecast({
        intersectsBounds: (b) => b.intersectsBox(box),
        intersectsTriangle: (tri) => tri.closestPointToSegment(seg, p1, p2) < R - 0.02,
      });
      if (urto) return false;
    }
    return true;
  }
  const nodo = (c, k) => c * MAX_PIANI + k;
  function nodoValido(c, k) {
    const n = nodo(c, k);
    if (!valido[n]) valido[n] = libera(colX(c % nx), -colY(Math.floor(c / nx)), piani(c)[k]) ? 1 : -1;
    return valido[n] === 1;
  }
  // archi uscenti da (c, k): verso le 8 colonne vicine
  const VICINI = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]];
  function uscenti(c, k, out) {
    out.length = 0;
    const i = c % nx, j = Math.floor(c / nx), fa = piani(c)[k];
    for (const [di, dj] of VICINI) {
      const i2 = i + di, j2 = j + dj;
      if (i2 < 0 || j2 < 0 || i2 >= nx || j2 >= ny) continue;
      const c2 = j2 * nx + i2, f2 = piani(c2);
      const k2 = f2.findIndex((y) => y <= fa + GRADINO);   // il pavimento piu' alto raggiungibile (o su cui si cade)
      if (k2 < 0) continue;
      const base = Math.max(fa, f2[k2]);
      if (!libera((colX(i) + colX(i2)) / 2, -(colY(j) + colY(j2)) / 2, base)) continue;
      if (nodoValido(c2, k2)) { out.push(nodo(c2, k2)); continue; }
      // giu' da un bordo: accanto allo spigolo la capsula non sta in piedi (tocca il bordo), ma ci si passa alla
      // quota di partenza e si atterra piu' in la' (fino a CADUTA colonne)
      if (f2[k2] > fa - 0.05) continue;
      for (let s = 2; s <= CADUTA; s++) {
        const i3 = i + di * s, j3 = j + dj * s;
        if (i3 < 0 || j3 < 0 || i3 >= nx || j3 >= ny) break;
        if (!libera(colX(i + di * (s - 1)), -colY(j + dj * (s - 1)), fa)) break;
        const c3 = j3 * nx + i3, k3 = piani(c3).findIndex((y) => y <= fa + 0.05);
        if (k3 >= 0 && nodoValido(c3, k3)) { out.push(nodo(c3, k3)); break; }
      }
    }
    return out;
  }

  // nodo di partenza: colonna piu' vicina, pavimento piu' alto sotto gli occhi
  const ci = Math.round((partenza.x - AREA.x0) / PASSO), cj = Math.round((-partenza.z - AREA.y0) / PASSO);
  const c0 = cj * nx + ci, k0 = Array.from(piani(c0)).findIndex((y) => y <= partenza.y - 0.5);
  if (k0 < 0 || !nodoValido(c0, k0)) return { errore: 'partenza non valida', partenza: partenza.toArray() };
  const start = nodo(c0, k0);

  // F: visita in avanti; si salvano gli archi per la visita all'indietro
  const inF = new Uint8Array(nx * ny * MAX_PIANI), coda = [start], da = [], a = [], tmp = [];
  inF[start] = 1;
  for (let q = 0; q < coda.length; q++) {
    const n = coda[q];
    for (const m of uscenti(Math.floor(n / MAX_PIANI), n % MAX_PIANI, tmp)) {
      da.push(n); a.push(m);
      if (!inF[m]) { inF[m] = 1; coda.push(m); }
    }
    if ((q & 4095) === 4095) { suAvanzamento(`grafo: ${q} pavimenti`); await new Promise((r) => setTimeout(r, 0)); }
  }
  // B: visita all'indietro dalla partenza
  const entranti = new Map();
  for (let e = 0; e < da.length; e++) { const l = entranti.get(a[e]); if (l) l.push(da[e]); else entranti.set(a[e], [da[e]]); }
  const inB = new Uint8Array(inF.length), coda2 = [start];
  inB[start] = 1;
  for (let q = 0; q < coda2.length; q++) for (const m of entranti.get(coda2[q]) || []) if (!inB[m]) { inB[m] = 1; coda2.push(m); }

  // gruppi di trappole (vicinanza fra colonne, qualsiasi piano entro 1 m di quota)
  const trappola = coda.filter((n) => !inB[n]);
  const gruppo = new Map(); const gruppi = [];
  const quota = (n) => piani(Math.floor(n / MAX_PIANI))[n % MAX_PIANI];
  const perColonna = new Map();
  for (const n of trappola) { const c = Math.floor(n / MAX_PIANI); (perColonna.get(c) || perColonna.set(c, []).get(c)).push(n); }
  for (const n of trappola) {
    if (gruppo.has(n)) continue;
    const g = [n]; gruppo.set(n, gruppi.length);
    for (let q = 0; q < g.length; q++) {
      const c = Math.floor(g[q] / MAX_PIANI), i = c % nx, j = Math.floor(c / nx);
      for (const [di, dj] of VICINI) for (const m of perColonna.get((j + dj) * nx + i + di) || []) {
        if (!gruppo.has(m) && Math.abs(quota(m) - quota(g[q])) < 1.0) { gruppo.set(m, gruppi.length); g.push(m); }
      }
    }
    gruppi.push(g);
  }

  // verifica con la fisica del giocatore
  const stato = { pos: new THREE.Vector3(), vel: new THREE.Vector3(), aTerra: false,
    segmento: new THREE.Line3(new THREE.Vector3(), new THREE.Vector3(0, -(ALTO - R), 0)) };
  const mossa = new THREE.Vector3(), DT = 1 / 240;
  function nodoDi(p) {   // pavimento della colonna sotto p (occhi) entro 0,35 m
    const i = Math.round((p.x - AREA.x0) / PASSO), j = Math.round((-p.z - AREA.y0) / PASSO);
    if (i < 0 || j < 0 || i >= nx || j >= ny) return -1;
    const c = j * nx + i, f = piani(c), piedi = p.y - ALTO;
    const k = Array.from(f).findIndex((y) => Math.abs(y - piedi) < 0.35);
    return k < 0 ? -1 : nodo(c, k);
  }
  function esce(n, ang, vel) {
    const c = Math.floor(n / MAX_PIANI);
    stato.pos.set(colX(c % nx), quota(n) + ALTO + 0.02, -colY(Math.floor(c / nx)));
    stato.vel.set(0, 0, 0); stato.aTerra = false;
    mossa.set(Math.cos(ang) * vel, 0, -Math.sin(ang) * vel);
    for (let s = 0; s < 240 * 3; s++) {
      passoCapsula(stato, mossa, DT, collisori);
      if (s % 12 === 11) { const m = nodoDi(stato.pos); if (m >= 0 && inB[m]) return true; }
    }
    return false;
  }
  const risultato = [];
  for (const [gi, g] of gruppi.entries()) {
    suAvanzamento(`verifica: gruppo ${gi + 1}/${gruppi.length}`); await new Promise((r) => setTimeout(r, 0));
    const campioni = [g[0], g[Math.floor(g.length / 3)], g[Math.floor(2 * g.length / 3)], g[g.length - 1]];
    let uscito = false;
    for (const n of new Set(campioni)) {
      for (let d = 0; d < 16 && !uscito; d++) for (const v of [FISICA.CORSA, FISICA.VELOCITA]) if (esce(n, d * Math.PI / 8, v)) { uscito = true; break; }
      if (uscito) break;
    }
    let sx = 0, sy = 0, zmin = Infinity, zmax = -Infinity, x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const n of g) {
      const c = Math.floor(n / MAX_PIANI), x = colX(c % nx), y = colY(Math.floor(c / nx)), z = quota(n);
      sx += x; sy += y; zmin = Math.min(zmin, z); zmax = Math.max(zmax, z);
      x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
    }
    // quota del bordo: il pavimento piu' alto di B attorno al gruppo (quanto bisogna risalire)
    let bordo = -Infinity;
    for (const n of g) {
      const c = Math.floor(n / MAX_PIANI), i = c % nx, j = Math.floor(c / nx);
      for (const [di, dj] of VICINI) {
        const c2 = (j + dj) * nx + i + di; const f = pavimenti.get(c2); if (!f) continue;
        f.forEach((y, k) => { if (inB[nodo(c2, k)] && y < quota(n) + 2) bordo = Math.max(bordo, y); });
      }
    }
    risultato.push({ confermata: !uscito, area: +(g.length * PASSO * PASSO).toFixed(2),
      centro: [+(sx / g.length).toFixed(1), +(sy / g.length).toFixed(1)], quota: [+zmin.toFixed(2), +zmax.toFixed(2)],
      bordo: Number.isFinite(bordo) ? +bordo.toFixed(2) : null,
      riquadro: [x0, y0, x1, y1].map((v) => +v.toFixed(1)) });
  }
  risultato.sort((p, q) => q.area - p.area);
  // diagnosi: pavimenti di una colonna (coordinate Blender) con validita', F e B
  window.__sondaTrappole = (bx, by) => {
    const c = Math.round((by - AREA.y0) / PASSO) * nx + Math.round((bx - AREA.x0) / PASSO);
    return Array.from(piani(c)).map((y, k) => ({ y: +y.toFixed(3), valido: nodoValido(c, k), F: !!inF[nodo(c, k)], B: !!inB[nodo(c, k)],
      archi: uscenti(c, k, []).map((m) => [Math.floor(m / MAX_PIANI) - c, +quota(m).toFixed(2)]) }));
  };
  window.__raggioTrappole = (bx, by) => {   // tutte le facce sotto un punto qualsiasi
    raggio.origin.set(bx, 120, -by); const h = [];
    for (const g of collisori) for (const x of g.boundsTree.raycast(raggio, THREE.DoubleSide)) h.push([+x.point.y.toFixed(3), +x.face.normal.y.toFixed(2)]);
    return h.sort((p, q) => q[0] - p[0]);
  };
  return { trappole: risultato.filter((t) => t.confermata), falsiAllarmi: risultato.filter((t) => !t.confermata),
    raggiungibili: coda.length, areaRaggiungibile: coda.length * PASSO * PASSO, ritorno: coda2.length,
    raggi, capsule, secondi: +((performance.now() - t0) / 1000).toFixed(1) };
}
