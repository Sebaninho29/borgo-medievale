// Giocatore in prima persona: capsula contro le BVH delle zone (esempio "characterMovement" di three-mesh-bvh),
// tastiera + mouse (Pointer Lock) oppure comandi touch (levetta a sinistra, sguardo trascinando a destra).
import * as THREE from 'three';
import { PointerLockControls } from 'three/examples/jsm/controls/PointerLockControls.js';

const VELOCITA = 3.2, CORSA = 6.5, GRAVITA = -20, RAGGIO = 0.32;

export class Giocatore {
  constructor(camera, elemento, altezza, partenza) {
    this.camera = camera; this.altezza = altezza; this.partenza = partenza.clone();
    this.pos = partenza.clone(); this.vel = new THREE.Vector3(); this.aTerra = false;
    this.segmento = new THREE.Line3(new THREE.Vector3(), new THREE.Vector3(0, -(altezza - RAGGIO), 0));
    this.tasti = {}; this.levetta = new THREE.Vector2(); this.collisori = [];
    this.controlli = new PointerLockControls(camera, elemento);
    addEventListener('keydown', (e) => { this.tasti[e.code] = true; });
    addEventListener('keyup', (e) => { this.tasti[e.code] = false; });
    this._v = new THREE.Vector3(); this._v2 = new THREE.Vector3(); this._mossa = new THREE.Vector3();
  }

  // comandi touch: meta' sinistra = levetta, meta' destra = sguardo
  attivaTouch(elementoLevetta, pomello) {
    const tocchi = new Map(), eul = new THREE.Euler(0, 0, 0, 'YXZ');
    const giu = (e) => {
      for (const t of e.changedTouches) {
        const sinistra = t.clientX < innerWidth / 2;
        tocchi.set(t.identifier, { x0: t.clientX, y0: t.clientY, x: t.clientX, y: t.clientY, sinistra });
        if (sinistra) { elementoLevetta.style.left = `${t.clientX - 60}px`; elementoLevetta.style.top = `${t.clientY - 60}px`; elementoLevetta.style.display = 'block'; }
      }
      e.preventDefault();
    };
    const muovi = (e) => {
      for (const t of e.changedTouches) {
        const s = tocchi.get(t.identifier); if (!s) continue;
        if (s.sinistra) {
          const dx = t.clientX - s.x0, dy = t.clientY - s.y0, d = Math.min(60, Math.hypot(dx, dy)), a = Math.atan2(dy, dx);
          this.levetta.set(Math.cos(a) * d / 60, -Math.sin(a) * d / 60);
          pomello.style.transform = `translate(${Math.cos(a) * d}px, ${Math.sin(a) * d}px)`;
        } else {
          eul.setFromQuaternion(this.camera.quaternion);
          eul.y -= (t.clientX - s.x) * 0.005; eul.x = THREE.MathUtils.clamp(eul.x - (t.clientY - s.y) * 0.005, -1.4, 1.4);
          this.camera.quaternion.setFromEuler(eul);
        }
        s.x = t.clientX; s.y = t.clientY;
      }
      e.preventDefault();
    };
    const su = (e) => {
      for (const t of e.changedTouches) {
        const s = tocchi.get(t.identifier);
        if (s && s.sinistra) { this.levetta.set(0, 0); pomello.style.transform = ''; elementoLevetta.style.display = 'none'; }
        tocchi.delete(t.identifier);
      }
    };
    const c = this.controlli.domElement;
    c.addEventListener('touchstart', giu, { passive: false }); c.addEventListener('touchmove', muovi, { passive: false });
    c.addEventListener('touchend', su); c.addEventListener('touchcancel', su);
  }

  aggiorna(dt) { for (let i = 0; i < 4; i++) this._passo(dt / 4); this.camera.position.copy(this.pos); }

  _passo(dt) {
    const { _v, _v2 } = this, t = this.tasti;
    let avanti = (t.KeyW || t.ArrowUp ? 1 : 0) - (t.KeyS || t.ArrowDown ? 1 : 0) + this.levetta.y;
    let lato = (t.KeyD || t.ArrowRight ? 1 : 0) - (t.KeyA || t.ArrowLeft ? 1 : 0) + this.levetta.x;
    const intensita = Math.min(1, Math.hypot(avanti, lato));
    const mossa = this._mossa.set(0, 0, 0);
    if (intensita > 0.05) {
      const v = (t.ShiftLeft || t.ShiftRight || this.levetta.length() > 0.95) ? CORSA : VELOCITA;
      this.camera.getWorldDirection(_v); _v.y = 0; _v.normalize();
      _v2.crossVectors(_v, this.camera.up).normalize();
      mossa.copy(_v.multiplyScalar(avanti).addScaledVector(_v2, lato).normalize().multiplyScalar(v * intensita));
    }
    passoCapsula(this, mossa, dt, this.collisori);
    if (this.pos.y < -10) { this.pos.copy(this.partenza); this.vel.set(0, 0, 0); }
  }
}

// Un passo di fisica della capsula (gravita', spostamento orizzontale 'mossa' in m/s, spinta fuori dai triangoli).
// stato = { pos (occhi), vel, aTerra, segmento }: lo usano il giocatore e il controllo delle trappole (trappole.js).
const _v = new THREE.Vector3(), _v2 = new THREE.Vector3(), _box = new THREE.Box3(), _seg = new THREE.Line3();
export function passoCapsula(stato, mossa, dt, collisori) {
  stato.vel.y += stato.aTerra ? 0 : dt * GRAVITA;
  stato.pos.addScaledVector(stato.vel, dt);
  stato.pos.addScaledVector(mossa, dt);
  _seg.copy(stato.segmento); _seg.start.add(stato.pos); _seg.end.add(stato.pos);
  _box.makeEmpty(); _box.expandByPoint(_seg.start); _box.expandByPoint(_seg.end);
  _box.min.addScalar(-RAGGIO); _box.max.addScalar(RAGGIO);
  for (const geo of collisori) {
    if (!geo.boundingBox.intersectsBox(_box)) continue;
    geo.boundsTree.shapecast({
      intersectsBounds: (b) => b.intersectsBox(_box),
      intersectsTriangle: (tri) => {
        const d = tri.closestPointToSegment(_seg, _v, _v2);
        if (d < RAGGIO) {
          const dir = _v2.sub(_v).normalize();
          _seg.start.addScaledVector(dir, RAGGIO - d); _seg.end.addScaledVector(dir, RAGGIO - d);
        }
      },
    });
  }
  const delta = _v.subVectors(_seg.start, stato.pos);
  stato.aTerra = delta.y > Math.abs(dt * stato.vel.y * 0.25);
  const off = Math.max(0, delta.length() - 1e-5); delta.normalize().multiplyScalar(off);
  stato.pos.add(delta);
  if (!stato.aTerra) { delta.normalize(); stato.vel.addScaledVector(delta, -delta.dot(stato.vel)); }
  else stato.vel.set(0, 0, 0);
}
export const FISICA = { VELOCITA, CORSA, RAGGIO };
