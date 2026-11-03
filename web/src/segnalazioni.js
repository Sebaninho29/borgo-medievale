// Segnalazioni dei difetti: P salva posizione (coordinate Blender), direzione dello sguardo e uno screenshot;
// L apre l'elenco (note, "Vai", scarica tutto in JSON). Tutto resta nel browser (localStorage).
const CHIAVE = 'borgo_segnalazioni';

export class Segnalazioni {
  constructor({ renderer, camera, vaiA, qualita, sbloccaPuntatore }) {
    Object.assign(this, { renderer, camera, vaiA, qualita, sbloccaPuntatore });
    this.inAttesa = false;
    try { this.lista = JSON.parse(localStorage.getItem(CHIAVE) || '[]'); } catch { this.lista = []; }
    this.pannello = document.getElementById('segnalazioni');
    this.avviso = document.getElementById('avviso');
    addEventListener('keydown', (e) => {
      if (e.target.tagName === 'TEXTAREA') return;
      if (e.code === 'KeyP') this.richiedi();
      if (e.code === 'KeyL') this.apriChiudi();
    });
    document.getElementById('btn-segnala').addEventListener('click', (e) => { e.stopPropagation(); this.richiedi(); });
    document.getElementById('btn-elenco').addEventListener('click', (e) => { e.stopPropagation(); this.apriChiudi(); });
  }

  richiedi() { this.inAttesa = true; }   // lo screenshot si prende subito dopo il prossimo render

  // da chiamare nel ciclo subito dopo il render (il buffer di WebGL e' ancora valido)
  dopoRender() {
    if (!this.inAttesa) return;
    this.inAttesa = false;
    const src = this.renderer.domElement, c = document.createElement('canvas');
    const w = 640, h = Math.round(640 * src.height / src.width);
    c.width = w; c.height = h; c.getContext('2d').drawImage(src, 0, 0, w, h);
    const p = this.camera.position, r = this.camera.rotation;
    const s = {
      n: (this.lista.at(-1)?.n || 0) + 1, quando: new Date().toISOString(), qualita: this.qualita,
      pos: [+p.x.toFixed(2), +(-p.z).toFixed(2), +p.y.toFixed(2)],                // Blender (x, y, z)
      sguardo: [+(r.y * 180 / Math.PI).toFixed(1), +(r.x * 180 / Math.PI).toFixed(1)],   // yaw, pitch (gradi)
      nota: '', img: c.toDataURL('image/jpeg', 0.75),
    };
    this.lista.push(s); this.salva();
    this.mostraAvviso(`Segnalazione ${s.n} salvata: x ${s.pos[0]}, y ${s.pos[1]}  (L per l'elenco)`);
    if (this.pannello.style.display === 'block') this.disegna();
  }

  salva() {
    try { localStorage.setItem(CHIAVE, JSON.stringify(this.lista)); }
    catch { this.mostraAvviso('Memoria del browser piena: scarica le segnalazioni e svuota l\'elenco'); }
  }

  mostraAvviso(t) {
    this.avviso.textContent = t; this.avviso.style.display = 'block';
    clearTimeout(this._t); this._t = setTimeout(() => { this.avviso.style.display = 'none'; }, 3500);
  }

  apriChiudi() {
    const aperto = this.pannello.style.display === 'block';
    this.pannello.style.display = aperto ? 'none' : 'block';
    if (!aperto) { this.sbloccaPuntatore(); this.disegna(); }
  }

  disegna() {
    const el = this.pannello; el.innerHTML = '';
    const testa = document.createElement('div'); testa.className = 'testa';
    testa.innerHTML = `<b>Segnalazioni (${this.lista.length})</b>`;
    const bottoni = [['Scarica tutto', () => this.scarica()], ['Copia elenco', () => this.copia()],
      ['Svuota', () => { if (confirm('Cancellare tutte le segnalazioni?')) { this.lista = []; this.salva(); this.disegna(); } }],
      ['Chiudi', () => this.apriChiudi()]];
    for (const [t, f] of bottoni) { const b = document.createElement('button'); b.textContent = t; b.onclick = f; testa.appendChild(b); }
    el.appendChild(testa);
    if (!this.lista.length) {
      const v = document.createElement('p'); v.textContent = 'Nessuna segnalazione. Premi P (o il pulsante a destra) davanti a un difetto.';
      el.appendChild(v);
    }
    for (const s of [...this.lista].reverse()) {
      const r = document.createElement('div'); r.className = 'voce';
      r.innerHTML = `<img src="${s.img}" alt="Segnalazione ${s.n}"><div class="dati"><b>#${s.n}</b>
        x ${s.pos[0]} &middot; y ${s.pos[1]} &middot; z ${s.pos[2]} &middot; sguardo ${s.sguardo[0]}&deg; / ${s.sguardo[1]}&deg;
        <textarea placeholder="Che cosa non va qui?"></textarea></div>`;
      const ta = r.querySelector('textarea'); ta.value = s.nota;
      ta.oninput = () => { s.nota = ta.value; this.salva(); };
      const dati = r.querySelector('.dati');
      const vai = document.createElement('button'); vai.textContent = 'Vai';
      vai.onclick = () => { this.vaiA(s.pos, s.sguardo); this.apriChiudi(); };
      const via = document.createElement('button'); via.textContent = 'Elimina';
      via.onclick = () => { this.lista = this.lista.filter((x) => x !== s); this.salva(); this.disegna(); };
      dati.append(vai, via);
      el.appendChild(r);
    }
  }

  testo() {
    return this.lista.map((s) => `#${s.n} pos ${s.pos.join(', ')} sguardo ${s.sguardo.join(', ')} [${s.qualita}] ${s.nota}`).join('\n');
  }

  copia() { navigator.clipboard?.writeText(this.testo()).then(() => this.mostraAvviso('Elenco copiato negli appunti')); }

  scarica() {
    const blob = new Blob([JSON.stringify({ sito: location.href, segnalazioni: this.lista }, null, 1)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = `segnalazioni_borgo_${new Date().toISOString().slice(0, 10)}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
}
