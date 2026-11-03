// Ombre del sole a due cascate (SunLight di three r186 + SunLightShadow con le cascate scelte qui).
// SunLightShadow divide la vista in due fette e racchiude ognuna in una sfera: con fov 70 e schermo 16:9 la seconda
// fetta diventa enorme (texel di 10-15 cm a meta' distanza). Qui invece:
// - cascata 0 (vicino): la fetta di vista fino a VICINO m, racchiusa nella sfera come nell'originale (raggio fisso,
//   quindi stabile quando si gira la testa): ~1,5 cm per texel con mappa 2048 (prima 4,9 cm su tutto);
// - cascata 1 (lontano): un quadrato di LONTANO m di lato fisso, centrato un po' avanti al giocatore (come prima il
//   riquadro di +-50 m, ma spostato verso dove si guarda), usato per tutto quello che sta oltre la cascata 0.
// I centri si agganciano alla griglia dei texel (niente ombre che "nuotano" camminando) e le due cascate si sfumano.
import { Matrix4, Vector3 } from 'three';
import { SunLightShadow } from 'three/examples/jsm/lights/SunLightShadow.js';

const _rot = new Matrix4(), _inv = new Matrix4(), _dir = new Vector3(), _su = new Vector3(), _c = new Vector3();
const _avanti = new Vector3(), _zero = new Vector3();
const _angoli = Array.from({ length: 8 }, () => new Vector3());

export class OmbraSole extends SunLightShadow {
  constructor({ vicino = 10, lontano = 100, avanti = 20, alto = 150 } = {}) {
    super();
    Object.assign(this, { vicino, lontano, avanti, alto });
  }

  updateMatrices(luce, vista) {
    if (vista === undefined) return;
    // margine dentro l'atlante: il filtro non legge nella cascata accanto
    const ix = Math.min(0.25, (Math.ceil(this.radius) + 1) / this.mapSize.x);
    const iy = Math.min(0.25, (Math.ceil(this.radius) + 1) / this.mapSize.y);
    for (let i = 0; i < 2; i++) this._viewports[i].set(i + ix, iy, 1 - 2 * ix, 1 - 2 * iy);
    const risoluzione = Math.min(this.mapSize.x * (1 - 2 * ix), this.mapSize.y * (1 - 2 * iy));

    // spazio della luce: z verso il sole
    _dir.setFromMatrixPosition(luce.matrixWorld).negate().normalize();
    _su.set(0, 1, 0); if (Math.abs(_su.dot(_dir)) > 0.99) _su.set(0, 0, 1);
    _rot.lookAt(_zero, _dir, _su); _inv.copy(_rot).transpose();

    // cascata 0: sfera attorno alla fetta di vista [near, vicino]
    const pi = vista.projectionMatrixInverse, near = vista.near;
    for (let k = 0; k < 4; k++) {
      const a = _angoli[k].set(k < 2 ? 1 : -1, k === 0 || k === 3 ? 1 : -1, -1).applyMatrix4(pi);
      _angoli[k + 4].copy(a).multiplyScalar(this.vicino / near);
    }
    _c.set(0, 0, 0);
    for (const a of _angoli) { a.applyMatrix4(vista.matrixWorld).applyMatrix4(_inv); _c.add(a); }
    _c.multiplyScalar(1 / 8);
    let r0 = 0;
    for (const a of _angoli) r0 = Math.max(r0, a.distanceTo(_c));
    this._cascata(0, _c, r0 / (1 - 1 / risoluzione), risoluzione);

    // cascata 1: quadrato fisso, centro avanti al giocatore (direzione dello sguardo in orizzontale)
    vista.getWorldDirection(_avanti); _avanti.y = 0;
    if (_avanti.lengthSq() > 1e-6) _avanti.normalize();
    _c.setFromMatrixPosition(vista.matrixWorld).addScaledVector(_avanti, this.avanti).applyMatrix4(_inv);
    this._cascata(1, _c, this.lontano / 2, risoluzione);

    // profondita' di vista delle cascate (inizio, fine, inizio della sfumatura): la 1 copre tutto oltre la 0
    const sfuma = this.vicino * 0.8;
    this._cascadeData[0].set(-1e10, this.vicino, sfuma, 0);
    this._cascadeData[1].set(sfuma, 1e10, 1e9, 0);
  }

  // centro c in spazio luce, mezzo lato r: aggancio alla griglia dei texel e camera della cascata i
  _cascata(i, c, r, risoluzione) {
    const texel = 2 * r / risoluzione;
    c.x = Math.round(c.x / texel) * texel; c.y = Math.round(c.y / texel) * texel;
    c.z += this.alto;
    const cam = this._cameras[i];
    cam.position.copy(c).applyMatrix4(_rot);
    cam.quaternion.setFromRotationMatrix(_rot);
    Object.assign(cam, { left: -r, right: r, top: r, bottom: -r, near: 1, far: 2 * this.alto });
    cam.updateProjectionMatrix(); cam.updateMatrixWorld();
    this._updateMatrix(cam, this._matrices[i], this._frustums[i], this._viewports[i]);
  }
}
