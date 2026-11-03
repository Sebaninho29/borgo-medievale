# Progetto: Quartiere medievale (Blender 5.2, Python)

## Obiettivo
Estendere `genera_quartiere.py` seguendo la pianta in `pianta_quartiere.png`:
la piazza del mercato esistente diventa il centro di un borgo murato con zone,
strade e edifici con un ruolo preciso. Stile: realistico, mista/fantasy, mattina d'estate.
Priorita' assoluta: resa estetica.

## File
- `genera_quartiere.py` - generatore procedurale. Ricostruisce TUTTA la scena da zero ogni volta.
  Parametri in cima al file. Salva in `%USERPROFILE%\Documents\Blender\Quartiere_Mercato\quartiere_mercato.blend`.
- `pianta_quartiere.png` - pianta approvata (coordinate in metri, 1 m = 1 unita' Blender,
  origine al centro della fontana, nord = +Y, est = +X).
- Texture Poly Haven (CC0) gia' scaricate in `%USERPROFILE%\Documents\Blender\Quartiere_Mercato\textures`.

## Comandi
- Generare la scena (con interfaccia):
  `"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --python genera_quartiere.py`
- Generare senza interfaccia (piu' veloce, per i test):
  `"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python genera_quartiere.py`
- Render di controllo dal file salvato (frame 1, camera attiva):
  `"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background "%USERPROFILE%\Documents\Blender\Quartiere_Mercato\quartiere_mercato.blend" --render-output //anteprima_ --render-format JPEG --render-frame 1`
  (per anteprime rapide abbassare CAMPIONI e risoluzione nei parametri)

## Architettura dello script (da rispettare)
- Geometria con `bmesh`; helper: `box`, `prism` (estrusione di un poligono lungo un asse), `lathe`, `sfera`, `arco_pts`, `rett`.
- Aperture (porte/finestre/archi) sottratte con booleano EXACT tramite `guscio(...)` + lista `tagli`.
- Ogni edificio = un oggetto unico (`unisci`), UV in metri con `uv_finale`, bordi smussati con `smussa`.
- Materiali PBR in `crea_materiali()`; slot fissi per gli edifici nella lista `MB` (indice via `I['nome']`).
- `edificio(...)` costruisce case generiche (stili: graticcio, intonaco, pietra; tetti: lato, fronte).
- `fila(...)` dispone le case lungo un lato lasciando i "buchi" per vicoli e strade.
- Facciate laterali esposte: matrice di lavoro `CM[0]` (vedi `edificio` e `finestre_laterali_palazzo`).
- Seme casuale `SEED`: stesso seme = stesso quartiere.

## Piano di lavoro (un passo alla volta, verificando con un render dopo ogni passo)
1. Strade: Via Maestra (est, larga 7 m, verso Porta Est), Via degli Artigiani (sud, 5 m, verso Porta Sud),
   Vicolo della Chiesa (nord), Via dei Nobili (ovest), Via del Borgo, Via del Sagrato, Stradella delle Mura.
   Le case si dispongono lungo le strade (generalizzare `fila` a una polilinea).
2. Mura con torri rotonde e due porte (Porta Est, Porta Sud) con arco e torri ai lati.
3. Zone: stile delle case per zona
   - Mercanti: case alte (3-4 piani), botteghe al piano terra.
   - Artigiani: case basse in pietra e legno, tettoie, cataste.
   - Borgo popolare: case piccole in legno, tetti di paglia, orti recintati.
   - Nobili: palazzetti in pietra con cortile, giardini con alberi, Torre dei Nobili.
   - Chiesa: chiesa con facciata a capanna, rosone, portale; campanile (riusare `torre`); sagrato.
   - Note richieste al passo 2:
     - materiale dei tetti dominante per zona (circa 80% delle case della zona), il resto vario;
     - case interne degli isolati (`isolati`, `riempi_spazi`) con orientamenti meno casuali
       (allineate agli isolati/alle file, meno rotazioni diverse tra case vicine).
4. Edifici con un ruolo, ognuno con funzione dedicata e dettagli riconoscibili:
   Locanda del Cinghiale (insegna, tavoli, stalle), Casa del mercante (argano, sacchi, casse),
   Fabbro (forgia, incudine, tettoia), Falegname (tavole, cavalletti), Forno (forno esterno, pane),
   Conceria (vasche), Pozzo degli artigiani.
5. Camere: aggiornare le inquadrature (una per zona) e un'aerea che mostri la pianta intera.

## Regole
- Non modificare le texture ne' rinominare la cartella del progetto.
- Mantenere i parametri in cima e i commenti in italiano.
- Dopo ogni modifica: eseguire lo script in background, controllare errori, fare un render di anteprima.
- Prestazioni: generazione completa sotto i 2 minuti; usare il booleano solo dove serve.
