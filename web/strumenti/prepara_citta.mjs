// Comprime le zone esportate da Blender (web/_esportazione/citta) in web/public/citta:
// geometria meshopt, texture WebP condivise fra le zone (stesso nome = stesso file) e copia a 512 px
// per i telefoni e il preset basso. Uso: npm run citta
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dedup, prune, meshopt, textureCompress } from '@gltf-transform/functions';
import { MeshoptEncoder, MeshoptDecoder } from 'meshoptimizer';
import sharp from 'sharp';
import fs from 'node:fs';
import path from 'node:path';

const SORGENTE = '_esportazione/citta';
const DEST = 'public/citta';
const QUALITA_WEBP = 80;

await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ 'meshopt.encoder': MeshoptEncoder, 'meshopt.decoder': MeshoptDecoder });

const dati = JSON.parse(fs.readFileSync(path.join(DEST, 'citta.json'), 'utf8'));
fs.rmSync(path.join(DEST, 'tex'), { recursive: true, force: true });
for (const z of dati.zone) {
  const doc = await io.read(path.join(SORGENTE, z.nome, z.file));
  await doc.transform(
    dedup(), prune(),
    textureCompress({ encoder: sharp, targetFormat: 'webp', quality: QUALITA_WEBP }),
    // posizioni a 16 bit, relative a ogni mesh (riquadri di 25 m: errore sotto il millimetro)
    meshopt({ encoder: MeshoptEncoder, level: 'high', quantizePosition: 16, quantizationVolume: 'mesh' }),
  );
  for (const t of doc.getRoot().listTextures()) {          // nomi stabili: la stessa texture e' un solo file
    const nome = path.basename(t.getURI() || t.getName()).replace(/\.[a-z]+$/i, '');
    t.setURI(`tex/${nome}.webp`);
  }
  doc.getRoot().listBuffers().forEach((b) => b.setURI(z.nome + '.bin'));
  await io.write(path.join(DEST, z.file), doc);
  const peso = fs.statSync(path.join(DEST, z.nome + '.bin')).size + fs.statSync(path.join(DEST, z.file)).size;
  z.peso = peso;
  z.texture = doc.getRoot().listTextures().map((t) => t.getURI());
  console.log(`${z.nome}: ${(peso / 1e6).toFixed(1)} MB di geometria, ${z.texture.length} texture`);
}
// copia ridotta delle texture per il preset basso
const dir = path.join(DEST, 'tex'), dir512 = path.join(DEST, 'tex512');
fs.rmSync(dir512, { recursive: true, force: true }); fs.mkdirSync(dir512);
let tot = 0, tot512 = 0;
for (const f of fs.readdirSync(dir)) {
  const img = sharp(path.join(dir, f)), m = await img.metadata();
  await img.resize(Math.max(1, Math.round(m.width / 2)), Math.max(1, Math.round(m.height / 2)))
    .webp({ quality: QUALITA_WEBP }).toFile(path.join(dir512, f));
  tot += fs.statSync(path.join(dir, f)).size; tot512 += fs.statSync(path.join(dir512, f)).size;
}
fs.writeFileSync(path.join(DEST, 'citta.json'), JSON.stringify(dati));
console.log(`texture: ${fs.readdirSync(dir).length} file, ${(tot / 1e6).toFixed(1)} MB (512 px: ${(tot512 / 1e6).toFixed(1)} MB)`);
