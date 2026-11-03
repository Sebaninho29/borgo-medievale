// Post-produzione: N8AO (solo preset alto) -> tone mapping AgX -> correzione colore calda e contrastata.
import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { N8AOPass } from 'n8ao';

export const Gradazione = {
  uniforms: {
    tDiffuse: { value: null },
    uCaldo: { value: 0.08 },       // bianchi verso l'ocra, ombre appena fredde
    uContrasto: { value: 1.18 },
    uSaturazione: { value: 1.15 },
    uVignetta: { value: 0.22 },
    uNeri: { value: 0.02 },        // livello del nero
  },
  vertexShader: /* glsl */`varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse; uniform float uCaldo, uContrasto, uSaturazione, uVignetta, uNeri; varying vec2 vUv;
    void main() {
      vec4 c = texture2D(tDiffuse, vUv); vec3 col = c.rgb;
      float l = dot(col, vec3(0.2126, 0.7152, 0.0722));
      col *= mix(vec3(1.0 - uCaldo * 0.3, 1.0, 1.0 + uCaldo * 0.5), vec3(1.0 + uCaldo, 1.0 + uCaldo * 0.3, 1.0 - uCaldo), smoothstep(0.1, 0.7, l));
      col = mix(vec3(l), col, uSaturazione);
      // contrasto a curva a S attorno al grigio medio: 0 resta 0 e 1 resta 1, cosi' le ombre scure non finiscono
      // tagliate a nero pieno (con la retta (col - 0.5) * c + 0.5 tutto cio' che sta sotto ~0.08 diventava 0)
      col = clamp(col, 0.0, 1.0);
      col = mix(0.5 * pow(2.0 * col, vec3(uContrasto)), 1.0 - 0.5 * pow(2.0 - 2.0 * col, vec3(uContrasto)), step(0.5, col));
      col = uNeri + col * (1.0 - uNeri);                                          // nero appena sollevato, come in pellicola
      col *= mix(1.0 - uVignetta, 1.0, smoothstep(0.85, 0.3, distance(vUv, vec2(0.5))));
      gl_FragColor = vec4(clamp(col, 0.0, 1.0), c.a);
    }`,
};

export function creaComposer(renderer, scena, camera, qualita) {
  const w = innerWidth, h = innerHeight;
  const rt = new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, samples: qualita.msaa });
  const composer = new EffectComposer(renderer, rt);
  composer.setPixelRatio(renderer.getPixelRatio());
  let n8 = null;
  if (qualita.n8ao) {
    n8 = new N8AOPass(scena, camera, w, h);
    Object.assign(n8.configuration, { aoRadius: 2.0, distanceFalloff: 1.0, intensity: 2.2, aoSamples: 16,
      denoiseSamples: 8, denoiseRadius: 10, gammaCorrection: false, halfRes: true });
    composer.addPass(n8);
  } else composer.addPass(new RenderPass(scena, camera));
  composer.addPass(new OutputPass());
  const grad = new ShaderPass(Gradazione);
  composer.addPass(grad);
  addEventListener('resize', () => { composer.setSize(innerWidth, innerHeight); if (n8) n8.setSize(innerWidth, innerHeight); });
  return { composer, gradazione: grad, n8 };
}
