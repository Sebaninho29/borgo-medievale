# Il Borgo nel browser (Fase 2, passo 2)

La citta' intera in prima persona: three.js + Vite, collisioni con three-mesh-bvh, cielo HDRI.
Caricamento a zone: prima piazza e Via Maestra (centro), poi alberi, nord, sud, est, ovest in background.
La scena Blender non viene mai modificata: tutto cio' che serve al web sta in questa cartella.

## Rifare la citta'
1. Esportazione da Blender (zone, case interne semplificate con finestre dipinte, alberi come impostori,
   occlusione ambientale cotta nei colori dei vertici, materiali semplificati):

       "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background "%USERPROFILE%\Documents\Blender\Quartiere_Mercato\quartiere_mercato.blend" --python web\esporta_borgo.py

   scrive `_esportazione/citta/<zona>/` e `public/citta/citta.json` + `public/citta/impostori/` (~1 minuto).
2. Compressione (geometria meshopt, texture WebP condivise fra le zone, copia a 512 px):

       npm run citta

   L'esportatore corregge nella copia esportata alcuni difetti della scena (la scena non viene salvata): tronchi e
   sega del falegname, corda dei festoni che finiva nel Vicolo della Chiesa; fondo scuro leggibile per botteghe e
   rimesse. Diagonali del graticcio davanti alle finestre e ghiera del forno ora sono corrette nel generatore.
   Impostori degli alberi: chioma infittita (buchi riempiti con foglie vicine) e piu' verde; in three niente
   riflesso speculare sulle foglie. Intonaco e muri di pietra: macchie, sporco alla base e crepe nello shader
   (citta.js, in coordinate di mondo, come i nodi di genera_quartiere.py).
3. Alberi veri da vicino (dopo il punto 1, ~1 minuto):

       "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background "%USERPROFILE%\Documents\Blender\Quartiere_Mercato\quartiere_mercato.blend" --python web\esporta_alberi.py
       npm run alberi

   Per ogni variante: tronco e rami dei modelli Poly Haven decimati (i rametti piu' piccoli, dentro la chioma, tolti),
   chioma di "ciuffi" (carte con un atlante 2 x 2 renderizzato dalle foglie vere, occlusione nei colori dei vertici),
   cespugli con la mesh vera. ~1,8 MB in tutto (`public/citta/alberi/`).

## Alberi
Entro `alberi` metri dal giocatore (preset: basso 15, medio 30, alto 45; `?alberi=0` = solo impostori) ogni albero e'
il modello vero, oltre resta l'impostore. `aggiornaAlberi()` in `src/citta.js` li scambia ogni 0,1 s con 3 m di
isteresi. Chiome tarate sugli impostori (`CHIOMA`: tinta, normali piegate verso l'alto, occlusione addolcita;
`CORTECCIA`: tronco dell'island_tree piu' bruno), stesso vento degli impostori (`ventoChioma`). Costo misurato
(2026-11-03, RTX 2060, medio): +6 draw call, +13-130k triangoli, +0,45 ms di GPU nella vista peggiore (sotto la
jacaranda del sagrato). Anteprime: `anteprimelberi\` (griglia_prima_dopo.jpg, griglia3.jpg).

## Provare e pubblicare
    npm install
    npm run dev          (sviluppo)
    npm run build        (sito in dist/, ~45 MB)
    npm run preview      (http://localhost:4173)

Il sito usa percorsi relativi (`base: './'`): `dist/` si pubblica cosi' com'e' su Netlify o GitHub Pages.

Comandi: clic per entrare, W A S D o frecce, mouse, Maiusc per correre, Esc per uscire.
Segnalazioni: P salva posizione (coordinate Blender) + screenshot, L apre l'elenco (note, Vai, Scarica tutto in JSON).
`?pos=x,y,z,yaw,pitch` fa partire il giocatore in un punto preciso (quello di una segnalazione).
Sul telefono: levetta a sinistra, trascinare a destra per guardare.
Parametri nell'indirizzo: `?q=basso|medio|alto` (qualita'; sul telefono di default basso), `?bench` (misura).

## Vento
Stendardi, banderuole, festoni, teli delle bancarelle, tende delle botteghe, insegna della locanda e foglie degli alberi
si muovono nel vertex shader (`VENTO_GLSL` in `src/citta.js`), niente simulazione: onde con la fase che varia nello
spazio, un'unica direzione per tutto il borgo e raffiche lente e irregolari che lo attraversano.
- Tutti i parametri stanno in `VENTO` in cima a `src/citta.js`: direzione (`azimut`), ampiezze e ritmi per tipo, e
  **`VENTO.forza`, che scala tutte le ampiezze insieme** (1 = brezza leggera, 0 = aria ferma).
- Riferimento "brezza leggera": i festoni della piazza (dondolio fino a ~15 cm al centro delle corde, periodo ~7 s).
  Regola: piu' un oggetto e' grande e pesante, meno si muove e piu' lento oscilla; nessuno si muove piu' dei festoni.
  Stendardi: stoffa pesante (piega 4 cm, spinta 8 cm, dondolio laterale 7 cm, onde lunghe e lente; prima del
  2026-11-02 erano 18/52/24 cm). Banderuole piccole e lente; teli e tende: solo l'orlo della balza, 1-1,2 cm.
- Insegna della Locanda del Cinghiale: oggetto rigido (`Insegna_Cinghiale` nel generatore, origine sull'asse del braccio).
  Tavola e catene ruotano insieme attorno al braccio, nessuna piega: inclinazione media sottovento (fino a 1,7 gradi,
  secondo quanto il vento spinge sulle facce) + dondolio fino a 1,4 gradi con periodo ~3 s, guidati dalle stesse
  raffiche con 0,8 s di ritardo (al massimo ~3 gradi, 6 cm al bordo basso). Il braccio di ferro battuto resta fermo.
  Perno e asse arrivano da `citta.json` (`insegne`). In compressione il ferro dell'insegna viene unito al ferro del
  borgo (stessi parametri): per questo anche `ferro` e' fra i materiali col vento.
- L'esportatore (`liberta_tele` in `esporta_borgo.py`) scrive nei canali G, B, A dell'attributo AO: liberta' (0 sul bordo
  fissato ad asta, trave o corda, 1 sul bordo libero), tipo / 8 (1 stendardi, 2 banderuole, 3 teli, 4 tende,
  5 festoni, 6 insegna rigida) e dondolio dei festoni (quanto la corda scende sotto la retta fra i capi). R resta
  l'occlusione. I materiali `festone_*` contano come festoni solo nell'oggetto "Festoni": la vecchia insegna (una
  tavola `festone_crema`) e lo stemma della Porta Sud venivano piegati come tele. L'esportatore stampa l'elenco degli
  oggetti mossi dal vento, con i vertici per tipo ("vento: ..."), per controllare che nessun oggetto rigido sia una tela.
- Le ombre si muovono con le tele: stesso spostamento nel materiale di profondita' della luce del sole. Tele a due facce.
- "Riduci movimento" del sistema: forza al 25%, foglie ferme. Preset basso: se gli fps restano sotto 40 per 2 s
  forza al 40% e foglie ferme, torna normale dopo 5 s sopra 55.
- Test: `?bench` espone `__vento({forza, fermo, lento})`, `__tempoVento(t)` (tempo del vento a mano, con `fermo`),
  `__registra(n, passo)` (fotogrammi a passo fisso), `__vista(x, y, z, yaw, pitch, fissa, fov)`.
  Anteprime: `anteprime\vento\`, `anteprime\insegna\`.

## Fontana
Animata come il vento, tutto negli shader (`src/fontana.js`, agganciato ai materiali in `conAO` di `src/citta.js`):
- getti (`acqua_getto`): striature che scendono lungo il getto (fase legata all'altezza, ogni getto la sua), trasparenza
  che varia con le striature, tremolio di pochi millimetri piu' forte in basso;
- vasche (`acqua`, entro 3,6 m dal centro della piazza): increspature circolari dai 4 + 16 punti d'impatto, ondulazione
  lieve di tutta la superficie e schiuma rotta attorno agli impatti. Le vasche sono poligoni senza vertici interni:
  si piega la normale per pixel (si muovono i riflessi del cielo), il pelo dell'acqua si riconosce dalla normale della
  faccia (la vasca alta ha le normali dei vertici smussate);
- schizzi: 232 particelle (`THREE.Points`) nei punti d'impatto, solo nei preset medio e alto.
- Stesse regole del vento: "riduci movimento" porta l'effetto al 25%, fps bassi (sotto 40 per 2 s, controllati solo a
  borgo caricato) al 40% in ogni preset; con l'effetto ridotto si accende solo una parte degli schizzi.
- Test: `__vento()` riporta anche `acqua` e `schizzi`; `__vento({ lento: true })` impone gli fps bassi, `null` torna
  automatico. Anteprime e misure in `anteprime\fontana\`.

## Qualita'
- basso: texture 512 px, ombre 1024, niente antialiasing, alberi veri entro 15 m
- medio: texture 1k, ombre 2048, MSAA 4x, alberi veri entro 30 m
- alto: come medio + ombre 4096 + occlusione ambientale in tempo reale (N8AO), alberi veri entro 45 m
Sempre: AO cotta (vertici), luce di rimbalzo calda, tone mapping AgX, correzione colore calda e contrastata.

## File
- `esporta_borgo.py` - esportatore Blender -> glTF a zone (passo 2); `esporta_prototipo.py` - quello del passo 1
- `strumenti/prepara_citta.mjs` - compressione (npm run citta); `esporta_alberi.py` + `strumenti/prepara_alberi.mjs` - alberi veri (npm run alberi)
- Le zone sono esportate in riquadri di 25 m (quantizzazione precisa); `src/citta.js` le riunisce per materiale.
- `src/main.js` (scena, luce, avvio, misure), `src/citta.js` (zone, AO, acqua, impostori), `src/segnalazioni.js`, `src/giocatore.js`
  (movimento, collisioni, touch), `src/post.js` (N8AO, correzione colore)
