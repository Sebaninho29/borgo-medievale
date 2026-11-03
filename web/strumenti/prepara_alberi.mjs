// Comprime gli alberi veri esportati da esporta_alberi.py (web/_esportazione/alberi) in web/public/citta/alberi:
// geometria meshopt (le normali "a sfera" e l'occlusione delle chiome restano), texture WebP a 1k e a 512 px
// (preset basso e telefoni). Le texture stanno a parte (alberi.json dice quale va su ogni parte). Uso: npm run alberi
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dedup, prune, meshopt } from '@gltf-transform/functions';
import { MeshoptEncoder, MeshoptDecoder } from 'meshoptimizer';
import sharp from 'sharp';
import fs from 'node:fs';
import path from 'node:path';

const SORGENTE = '_esportazione/alberi';
const DEST = 'public/citta/alberi';
const QUALITA_WEBP = 82;

await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ 'meshopt.encoder': MeshoptEncoder, 'meshopt.decoder': MeshoptDecoder });

const dati = JSON.parse(fs.readFileSync(path.join(DEST, 'alberi.json'), 'utf8'));
for (const d of ['tex', 'tex512']) { fs.rmSync(path.join(DEST, d), { recursive: true, force: true }); fs.mkdirSync(path.join(DEST, d)); }
let geo = 0, tex = 0, tex512 = 0;
const fatte = new Set();
for (const [v, info] of Object.entries(dati.varianti)) {
  const doc = await io.read(path.join(SORGENTE, v + '.glb'));
  // posizioni a 16 bit sull'albero intero (al massimo ~20 m: errore sotto il millimetro)
  await doc.transform(dedup(), prune(), meshopt({ encoder: MeshoptEncoder, level: 'high', quantizePosition: 16 }));
  const file = path.join(DEST, v + '.glb');
  await io.write(file, doc);
  geo += fs.statSync(file).size;
  for (const p of info.parti) {
    const nome = p.tex.replace(/\.[a-z]+$/i, '');
    p.tex = nome + '.webp';
    if (fatte.has(nome)) continue;
    fatte.add(nome);
    const src = sharp(path.join(SORGENTE, path.basename(p.tex, '.webp') + (fs.existsSync(path.join(SORGENTE, nome + '.png')) ? '.png' : '.jpg')));
    const alfa = p.tipo === 'foglie';
    const opz = { quality: QUALITA_WEBP, alphaQuality: 90, effort: 6 };
    await src.clone().webp(opz).toFile(path.join(DEST, 'tex', p.tex));
    await src.clone().resize(512, 512).webp(opz).toFile(path.join(DEST, 'tex512', p.tex));
    tex += fs.statSync(path.join(DEST, 'tex', p.tex)).size; tex512 += fs.statSync(path.join(DEST, 'tex512', p.tex)).size;
    if (alfa) console.log(`  atlante ${p.tex}`);
  }
  console.log(`${v}: ${(fs.statSync(file).size / 1e3).toFixed(0)} kB`);
}
fs.writeFileSync(path.join(DEST, 'alberi.json'), JSON.stringify(dati));
console.log(`alberi: ${(geo / 1e6).toFixed(2)} MB di geometria, texture ${(tex / 1e6).toFixed(2)} MB (512 px: ${(tex512 / 1e6).toFixed(2)} MB)`);
