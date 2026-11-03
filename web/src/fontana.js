// Fontana animata, come il vento: tutto negli shader, niente simulazione fisica.
// - getti (materiale acqua_getto): striature che scorrono verso il basso, trasparenza variabile, leggero tremolio
// - vasche (materiale acqua, solo entro 3,6 m dal centro della piazza): increspature circolari dai punti d'impatto e
//   un'ondulazione lieve di tutta la superficie; si piega la normale, quindi si muovono i riflessi del cielo
// - schizzi: poche particelle (232) nei punti d'impatto, solo nei preset medio e alto
// Geometria da genera_quartiere.py, fontana(): centro nell'origine, 4 getti alti che cadono a r = 0,85 m nella vasca
// alta (pelo dell'acqua a z = 2,29), 16 getti bassi a r = 1,55 / 1,5 m (alternati ogni 22,5 gradi) nella vasca bassa
// (z = 0,66). I punti sono simmetrici, quindi valgono uguali nelle coordinate di three (x, z = -y di Blender).
import * as THREE from 'three';

// uAcqua: forza dell'effetto (1 normale; main.js la riduce con "riduci movimento" o con gli fps bassi)
export const uniformiAcqua = { uAcqua: { value: 1 } };

const ALTO = { z: 2.29, r: 0.85, n: 4, a0: Math.PI / 4 };
const BASSO = { z: 0.66, r: [1.55, 1.5], n: 16 };

// comune ai due materiali: rumore e punti d'impatto (uTempo arriva dalle uniformi del vento)
export const FONTANA_GLSL = `
uniform float uAcqua;
float fh(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float fn(vec2 p) {
  vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(fh(i), fh(i + vec2(1, 0)), f.x), mix(fh(i + vec2(0, 1)), fh(i + vec2(1, 1)), f.x), f.y);
}
// punto d'impatto k della vasca (alta: 0-3, bassa: 0-15), coordinate xz
vec2 impatto(bool alta, int k) {
  if (alta) { float a = ${ALTO.a0.toFixed(6)} + float(k) * 1.5707963; return ${ALTO.r.toFixed(2)} * vec2(cos(a), sin(a)); }
  float a = float(k) * 0.3926991; return (mod(float(k), 2.0) < 0.5 ? ${BASSO.r[0].toFixed(2)} : ${BASSO.r[1].toFixed(2)}) * vec2(cos(a), sin(a));
}
`;

// vertex shader dei getti: tremolio di pochi millimetri, piu' forte in basso (il getto si apre cadendo)
export const GETTO_VERTEX = `
  { float c = clamp((2.9 - transformed.y) / 2.3, 0.0, 1.0);
    transformed.xz += (0.002 + 0.004 * c) * uAcqua * vec2(sin(uTempo * 23.0 + transformed.y * 37.0 + transformed.x * 11.0),
                                                         cos(uTempo * 19.0 + transformed.y * 31.0 + transformed.z * 13.0)); }
`;
// fragment dei getti: striature lungo il getto che scendono (fase legata all'altezza), trasparenza che varia con esse
export const GETTO_FRAGMENT = `
  { float v = (0.6 + 0.4 * uAcqua) * 3.2;                       // velocita' delle striature (m/s)
    float id = floor(atan(vPosMondo.z, vPosMondo.x) * 2.546);   // ogni getto la sua fase (16 settori)
    float s = fn(vec2(id * 7.3 + vPosMondo.x * 40.0 + vPosMondo.z * 40.0, (vPosMondo.y + uTempo * v) * 9.0));
    s = 0.6 * s + 0.4 * fn(vec2(id * 3.1, (vPosMondo.y + uTempo * v * 1.3) * 23.0));
    float st = mix(0.5, s, uAcqua);
    diffuseColor.rgb *= 0.7 + 0.6 * st;
    diffuseColor.a = clamp(diffuseColor.a * (0.35 + 1.5 * st), 0.08, 0.85); }
`;
// fragment delle vasche: pendenza della superficie = increspature dai punti d'impatto + ondulazione lieve; la normale
// (nello spazio della camera) si piega di conseguenza; schiuma chiara attorno agli impatti. Il pelo dell'acqua si
// riconosce dalla normale della faccia (derivate della posizione): la vasca alta ha le normali dei vertici smussate
// verso il bordo, inclinate
export const VASCA_FRAGMENT = `
  if (length(vPosMondo.xz) < 3.6 && vPosMondo.y > 0.5
      && abs(normalize(cross(dFdx(vPosMondo), dFdy(vPosMondo))).y) > 0.9) {
    bool alta = vPosMondo.y > 1.5;
    vec2 P = vPosMondo.xz, g = vec2(0.0);
    float dmin = 10.0;
    for (int k = 0; k < 16; k++) {
      if (alta && k >= 4) break;
      vec2 d = P - impatto(alta, k); float r = length(d) + 1e-4;
      dmin = min(dmin, r);
      float fase = r * 52.0 - uTempo * 9.0 + float(k) * 1.7;
      float onda = cos(fase) * 0.2 * exp(-r * 3.0) * smoothstep(0.0, 0.04, r);
      onda *= 0.75 + 0.25 * sin(uTempo * 2.3 + float(k) * 2.1);   // il getto non batte sempre uguale
      g += onda * d / r;
    }
    g += 0.035 * vec2(cos(P.x * 6.0 + uTempo * 1.1 + P.y * 2.0), cos(P.y * 5.0 - uTempo * 0.9 + P.x * 1.5))
       + 0.02 * vec2(cos(P.x * 11.0 - P.y * 7.0 + uTempo * 1.7), cos(P.y * 13.0 + P.x * 5.0 - uTempo * 1.4));
    g *= uAcqua;
    normal = normalize((viewMatrix * vec4(normalize(vec3(-g.x, 1.0, -g.y)), 0.0)).xyz);
    // schiuma: piccola e rotta (bolle che si muovono), non un disco pieno
    float b = fn(P * 55.0 + vec2(uTempo * 2.0, -uTempo * 1.5)) * fn(P * 23.0 - uTempo * 1.2);
    float schiuma = smoothstep(0.09, 0.01, dmin) * smoothstep(0.12, 0.45, b) * (0.4 + 0.6 * uAcqua);
    diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.8, 0.86, 0.88), schiuma * 0.6);
    diffuseColor.a = max(diffuseColor.a, schiuma * 0.8);
  }
`;

// schizzi: ogni particella rinasce nel suo punto d'impatto, sale e ricade in meno di un secondo (seme: fase, durata,
// direzione, forza). Con uAcqua < 1 una parte delle particelle resta spenta
export function creaSchizzi(uniformiVento) {
  const per = [];   // [x, y, z, quante]
  for (let k = 0; k < ALTO.n; k++) {
    const a = ALTO.a0 + k * Math.PI / 2; per.push([ALTO.r * Math.cos(a), ALTO.z, ALTO.r * Math.sin(a), 10]);
  }
  for (let k = 0; k < BASSO.n; k++) {
    const a = k * Math.PI / 8, r = BASSO.r[k % 2]; per.push([r * Math.cos(a), BASSO.z, r * Math.sin(a), 12]);
  }
  const n = per.reduce((s, p) => s + p[3], 0);
  const origine = new Float32Array(n * 3), seme = new Float32Array(n * 4);
  let i = 0, caso = 12345;
  const rnd = () => (caso = (caso * 16807) % 2147483647) / 2147483647;   // stesso schizzo a ogni caricamento
  for (const [x, y, z, q] of per) for (let j = 0; j < q; j++, i++) {
    origine.set([x + (rnd() - 0.5) * 0.08, y, z + (rnd() - 0.5) * 0.08], 3 * i);
    seme.set([rnd(), rnd(), rnd(), rnd()], 4 * i);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(origine.slice(), 3));   // solo per il culling
  geo.setAttribute('origine', new THREE.BufferAttribute(origine, 3));
  geo.setAttribute('seme', new THREE.BufferAttribute(seme, 4));
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 1.2, 0), 3.2);
  const mat = new THREE.ShaderMaterial({
    uniforms: { uTempo: uniformiVento.uTempo, uAcqua: uniformiAcqua.uAcqua, uScala: { value: 600 } },
    transparent: true, depthWrite: false,
    vertexShader: `
      uniform float uTempo; uniform float uAcqua; uniform float uScala;
      attribute vec3 origine; attribute vec4 seme;
      varying float vA;
      void main() {
        float vita = 0.4 + 0.35 * seme.y;
        float t = fract(uTempo / vita + seme.x) * vita;
        float a = seme.z * 6.2831853;
        vec3 p = origine + vec3(cos(a), 0.0, sin(a)) * (0.12 + 0.25 * seme.w) * t
               + vec3(0.0, (0.7 + 0.9 * seme.w) * t - 4.9 * t * t, 0.0);
        vA = (1.0 - t / vita) * step(origine.y - 0.005, p.y) * step(seme.x, uAcqua);
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_PointSize = max(1.5, (0.012 + 0.01 * seme.y) * uScala / -mv.z);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `
      varying float vA;
      void main() {
        float d = length(gl_PointCoord - 0.5);
        if (d > 0.5 || vA <= 0.0) discard;
        gl_FragColor = vec4(vec3(0.86, 0.92, 0.95), vA * 0.75 * (1.0 - d * 1.6));
        #include <colorspace_fragment>
      }`,
  });
  const punti = new THREE.Points(geo, mat);
  punti.name = 'schizzi_fontana'; punti.renderOrder = 2;
  punti.userData.quante = n;
  return punti;
}
