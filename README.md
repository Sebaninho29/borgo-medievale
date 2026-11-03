# Borgo medievale

Un borgo murato generato proceduralmente in Blender (Python, `bmesh`) ed esplorabile in prima persona nel browser
(three.js). Stile realistico con un tocco fantasy, mattina d'estate.

**Sito:** https://sebaninho29.github.io/borgo-medievale/

## Contenuto
- `genera_quartiere.py` - generatore: ricostruisce da zero l'intera scena (strade, mura, porte, zone, edifici con un
  ruolo, camere). Parametri in cima al file; seme `SEED` = stesso borgo.
- `pianta_quartiere.png` - pianta approvata (1 m = 1 unita' Blender, origine al centro della fontana, nord = +Y).
- `CLAUDE.md` - obiettivo, architettura dello script e regole del progetto.
- `web/` - il borgo nel browser: esportatori Blender -> glTF (`esporta_borgo.py`, `esporta_alberi.py`), strumenti di
  compressione (`web/strumenti`), sorgenti three.js (`web/src`). Dettagli e comandi in [`web/README.md`](web/README.md).

## Cosa non c'e' (pesante o rigenerabile)
La scena `.blend`, le texture e i modelli Poly Haven (CC0, si riscaricano da polyhaven.com), le esportazioni
(`web/_esportazione`, `web/public/citta`), il sito compilato (`web/dist`, pubblicato sul ramo `gh-pages`),
`node_modules`, render e anteprime.

## Rifare tutto
1. Scena: `blender --background --python genera_quartiere.py` (Blender 5.2; texture in
   `D:\Quartiere_Mercato\Blender\textures`).
2. Web: esportazione e compressione come in `web/README.md`, poi `npm install` e `npm run build` in `web/`.
3. Pubblicazione: `bash web/strumenti/pubblica_pages.sh` (copia `web/dist` sul ramo `gh-pages`).
