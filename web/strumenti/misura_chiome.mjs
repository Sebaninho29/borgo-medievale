// Taratura delle chiome vere sugli impostori: per ogni vista confronta tre screenshot (sfondo senza alberi, impostore,
// albero vero). Maschera = pixel che differiscono dallo sfondo; colore medio lineare dei pixel di foglia (g >= r) nei due
// casi e rapporto impostore / vero per canale. Uso: node strumenti/misura_chiome.mjs <cartella> <vista> [<vista> ...]
// (file <vista>_sfondo.png, <vista>_imp.png, <vista>_vero.png)
import sharp from 'sharp';
import path from 'node:path';

const [dir, ...viste] = process.argv.slice(2);
const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
const leggi = async (f) => (await sharp(path.join(dir, f)).removeAlpha().raw().toBuffer({ resolveWithObject: true }));
for (const v of viste) {
  const S = await leggi(v + '_sfondo.png'), I = await leggi(v + '_imp.png'), R = await leggi(v + '_vero.png');
  const media = (X) => {
    const s = [0, 0, 0]; let n = 0, alta = 0, bassa = 0, na = 0, nb = 0;
    const W = X.info.width, H = X.info.height;
    for (let i = 0; i < X.data.length; i += 3) {
      const d = Math.abs(X.data[i] - S.data[i]) + Math.abs(X.data[i + 1] - S.data[i + 1]) + Math.abs(X.data[i + 2] - S.data[i + 2]);
      if (d < 40 || X.data[i + 1] < X.data[i]) continue;          // non e' albero, o non e' foglia (tronco)
      const r = lin(X.data[i]), g = lin(X.data[i + 1]), b = lin(X.data[i + 2]);
      s[0] += r; s[1] += g; s[2] += b; n++;
      // ombreggiatura: luminanza media della meta' piu' chiara e piu' scura (a soglia fissa sulla luminanza)
      const y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      if (y > 0.06) { alta += y; na++; } else { bassa += y; nb++; }
    }
    return { rgb: s.map((x) => x / n), n, chiari: na / n, yChiari: alta / Math.max(na, 1), yScuri: bassa / Math.max(nb, 1) };
  };
  const mi = media(I), mr = media(R);
  const f = (a) => a.map((x) => x.toFixed(4)).join(' ');
  console.log(`${v}: impostore ${f(mi.rgb)} (${mi.n} px, chiari ${(mi.chiari * 100).toFixed(0)}%) | vero ${f(mr.rgb)} (${mr.n} px, chiari ${(mr.chiari * 100).toFixed(0)}%)`);
  console.log(`   rapporto imp/vero ${f(mi.rgb.map((x, k) => x / mr.rgb[k]))}  luminanza chiari ${mi.yChiari.toFixed(3)}/${mr.yChiari.toFixed(3)} scuri ${mi.yScuri.toFixed(3)}/${mr.yScuri.toFixed(3)}`);
}
