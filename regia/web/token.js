"use strict";
/* Regia — scheda Token. Legge /api/token (calcoli di dont-waste-your-token) solo quando la scheda è aperta, ogni 60 s.
   Testo sempre via textContent; SVG costruito con createElementNS. */
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const CH = "plancia.vista";
  const q = (s) => document.querySelector(s);
  let vista = "sessioni", dati = null, timer = null;
  try { vista = localStorage.getItem(CH) === "token" ? "token" : "sessioni"; } catch (_) { /* senza memoria */ }

  const e = (tag, cls, testo) => { const x = document.createElement(tag); if (cls) x.className = cls; if (testo != null) x.textContent = testo; return x; };
  const s = (tag, attr) => { const x = document.createElementNS(NS, tag); for (const k in attr) x.setAttribute(k, attr[k]); return x; };
  const pct = (v) => (v == null ? "—" : `${Math.round(v)} %`);
  const quando = (t) => new Date(t * 1000).toLocaleString("it-IT", { weekday: "short", hour: "2-digit", minute: "2-digit" });
  const ore = (t) => new Date(t * 1000).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
  const dec = (n) => Number(n).toLocaleString("it-IT", { maximumFractionDigits: 1 });
  const tra = (t) => { const m = Math.max(0, Math.round((t - Date.now() / 1000) / 60)); return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`; };
  const milioni = (n) => (n >= 1e6 ? `${(n / 1e6).toLocaleString("it-IT", { maximumFractionDigits: 1 })} M` : n >= 1e3 ? `${Math.round(n / 1e3)} k` : String(n));

  /* ---------- schede ---------- */
  function mostra(v, fuoco) {
    vista = v;
    try { localStorage.setItem(CH, v); } catch (_) { /* pazienza */ }
    document.body.dataset.vista = v;
    for (const [id, nome] of [["scheda-sessioni", "sessioni"], ["scheda-token", "token"]]) {
      const b = q(`#${id}`); const on = nome === v;
      b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1;
      if (on && fuoco) b.focus();
    }
    q("#vista-token").hidden = v !== "token";
    q("#vista-sessioni").hidden = v !== "sessioni";
    clearInterval(timer);
    if (v === "token") { carica(); timer = setInterval(() => { if (!document.hidden) carica(); }, 60000); }
  }
  q("#scheda-sessioni").addEventListener("click", () => mostra("sessioni"));
  q("#scheda-token").addEventListener("click", () => mostra("token"));
  q(".schede").addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowRight" || ev.key === "ArrowLeft") { ev.preventDefault(); mostra(vista === "token" ? "sessioni" : "token", true); }
  });

  let inCorso = false;
  async function carica() {
    if (inCorso) return;  // un solo calcolo alla volta (clic ripetuti, timer e ritorno in primo piano)
    inCorso = true;
    if (!dati) {
      q("#t-nota").textContent = "Carico i dati dei token…";
      document.querySelectorAll("#vista-token .t-num").forEach((x) => { if (!x.textContent) x.textContent = "…"; });
    }
    const ab = new AbortController(), tm = setTimeout(() => ab.abort(), 20000);
    try {
      const r = await fetch("/api/token", { cache: "no-store", signal: ab.signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      dati = await r.json();
      disegna();
    } catch (err) {
      q("#t-nota").textContent = err.name === "AbortError"
        ? "Il server della Regia non risponde da 20 s: riprovo tra un minuto."
        : `Server della Regia non raggiungibile (${err.message}): riprovo tra un minuto.`;
    } finally { clearTimeout(tm); inCorso = false; }
  }

  /* ---------- schede numeriche ---------- */
  function previsione(f) {
    const p = f && f.projection;
    if (!p) return "";
    if (p.status === "exceeds") return `A questo ritmo ti blocchi ${quando(p.exceeds_at)}, tra ${tra(p.exceeds_at)}.`;
    if (p.status === "ok") return `A questo ritmo finisci la finestra al ${pct(p.at_reset_pct)}.`;
    return `Previsione: dati insufficienti (${p.reason}).`;
  }
  function card(id, num, sotto, prev, alto, altoPrev = alto) {
    const c = q(id);
    c.querySelector(".t-num").textContent = num;
    c.querySelector(".t-num").classList.toggle("alto", !!alto);
    c.querySelector(".t-sotto").textContent = sotto;
    c.querySelector(".t-prev").textContent = prev;
    c.querySelector(".t-prev").classList.toggle("alto", !!altoPrev);
  }

  /* ---------- grafico a linee (un solo asse 0-100 %) ---------- */
  function grafico(box, serie, t0, t1, extra) {
    box.replaceChildren();
    const W = Math.max(260, box.clientWidth), H = 180, m = { l: 34, r: 12, t: 10, b: 24 };
    const x = (t) => m.l + ((t - t0) / (t1 - t0 || 1)) * (W - m.l - m.r);
    const y = (v) => m.t + (1 - v / 100) * (H - m.t - m.b);
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img" });
    svg.setAttribute("aria-label", extra.etichetta);
    for (const v of [0, 50, 100]) {
      svg.append(s("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: "g-griglia" }));
      const t = s("text", { x: m.l - 6, y: y(v) + 4, class: "g-asse", "text-anchor": "end" }); t.textContent = `${v}`; svg.append(t);
    }
    // tacche: mezzanotti (o ogni 12 h nel 48 h)
    const passo = extra.tacche || 86400;
    let tk = new Date(t0 * 1000); tk.setHours(passo === 43200 ? (tk.getHours() < 12 ? 12 : 24) : 24, 0, 0, 0);
    for (let t = tk.getTime() / 1000; t < t1; t += passo) {
      svg.append(s("line", { x1: x(t), x2: x(t), y1: m.t, y2: H - m.b, class: "g-griglia" }));
      const l = s("text", { x: x(t), y: H - 6, class: "g-asse", "text-anchor": "middle" });
      l.textContent = new Date(t * 1000).toLocaleString("it-IT", passo === 43200 ? { weekday: "short", hour: "2-digit" } : { weekday: "short" });
      svg.append(l);
    }
    for (const sr of serie) {
      const pts = sr.punti.filter((p) => p[1] != null);
      if (pts.length < 2) continue;
      // buco di letture (Mac spento, senza rete): la linea si interrompe, non inventa una diagonale
      const buco = sr.buco || Infinity;
      svg.append(s("path", { d: pts.map((p, i) => `${i && p[0] - pts[i - 1][0] <= buco ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(""), class: `g-linea ${sr.cls}` }));
    }
    // hover: linea verticale + valori della serie principale
    const croce = s("line", { y1: m.t, y2: H - m.b, class: "g-croce", visibility: "hidden" });
    svg.append(croce);
    const tip = e("div", "g-tip"); tip.hidden = true;
    const area = s("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent" });
    svg.append(area);
    const vicino = (pts, t) => pts.reduce((a, p) => (Math.abs(p[0] - t) < Math.abs(a[0] - t) ? p : a), pts[0]);
    area.addEventListener("pointermove", (ev) => {
      const r = svg.getBoundingClientRect();
      const t = t0 + ((ev.clientX - r.left) * (W / r.width) - m.l) / (W - m.l - m.r) * (t1 - t0);
      const righe = serie.filter((sr) => sr.tip && sr.punti.length).map((sr) => { const p = vicino(sr.punti, t); return [sr.nome, p]; });
      if (!righe.length) return;
      const tx = righe[0][1][0];
      croce.setAttribute("x1", x(tx)); croce.setAttribute("x2", x(tx)); croce.setAttribute("visibility", "visible");
      tip.replaceChildren(e("b", null, new Date(tx * 1000).toLocaleString("it-IT", { weekday: "short", hour: "2-digit", minute: "2-digit" })));
      righe.forEach(([n, p]) => tip.append(e("span", null, `${n}: ${pct(p[1])}`)));
      tip.hidden = false;
      const px = (x(tx) / W) * r.width;
      tip.style.left = `${Math.min(Math.max(px, 70), r.width - 70)}px`;
    });
    area.addEventListener("pointerleave", () => { croce.setAttribute("visibility", "hidden"); tip.hidden = true; });
    box.append(svg, tip);
  }

  function tabella(id, righe, vuoto) {
    const t = q(id); t.replaceChildren();
    if (!righe.length) { const tr = e("tr"); tr.append(e("td", "nota-vuota", vuoto)); t.append(tr); return; }
    const max = Math.max(...righe.map((r) => r[1]), 1);
    righe.forEach(([nome, v, alto]) => {
      const tr = e("tr");
      const barra = e("span", "t-barra"); barra.style.width = `${Math.max(2, (v / max) * 100)}%`;
      const c2 = e("td", "t-bar"); c2.append(barra);
      const tn = e("td", "t-nome", nome); tn.title = nome;
      tr.append(tn, c2, e("td", `t-val${alto ? " alto" : ""}`, milioni(v)));
      t.append(tr);
    });
  }

  function disegna() {
    const d = dati;
    if (!d) return;
    if (d.errore) { q("#t-nota").textContent = d.errore; return; }
    const c = d.cinque, w = d.sette, st = d.settimana;
    const p5 = c && c.projection, p7 = w && w.projection;
    card("#t-cinque", pct(c && c.pct), c && c.resets_at ? `si azzera ${quando(c.resets_at)}${c.stale ? " (lettura vecchia)" : ""}` : "", previsione(c), p5 && p5.status === "exceeds");
    /* allarme in testa alla scheda: il blocco delle 5 ore non deve sembrare un dettaglio */
    const al = q("#t-allarme"), blocco = [[p5, "5 ore"], [p7, "settimana"]].find(([p]) => p && p.status === "exceeds");
    al.hidden = !blocco;
    if (blocco) al.textContent = `Attenzione: a questo ritmo il limite ${blocco[1] === "5 ore" ? "delle 5 ore" : "della settimana"} ti blocca alle ${ore(blocco[0].exceeds_at)} (tra ${tra(blocco[0].exceeds_at)}): rallenta o ferma le sessioni che non servono.`;
    card("#t-sette", pct(w && w.pct), w && w.resets_at ? `si azzera ${quando(w.resets_at)}` : "", previsione(w), p7 && p7.status === "exceeds");
    if (st) {
      const scarto = Math.round((w.pct - st.ideale_pct));
      /* frasi riscritte: «avanti/indietro sul ritmo» non si capiva */
      card("#t-oggi", pct(st.oggi_pct), `della settimana usato oggi · tetto giornaliero ~${d.soglia_giorno} %${st.oggi_pct > d.soglia_giorno ? ": superato" : ""}`,
        `${scarto > 0 ? `Hai speso ${scarto} punti più del ritmo che arriva giusto a fine settimana.` : scarto < 0 ? `Sei ${-scarto} punti sotto il ritmo che arriva giusto a fine settimana.` : "Sei sul ritmo che arriva giusto a fine settimana."}${st.margine_giorno != null ? ` Da qui puoi usare ~${dec(st.margine_giorno)} % al giorno per i ${dec(st.giorni_rimasti)} giorni che restano.` : ""}`,
        st.oggi_pct > d.soglia_giorno, false);
    } else card("#t-oggi", "—", "finestra settimanale senza dati", "", false);

    const ora = Date.now() / 1000;
    const s48 = d.serie48 || [];
    grafico(q("#g48"), [
      { nome: "Settimana", cls: "g-sette", punti: s48.map((p) => [p[0], p[2]]), tip: true, buco: 3600 },
      { nome: "5 ore", cls: "g-cinque", punti: s48.map((p) => [p[0], p[1]]), tip: true, buco: 3600 },
    ], ora - 48 * 3600, ora, { etichetta: "Consumo delle ultime 48 ore, 5 ore e settimana", tacche: 43200 });
    if (st && w) {
      const fine = w.resets_at;
      const prev = p7 && p7.status !== "insufficient" ? [[ora, w.pct], [p7.status === "exceeds" ? p7.exceeds_at : fine, p7.status === "exceeds" ? 100 : p7.at_reset_pct]] : [];
      grafico(q("#gsett"), [
        { nome: "Ritmo costante", cls: "g-ideale", punti: [[st.inizio, 0], [fine, 100]] },
        { nome: "Previsione", cls: "g-prev", punti: prev },
        { nome: "Settimana", cls: "g-sette", punti: st.serie, tip: true, buco: 3 * 3600 },
      ], st.inizio, fine, { etichetta: "Consumo della settimana con ritmo costante e previsione" });
    } else q("#gsett").replaceChildren(e("p", "nota-vuota", "Nessuna finestra settimanale in corso."));

    const oggi = new Date().toISOString().slice(0, 10);
    tabella("#t-giorni", (d.giorni || []).slice().reverse().map((g) => [new Date(`${g.giorno}T12:00`).toLocaleDateString("it-IT", { weekday: "short", day: "numeric" }), g.pesati, g.giorno === oggi]), "Nessuna trascrizione negli ultimi 7 giorni.");
    tabella("#t-progetti", (d.progetti || []).map((p) => [p.nome, p.pesati]), "Nessun progetto.");
    tabella("#t-agenti", (d.agenti || []).map((a) => [a.nome, a.pesati]), "Nessun agente vivo.");
    const pp = d.per_pct;
    q("#t-nota").textContent = `Letture: ${d.letture.toLocaleString("it-IT")}, l'ultima alle ${(d.ultima || "").slice(11, 16)}. `
      + `Token pesati, cioè contati come i prezzi API (input 1, output 5, scrittura cache 1,25, lettura cache 0,1): una convenzione per confrontare, non la formula dei limiti. Solo le trascrizioni di questo Mac: cloud e altri PC non ci sono. `
      + (pp && pp.status === "ok" ? `In questa settimana 1 % ≈ ${milioni(pp.tokens_per_pct)} token pesati. ` : "")
      + `Calcoli di dont-waste-your-token. Agg. ${ore(ora)}.`;
  }

  let rid = null;
  addEventListener("resize", () => { clearTimeout(rid); rid = setTimeout(() => { if (vista === "token") disegna(); }, 150); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden && vista === "token") carica(); });
  mostra(vista);
})();
