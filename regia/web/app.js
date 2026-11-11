"use strict";
/* Regia — minimale. Legge /api/stato ogni 12 s e /api/messaggi ogni 2 s (ETag), manda richieste a /api/richiesta. Testo sempre via textContent. */

const OGNI_MS = 12000;
let etagMsg = null;
const MESSAGGI_MS = 2000; // prima 12 s + cache 5 s: sembrava che la risposta non arrivasse
const ASCOLTO_MAX_MIN = 12; // il SUP controlla la coda ogni 10 min (cron): oltre 12 min non è in ascolto
const INIZIO_LAVORI = "INIZIO LAVORI: fai fare /passaggio alle sessioni che ne hanno bisogno, allineati col cloud (/allinea), fammi il riepilogo della situazione, aggiorna l'app.";
const SUP = "SUPERAGENTE";
// barra in alto:
// true = 7d/5h come etichette distinte e più spazio; false = stile di prima, identico
const BARRA_DISTINTA = true;
const STATI_RICHIESTA = {
  nuova: "il SUP non l'ha ancora letta",
  letta: "letta dal SUP, non ancora presa",
  verde: "ordine dato all'agente",
  giallo: "in mano all'agente",
  grigio: "consegnata",
  conferma: "serve la tua conferma (in chat)",
};
const RITARDO_MIN = 2; // richiesta ancora «nuova» dopo 2 min → rosso: il SUP non l'ha presa
const minutiDa = (ora) => { const t = Date.parse(String(ora || "").replace(" ", "T")); return Number.isNaN(t) ? 0 : (Date.now() - t) / 60000; };
const inRitardo = (q) => q.stato === "nuova" && minutiDa(q.ora) >= RITARDO_MIN;
const DORMIENTE_MIN = 180; // ferma da più di 3 ore: in fondo e attenuata, qualunque ordine automatico
const dormiente = (s) => s.stato === "ferma" && (s.minuti ?? 0) >= DORMIENTE_MIN;
const PESO_STATO = { "in attesa": 0, ferma: 1, "al lavoro": 2, "non viva": 3, "in pausa": 4 };
/* in pausa: «bypassata da tutto … sempre messe in fondo», anche in ordine manuale */
const inPausa = (s) => s.stato === "in pausa";
const oraHM = (t) => (t || "").slice(11, 16);
const FERMA_RECENTE_MIN = 60; // «Ferme in cima» tiene sopra solo chi si è fermato da poco: le ferme da ore non coprono quelle al lavoro
const fermaRecente = (s) => s.stato === "in attesa" || (s.stato === "ferma" && (s.minuti ?? 1e9) < FERMA_RECENTE_MIN);

/* ---------- preferenze (localStorage può mancare: tutto in try/catch) ---------- */
const PREF_CHIAVE = "plancia.pref.v1";
let pref = { ordine: "recente", fermiInCima: true, manuale: [], aperte: {}, viste: {}, sospesoAperto: true, avvisi: false };
try { Object.assign(pref, JSON.parse(localStorage.getItem(PREF_CHIAVE) || "{}")); } catch (_) { /* senza memoria */ }
function salva() { try { localStorage.setItem(PREF_CHIAVE, JSON.stringify(pref)); } catch (_) { /* pazienza */ } }

const $ = (s, el = document) => el.querySelector(s);
const righeEl = $("#righe");
const tpl = $("#tpl-riga");
const righe = new Map(); // nome → elemento
let ultimo = null;
let mostrato = null; // ordine a schermo: cambia solo su comando

function el(tag, cls, testo) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (testo != null) e.textContent = testo;
  return e;
}
const pulisci = (t) => String(t || "").replace(/\*\*|`/g, "").replace(/^-\s+/, "");
function fa(minuti) {
  if (minuti == null) return "";
  if (minuti < 1) return "adesso";
  if (minuti < 60) return `${minuti} min fa`;
  const h = Math.floor(minuti / 60);
  return h < 48 ? `${h} h fa` : `${Math.floor(h / 24)} g fa`;
}
// markdown dei messaggi → testo semplice (niente HTML: resta textContent)
const testoPiano = (t) => String(t || "").replace(/\*\*|__|`/g, "").replace(/^#{1,6}\s+/gm, "").replace(/^\s*[-*]\s+/gm, "• ").replace(/\n{3,}/g, "\n\n");
const oraCorta = (s) => (s || "").slice(11, 16);

/* link nei testi:
   [parola](url) e URL nudi (anche 127.0.0.1:4322/… senza http) → <a> in scheda nuova. Solo http/https: niente javascript:, data:, file:. */
const FILE_EST = "png|jpe?g|gif|webp|svg|pdf|html?|md|txt|mp4|mov";
const RE_LINK = new RegExp(String.raw`\[([^\]\n]{1,200})\]\(\s*([^)\n]{1,2000}?)\s*\)|\b((?:https?:\/\/|(?:localhost|127\.0\.0\.1):\d{2,5})[^\s<>"'()\[\]]*)|((?:~|\/Users\/[^\/\s]+)\/[^\n<>"'()\[\]·]*?\.(?:${FILE_EST}))(?![\w/])`, "gi");
/* file locali (~/… o /Users/…): li serve il server Regia su /file. Host «localhost» apposta: Regia.app tiene dentro solo
   127.0.0.1, così il file si apre nel browser e la Regia resta al suo posto */
const fileLocale = (u) => /^(~|\/Users\/)/.test(u) && new RegExp(`\\.(${FILE_EST})$`, "i").test(u);
function urlSicuro(u) {
  if (fileLocale(u)) return `http://localhost:${location.port || 80}/file?p=${encodeURIComponent(u)}`;
  if (/^(localhost|127\.0\.0\.1):/i.test(u)) u = "http://" + u;
  try { const x = new URL(u); return x.protocol === "http:" || x.protocol === "https:" ? x.href : null; } catch (_) { return null; }
}
const senzaLink = (t) => String(t ?? "").replace(/\[([^\]\n]{1,200})\]\(\s*[^)\n]{1,2000}?\s*\)/g, "$1"); // riga chiusa: è un bottone, niente <a>
// nomi di sessione nel testo → link che apre e porta alla riga. Solo nomi di sessioni vive, in MAIUSCOLO e come parola intera; il SUP no (non è una riga).
function testoConNomi(fr, t) {
  const nomi = ultimo ? vista(ultimo).map((s) => s.nome).filter((n) => n.length >= 3) : [];
  if (!t || !nomi.length) { fr.append(document.createTextNode(t)); return; }
  const re = new RegExp(`(^|[^A-Z0-9_-])(${nomi.map((n) => n.replace(/[-]/g, "\\-")).join("|")})(?![A-Z0-9_-])`, "g");
  let da = 0;
  for (const m of t.matchAll(re)) {
    const i = m.index + m[1].length;
    fr.append(document.createTextNode(t.slice(da, i)));
    const a = el("a", "link nome-s", m[2]);
    a.href = "#"; a.title = `Vai alla sessione ${m[2]}`;
    a.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); apriScheda(m[2]); });
    fr.append(a);
    da = i + m[2].length;
  }
  fr.append(document.createTextNode(t.slice(da)));
}

function conLink(testo) {
  const t = String(testo ?? ""), fr = document.createDocumentFragment();
  let da = 0;
  for (const m of t.matchAll(RE_LINK)) {
    let grezzo = m[2] || m[3] || m[4], parola = m[1] || (m[4] ? m[4].split("/").pop() : undefined);
    let coda = "";
    if (!parola) { const p = grezzo.match(/[.,;:!?]+$/); if (p) { coda = p[0]; grezzo = grezzo.slice(0, -coda.length); } } // punto finale fuori dal link
    const href = urlSicuro(grezzo);
    if (!href) continue;
    testoConNomi(fr, t.slice(da, m.index));
    const a = el("a", "link", parola || grezzo);
    a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer"; a.title = href;
    a.addEventListener("click", (e) => e.stopPropagation()); // non apre/chiude la riga
    fr.append(a, document.createTextNode(coda));
    da = m.index + m[0].length;
  }
  testoConNomi(fr, t.slice(da));
  return fr;
}

/* ---------- dati per riga ---------- */
// il SUP non è una riga: ha il suo riquadro fisso «Al superagente»
const vista = (d) => d.sessioni.filter((s) => s.nome !== SUP).map((s) => ({ ...s }));
const supSessione = (d) => d.sessioni.find((s) => s.nome === SUP) || { nome: SUP, stato: "non viva" };

function ordina(lista) {
  const per = {
    // per ora esatta dell'ultima attività, fissa per le ferme: coi minuti trascorsi due ferme da 622 e 623 min
    // si scambiavano di posto a ogni giro e «Riordina» restava sempre acceso
    recente: (a, b) => (b.ultima ?? 0) - (a.ultima ?? 0),
    peso: (a, b) => (b.contesto_k ?? -1) - (a.contesto_k ?? -1),
    stato: (a, b) => PESO_STATO[a.stato] - PESO_STATO[b.stato],
    nome: (a, b) => a.nome.localeCompare(b.nome),
    manuale: (a, b) => {
      const i = (n) => { const k = pref.manuale.indexOf(n); return k < 0 ? 1e6 : k; };
      return i(a.nome) - i(b.nome) || a.nome.localeCompare(b.nome);
    },
  }[pref.ordine] || ((a, b) => a.nome.localeCompare(b.nome));
  const ferma = (s) => (pref.fermiInCima && s.nome !== SUP && fermaRecente(s) ? 0 : 1);
  const dorme = (s) => (pref.ordine !== "manuale" && dormiente(s) ? 1 : 0);
  const pausa = (s) => (s.nome !== SUP && inPausa(s) ? 1 : 0);
  return lista.sort((a, b) => pausa(a) - pausa(b) || dorme(a) - dorme(b) || ferma(a) - ferma(b) || per(a, b) || a.nome.localeCompare(b.nome));
}

/* perché l'ordine non è quello scelto: visibile, non solo nel title */
function scriviNotaOrdine(sessioni) {
  const parti = [];
  if (pref.fermiInCima && sessioni.some(fermaRecente)) parti.push("le sessioni ferme da meno di un'ora o in attesa di un permesso stanno in cima (spunta «Ferme in cima»)");
  if (pref.ordine !== "manuale" && sessioni.some(dormiente)) parti.push("quelle ferme da più di 3 ore stanno in fondo, attenuate");
  if (sessioni.some(inPausa)) parti.push("quelle in pausa stanno sempre in ultima posizione ed escono da sole quando scrivi loro o riprendono a lavorare");
  const p = $("#nota-ordine");
  p.hidden = !parti.length;
  p.textContent = parti.length ? `Ordine: ${parti.join("; ")}.` : "";
}

/* ---------- testata ---------- */
function disegnaTestata(d) {
  const c = d.consumo, cons = $("#consumo");
  cons.replaceChildren();
  cons.classList.toggle("distinta", BARRA_DISTINTA);
  if (c) {
    /* formato «7d 75 % gio 22.00 · 5h 6 % 18.30»; orari dai resets_at. Rosso: 7d sopra la soglia
       cumulativa di oggi (piano elastico), 5h dal 71 % */
    const GG = ["dom", "lun", "mar", "mer", "gio", "ven", "sab"], d2 = (n) => String(n).padStart(2, "0");
    const quando = (rip, giorno) => {
      const t = new Date(rip * 1000), h = `${d2(t.getHours())}.${d2(t.getMinutes())}`;
      return giorno ? `${GG[t.getDay()]} ${h}` : h;
    };
    const pezzo = (etichetta, pct, rip, giorno, alto, tit) => {
      const b = el("span", alto ? "alto" : "");
      b.append(el("span", "etic", etichetta), document.createTextNode(" "), el("b", null, pct == null ? "—" : `${pct} %`));
      if (rip) b.append(document.createTextNode(` ${quando(rip, giorno)}`));
      b.title = tit;
      return b;
    };
    const s7 = c.soglia_7d, p7 = c.settimana_7d, p5 = c.sessione_5h;
    cons.append(
      pezzo("7d", p7, c.ripristino_7d, true, p7 != null && s7 != null && p7 > s7,
        `Settimana${c.ripristino_7d ? `: si azzera ${quando(c.ripristino_7d, true)}` : ""}${s7 != null ? ` · soglia di oggi ${s7} %${p7 > s7 ? ": superata" : ""}` : ""}`),
      el("span", "sep", "·"),
      pezzo("5h", p5, c.ripristino_5h, false, p5 != null && p5 >= 71,
        `Sessione di 5 ore${c.ripristino_5h ? `: si azzera alle ${quando(c.ripristino_5h, false)}` : ""}`));
  }
  const pa = $("#avviso-pausa"), pz = d.pausa;
  pa.hidden = !pz;
  if (pz) pa.textContent = `SUP in riavvio (${pz.motivo}) dalle ${oraCorta(pz.ora)}: quello che scrivi resta qui e parte da solo quando riparte.`;
  // sulla casella
  const cp = $("#sup-riavvio");
  cp.hidden = !pz;
  if (pz) cp.textContent = `SUP in riavvio dalle ${oraCorta(pz.ora)}: i messaggi che mandi ora restano qui («aspetta il SUP») e partono da soli quando riparte.`;
  const av = $("#avviso-permesso"), p = d.sup.aspetta_permesso;
  const supRiga = supSessione(d);
  if (p) { av.textContent = `Il SUP aspetta un permesso nel terminale: ${p.cosa} (dalle ${oraCorta(p.ora)}) `; av.append(bottoneTerminale(SUP)); av.hidden = false; }
  else if (supRiga && supRiga.stato === "in attesa") { av.textContent = "Il SUP forse aspetta un permesso nel terminale (fermo su un comando). "; av.append(bottoneTerminale(SUP)); av.hidden = false; }
  else av.hidden = true;
  const err = $("#avviso-errore");
  err.hidden = !d.errore; err.textContent = d.errore || "";

  const lista = $("#sospeso-lista"); lista.replaceChildren();
  const voci = d.insospeso;
  /* chi aspetta te sta sempre qui, con la sua domanda; niente doppioni con le voci del SUP */
  const giaDette = new Set((Array.isArray(voci) ? voci : []).map((v) => v.sessione).filter(Boolean));
  const attese = vista(d).filter((s) => s.stato === "in attesa" && !giaDette.has(s.nome));
  attese.forEach((s) => {
    const li = el("li", "attesa");
    li.append(el("strong", "", `${s.nome} forse aspetta un tuo permesso`));
    const q = senzaLink(primaRiga(s.ultimo_testo)).slice(0, 160);
    if (q) li.append(document.createTextNode(`: ${q}`));
    li.title = "Ferma su un comando da più di 2 minuti: di solito è una domanda di permesso nel suo terminale.";
    lista.append(li);
  });
  if (!Array.isArray(voci)) { if (!attese.length) lista.append(el("li", "nota-vuota", "Riquadro non ancora creato: il SUP lo riempie con sup.py sospeso aggiungi.")); }
  else if (!voci.length) { if (!attese.length) lista.append(el("li", "nota-vuota", "Niente in sospeso.")); }
  else {
    /* voci di una sessione in pausa: in fondo e spente, col loro numero (lo stesso di sup.py sospeso) */
    const ferme = new Set(vista(d).filter(inPausa).map((s) => s.nome));
    const righe = voci.map((v, i) => {
      const li = el("li"); li.value = attese.length + i + 1; li.append(conLink(v.testo));
      const ses = (v.sessione || "").toUpperCase();
      if (v.sessione) li.append(el("span", "di", ferme.has(ses) ? `${v.sessione} · in pausa` : v.sessione));
      if (ferme.has(ses)) li.classList.add("in-pausa");
      return li;
    });
    lista.append(...righe.filter((li) => !li.classList.contains("in-pausa")), ...righe.filter((li) => li.classList.contains("in-pausa")));
  }
  $("#sospeso-conta").textContent = (Array.isArray(voci) ? voci.length : 0) + attese.length;
  $("#sospeso").classList.toggle("chiuso", !pref.sospesoAperto);
  $("#sospeso-apri").setAttribute("aria-expanded", String(pref.sospesoAperto));
}

/* ---------- righe ---------- */
function nuovaRiga(nome) {
  const r = tpl.content.firstElementChild.cloneNode(true);
  r.dataset.nome = nome;
  $(".nome", r).textContent = nome;
  $(".apri", r).addEventListener("click", () => {
    pref.aperte[nome] = !aperta(nome); segnaViste(nome); salva(); disegna();
    if (pref.aperte[nome]) caricaChat(nome).then((ok) => { if (ok) disegna(); });
    if (pref.aperte[nome]) $("textarea", r).focus({ preventScroll: true });
  });
  $(".col-fatti", r).addEventListener("click", () => { segnaViste(nome); salva(); disegna(); });
  const form = $(".modulo", r), ta = $("textarea", r);
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const testo = ta.value.trim();
    if (!testo || ta.readOnly) return;
    ta.readOnly = true; form.setAttribute("aria-busy", "true");
    const ok = await manda(r.dataset.dest || nome, testo, r);
    ta.readOnly = false; form.removeAttribute("aria-busy");
    if (ok) ta.value = "";
  });
  // spostare: trascinando la maniglia, o con frecce sulla maniglia
  const man = $(".maniglia", r);
  man.setAttribute("tabindex", "0"); man.setAttribute("role", "button");
  man.setAttribute("aria-label", `Sposta ${nome}: frecce su e giù`);
  man.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    r.classList.add("trascina");
    let mosso = false;
    const muovi = (ev) => {
      mosso = true;
      if (ev.clientY < 60) window.scrollBy(0, -24); else if (ev.clientY > innerHeight - 60) window.scrollBy(0, 24);
      for (const x of righeEl.children) {
        if (x === r) continue;
        const b = x.getBoundingClientRect();
        if (ev.clientY < b.top + b.height / 2) { if (r.nextElementSibling !== x) righeEl.insertBefore(r, x); return; }
      }
      if (righeEl.lastElementChild !== r) righeEl.append(r);
    };
    const fine = () => {
      // su window e non sulla maniglia: spostare la riga nel DOM fa perdere la cattura del puntatore
      window.removeEventListener("pointermove", muovi);
      window.removeEventListener("pointerup", fine);
      window.removeEventListener("pointercancel", fine);
      r.classList.remove("trascina");
      if (mosso) passaAManuale();
    };
    window.addEventListener("pointermove", muovi);
    window.addEventListener("pointerup", fine);
    window.addEventListener("pointercancel", fine);
  });
  man.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
    e.preventDefault();
    const vic = e.key === "ArrowUp" ? r.previousElementSibling : r.nextElementSibling;
    if (!vic) return;
    righeEl.insertBefore(r, e.key === "ArrowUp" ? vic : vic.nextElementSibling);
    passaAManuale(); man.focus();
  });
  righe.set(nome, r);
  return r;
}

const aperta = (nome) => !!pref.aperte[nome];
const primaRiga = (t) => testoPiano(t).split("\n").map((x) => x.trim()).find(Boolean) || "";

function riordina() { mostrato = null; disegna(); const b = $("#riordina"); b.blur(); }

function passaAManuale() {
  pref.manuale = [...righeEl.children].map((x) => x.dataset.nome);
  mostrato = pref.manuale.slice();
  pref.ordine = "manuale"; $("#ordine").value = "manuale";
  salva();
}

function segnaViste(nome) {
  const s = ultimo && (nome === SUP ? ultimo.sup : vista(ultimo).find((x) => x.nome === nome));
  const ult = s && s.risposte && s.risposte.length ? s.risposte[s.risposte.length - 1].ora : null;
  if (ult) pref.viste[nome] = ult;
}

function sezione(titolo, figli, cls) {
  const sec = el("section", `blocco ${cls || ""}`);
  sec.append(el("h3", null, titolo), ...figli);
  return sec;
}
function lista(voci, ordinata) {
  const l = el(ordinata ? "ol" : "ul");
  voci.forEach((v) => { const li = el("li"); li.append(conLink(pulisci(v))); l.append(li); });
  return l;
}

function riempi(r, s) {
  const ap = aperta(s.nome);
  r.dataset.dest = s.destinatario || s.nome;
  r.classList.toggle("aperta", ap);
  r.dataset.stato = s.stato;
  r.classList.toggle("dormiente", dormiente(s));
  $(".apri", r).setAttribute("aria-expanded", String(ap));
  $(".dettaglio", r).hidden = !ap;

  // riga chiusa: stato · da quando · contesto
  scriviMeta($(".meta", r), s);
  const k = s.contesto_k;
  const cx = s.contesto || {};
  const comp = $(".compito", r); // con le 2 righe in testa non si ripete: resta solo se manca il contesto
  comp.textContent = cx.occupa ? "" : pulisci(s.compito) || "Compito non scritto.";
  comp.hidden = !!cx.occupa;
  /* prima riga = lavoro ATTUALE (frase che l'agente riscrive a ogni cambio di compito); senza, lo scopo dall'agenda */
  const occ = $(".c-occupa", r), ad = s.adesso;
  $(".c-occupa-etichetta", r).textContent = ad ? "Adesso" : "Di cosa si occupa";
  if (ad) {
    const m = ad.minuti, eta = m < 60 ? `${m} min` : m < 1440 ? `${Math.floor(m / 60)} h` : `${Math.floor(m / 1440)} g`;
    occ.replaceChildren(document.createTextNode(ad.testo), el("span", "vecchia", ` · da ${eta}${m >= 1440 ? ", vecchia" : ""}`));
  } else {
    occ.replaceChildren(document.createTextNode(cx.occupa || "non scritto nell'agenda"));
    if (cx.vecchia) occ.append(" ", el("span", "vecchia", "(dal registro, vecchio)"));
  }
  const pun = $(".c-punto", r); pun.replaceChildren();
  if (cx.ora) pun.append(el("time", null, cx.ora));
  pun.append(document.createTextNode(cx.punto || "nessuna voce recente nell'agenda"));
  $(".peso", r).textContent = k == null ? "" : `Contesto ${k}K${s.livello === "riavvio" ? ": da riavviare" : s.livello === "passaggio" ? ": tempo di passaggio" : ""}`;
  const pas = $(".passaggio", r);
  pas.hidden = !s.passaggio;
  if (s.passaggio) pas.textContent = `Nota di passaggio da leggere (${s.passaggio.quando})`;

  // colonna 2: ultime cose fatte, richieste dell'agente, risposte del SUP
  const filo = $(".filo", r); const blocchi = [];
  const risp = s.risposte || [];
  const vista_ = pref.viste[s.nome] || "";
  const nonLette = risp.filter((x) => x.ora > vista_).length;
  $(".pallino-nuovo", r).hidden = !nonLette;
  const att = $(".attivita", r); att.replaceChildren();
  // una risposta del SUP non letta restava in testa finché l'utente non apriva la riga. Ora vince la cosa più recente
  // tra l'ultima risposta del SUP e l'ultimo lavoro della sessione (minuti = ultima scrittura della trascrizione).
  const ur = risp[risp.length - 1];
  const tSup = ur ? Date.parse(String(ur.ora).replace(" ", "T")) || 0 : 0;
  const tAg = s.minuti != null && s.ultimo_testo ? Date.now() - s.minuti * 60000 : 0;
  if (ur && tSup >= tAg) {
    if (nonLette) att.append(el("span", "nuovo", `SUP: ${senzaLink(ur.testo)}`));
    else att.textContent = senzaLink(`SUP: ${ur.testo}`);
  } else att.textContent = senzaLink(primaRiga(s.ultimo_testo));
  att.title = att.textContent;
  const ch = chatDi[s.nome];
  if (ap && ch) blocchi.push(sezione("Chat", [disegnaChat(s.nome, ch.voci)], "chat-blocco"));
  else if (risp.length) {
    const ul = el("ul", "risposte");
    risp.slice(-6).reverse().forEach((x) => { // più recente in cima
      const li = el("li", x.ora > vista_ ? "non-letta" : "");
      li.append(el("time", null, oraCorta(x.ora)), conLink(x.testo));
      ul.append(li);
    });
    blocchi.push(sezione(`Risposte del SUP${nonLette ? ` · ${nonLette} ${nonLette === 1 ? "nuova" : "nuove"}` : ""}`, [ul]));
  }
  if (s.ultimo_testo && !(ap && ch)) blocchi.push(sezione("Ultimo messaggio dell'agente", [(() => { const p = el("p", "ultimo"); p.append(conLink(testoPiano(s.ultimo_testo))); return p; })()]));
  if (s.agenda && s.agenda.prossimi.length) blocchi.push(sezione("Prossimi passi", [lista(s.agenda.prossimi.slice(0, 4), true)]));
  if (s.agenda && s.agenda.cronologia.length) blocchi.push(sezione("Ultime voci dell'agenda", [lista(s.agenda.cronologia.slice(0, 3))]));
  if (!blocchi.length) blocchi.push(el("p", "nota-vuota", "Niente da mostrare."));
  filo.replaceChildren(...blocchi);

  // colonna 3: ultime 4 richieste, la più recente in alto
  const rich = (s.richieste || []).slice(-4).reverse();
  const ult = $(".ultima", r); ult.replaceChildren(); ult.className = "c3 ultima";
  if (rich.length) {
    ult.classList.add(`st-${rich[0].stato}`);
    ult.classList.toggle("ritardo", inRitardo(rich[0]));
    ult.append(el("span", "r-pallino"), el("span", null, senzaLink(rich[0].testo)));
    ult.title = `${STATI_RICHIESTA[rich[0].stato] || rich[0].stato}: ${rich[0].testo}`;
  }
  scriviRichieste($(".richieste", r), ap && ch ? rich.slice(0, 1) : rich); // con la chat aperta i messaggi stanno lì: qui solo l'ultimo
}

/* ---------- chat per sessione: tutto letto da file, 0 token; chat.py sul server ---------- */
const chatDi = {}; // nome → { etag, voci }
const chatAperte = new Set(); // voci lunghe aperte con «apri tutto» (chiave: ora + inizio testo)
const chatRidotte = new Set(); // voci del SUP: aperte di default, «riduci» le accorcia
const CHAT_MOSTRA = 15, CHAT_TAGLIO = 400, CHAT_MOSTRA_SUP = 30;
/* filo unico del SUP: nella chat del SUP anche ciò che scrivi nelle chat delle sessioni,
   le risposte del SUP lì e i messaggi degli agenti al SUP; compatti su 3 righe con «apri», nome sessione cliccabile */
let filoSup = { etag: null, voci: [] };
const ALTRI = new Set(["tu-s", "sup-s", "agente"]);
const ETICHETTE = { "tu-s": () => "Tu → ", "sup-s": () => "SUP → ", agente: () => "", tu: () => "Tu (dalla Regia)", sup: () => "SUP", terminale: () => "Tu (nel terminale)",
  sessione: (v) => v.passi > 1 ? `Sessione (ultimo di ${v.passi} aggiornamenti)` : "Sessione", in: (v) => `${v.da} → sessione`, out: (v) => `Sessione → ${v.a}` };

function disegnaChat(nome, voci) {
  const ul = el("ul", "chat");
  ul.setAttribute("aria-label", `Chat di ${nome}, la più recente in alto`);
  voci.slice(-(nome === SUP ? CHAT_MOSTRA_SUP : CHAT_MOSTRA)).reverse().forEach((v) => { // più recente in cima
    if (ALTRI.has(v.chi)) return ul.append(voceAltra(v));
    const li = el("li", `v v-${v.chi}`);
    const testa = el("div", "v-testa");
    testa.append(el("span", "v-chi", (ETICHETTE[v.chi] || (() => v.chi))(v)), el("time", null, oraCorta(v.ora)));
    if (v.chi === "tu" && v.id) testa.append(chipStato(v)); // stato dopo l'ora, un po' a destra
    const chiave = `${v.ora}|${(v.testo || "").slice(0, 40)}`;
    const apertaDiBase = v.chi === "sup"; // messaggi del SUP completi di default
    const lungo = (v.testo || "").length > CHAT_TAGLIO, aperto = apertaDiBase ? !chatRidotte.has(chiave) : chatAperte.has(chiave);
    const p = el("p", "v-testo");
    p.append(conLink(testoPiano(lungo && !aperto ? v.testo.slice(0, CHAT_TAGLIO).trimEnd() + "…" : v.testo)));
    li.append(testa, p);
    if (lungo) {
      const b = el("button", "v-tutto", aperto ? "riduci" : "apri tutto");
      b.type = "button";
      const insieme = apertaDiBase ? chatRidotte : chatAperte, dentro = insieme.has(chiave);
      b.addEventListener("click", (e) => { e.stopPropagation(); dentro ? insieme.delete(chiave) : insieme.add(chiave); disegna(); });
      li.append(b);
    }
    ul.append(li);
  });
  if (!voci.length) ul.append(el("li", "nota-vuota", "Ancora niente in questa chat."));
  return ul;
}

/* voce di un altro filo dentro la chat del SUP: stile diverso, chiusa su 3 righe, «apri» solo se il testo è più lungo */
function voceAltra(v) {
  const nome = v.chi === "agente" ? v.da : v.sessione;
  const li = el("li", `v v-altro v-${v.chi}`);
  const testa = el("div", "v-testa"), chi = el("span", "v-chi", ETICHETTE[v.chi](v));
  const b = el("button", "v-sessione", nome || "?");
  b.type = "button"; b.dataset.nome = nome || ""; b.title = `Apri la chat di ${nome}`;
  chi.append(b);
  if (v.chi === "agente") chi.append(document.createTextNode(" → SUP"));
  testa.append(chi, el("time", null, oraCorta(v.ora)));
  if (v.chi === "tu-s" && v.id) testa.append(chipStato(v));
  const chiave = `${v.ora}|${v.chi}|${(v.testo || "").slice(0, 40)}`, aperto = chatAperte.has(chiave);
  const p = el("p", `v-testo${aperto ? "" : " v-corto"}`);
  // il nome è già nell'intestazione: tolto se il testo comincia con «NOME:» / «NOME ·»
  const testo = nome ? String(v.testo || "").replace(new RegExp(`^${nome}\\s*[:·]\\s*`), "") : String(v.testo || "");
  p.append(conLink(testoPiano(testo)));
  li.append(testa, p);
  const righe = (v.testo || "").split("\n").length;
  if (righe > 3 || (v.testo || "").length > 180) {
    const t = el("button", "v-tutto", aperto ? "riduci" : "apri");
    t.type = "button";
    t.addEventListener("click", (e) => { e.stopPropagation(); aperto ? chatAperte.delete(chiave) : chatAperte.add(chiave); disegna(); });
    li.append(t);
  }
  return li;
}
document.addEventListener("click", (e) => {
  const b = e.target.closest(".v-sessione");
  if (!b || !b.dataset.nome) return;
  e.stopPropagation();
  apriScheda(b.dataset.nome);
});
async function caricaFiloSup() {
  try {
    const r = await fetch("/api/filo-sup", { headers: filoSup.etag ? { "If-None-Match": filoSup.etag } : {} });
    if (r.status === 304 || !r.ok) return false;
    filoSup = { etag: r.headers.get("ETag"), voci: (await r.json()).voci || [] };
    return true;
  } catch (_) { return false; }
}

async function caricaChat(nome) {
  const c = chatDi[nome];
  try {
    const r = await fetch(`/api/chat?s=${encodeURIComponent(nome)}`, { headers: c && c.etag ? { "If-None-Match": c.etag } : {} });
    if (r.status === 304 || !r.ok) return false;
    chatDi[nome] = { etag: r.headers.get("ETag"), voci: (await r.json()).voci || [] };
    return true;
  } catch (_) { return false; }
}

async function aggiornaChat() { // solo le sessioni aperte, solo a pagina visibile
  if (!ultimo || document.hidden) return;
  const nomi = vista(ultimo).map((s) => s.nome).filter(aperta);
  const cambiate = await Promise.all(nomi.map(caricaChat));
  if (cambiate.some(Boolean)) disegna();
}

function scriviMeta(meta, s) {
  meta.replaceChildren();
  meta.append(el("span", "st", s.stato === "in attesa" ? "forse aspetta un permesso" : inPausa(s) && s.pausa ? `in pausa dalle ${oraHM(s.pausa.ora)}` : s.stato));
  if (s.minuti != null && !inPausa(s)) meta.append(document.createTextNode(` · ${fa(s.minuti)}`)); // in pausa: conta da quando, non l'ultima attività
  const k = s.contesto_k;
  if (k != null) {
    meta.append(document.createTextNode(" · "));
    meta.append(el("span", s.livello === "riavvio" ? "alto" : "", `${k}K${s.livello === "riavvio" ? " riavvio" : s.livello === "passaggio" ? " passaggio" : ""}`));
  }
  meta.title = s.stato === "in attesa" ? "Fermo su un comando da più di 2 minuti: forse aspetta un permesso."
    : inPausa(s) ? `In pausa${s.pausa && s.pausa.motivo ? ` (${s.pausa.motivo})` : ""}: fuori da avvisi e conteggi. Esce da sola quando le scrivi o riprende a lavorare.` : "";
}

/* stato UNICO di un messaggio.
   Sequenza: inviato → letto dal SUP → girato a X → in mano a X → risposto → concluso (+ serve conferma, ritardo).
   «inviato» e «arrivato» erano la stessa cosa (la Regia scrive nella coda, che è la casella del SUP): accorpati. */
const fatta = (q) => q.stato === "grigio" || (q.storia || []).some((x) => x.stato === "risposta");
function statoUnico(q) {
  const st = q.storia || [];
  const ultimoDi = (stato) => [...st].reverse().find((x) => x.stato === stato);
  const a = q.a || (ultimoDi("verde") || {}).a;
  if (q.stato === "grigio") return { nome: "concluso", cls: "s-concluso", ora: q.ora_stato, spiega: STATI_RICHIESTA.grigio };
  const r = ultimoDi("risposta");
  if (r) return { nome: "risposto", cls: "s-risposto", ora: r.ora, spiega: "il SUP ha risposto (in chat)" };
  if (q.modificata && (q.mod_vista || "") < q.modificata && !["nuova", "attesa"].includes(q.stato))
    return { nome: "modificato · aspetta il SUP", cls: "s-corso", ora: q.modificata, spiega: "hai cambiato la richiesta: il SUP la rivede al prossimo giro" };
  if (q.stato === "conferma") return { nome: "serve la tua conferma", cls: "s-allarme", ora: q.ora_stato, spiega: STATI_RICHIESTA.conferma };
  if (q.stato === "giallo") return { nome: a ? `in mano a ${a}` : "in mano all'agente", cls: "s-corso", ora: q.ora_stato, spiega: STATI_RICHIESTA.giallo };
  if (q.stato === "verde") return { nome: a ? `girato a ${a}` : "preso dal SUP", cls: "s-corso", ora: q.ora_stato, spiega: STATI_RICHIESTA.verde };
  if (q.stato === "attesa") return { nome: "aspetta il SUP", cls: "s-corso", ora: q.ora, spiega: "SUP in riavvio: il messaggio parte da solo quando riparte" };
  if (q.stato === "letta") return { nome: "letto dal SUP", cls: "s-corso", ora: (ultimoDi("letta") || {}).ora || q.ora_stato, spiega: STATI_RICHIESTA.letta };
  if (inRitardo(q)) return { nome: `non letto da ${Math.floor(minutiDa(q.ora))} min`, cls: "s-allarme", ora: q.ora, spiega: "il SUP non l'ha ancora presa" };
  return { nome: "inviato", cls: "s-inviato", ora: q.ora, spiega: STATI_RICHIESTA.nuova };
}
function chipStato(q) {
  const s = statoUnico(q);
  const c = el("span", `stato-unico ${s.cls}`, s.nome);
  c.title = s.spiega + (s.ora ? ` · ${oraCorta(s.ora)}` : "");
  return c;
}

function scriviRichieste(ul, rich) { // dettaglio delle sessioni: stesso stato unico, testo intero
  ul.replaceChildren();
  rich.forEach((q) => {
    const li = el("li", `richiesta st-${q.stato}${inRitardo(q) ? " ritardo" : ""}`);
    const testa = el("div", "r-testa");
    testa.append(el("span", "r-pallino"), chipStato(q), el("time", null, oraCorta(q.ora)));
    const pt = el("p", "r-testo"); pt.append(conLink(q.testo));
    li.append(testa, pt);
    if (q.nota) { const pn = el("p", "r-nota"); pn.append(conLink(q.nota)); li.append(pn); }
    ul.append(li);
  });
}

/* lista sotto la casella del SUP: una riga per richiesta [stato · testo troncato con … · ora],
   clic sul testo = aperto/chiuso; aperte in cima finché non hanno risposta, poi le concluse; la lista scorre. */
const righeSupAperte = new Set();
/* FASE 2: matita sulle richieste ancora senza risposta →
   la riga diventa una casella (Invio salva, Maiusc+Invio a capo, Esc annulla). Mentre si modifica la lista non si
   ridisegna (la bozza non si perde). Dopo la risposta niente modifica: «manda di nuovo» riempie la casella in alto. */
let modificaSup = null; // { id, bozza, errore, invio }
let richiesteSup = [];
function scriviRigheSup(ul, rich, forza = false) {
  richiesteSup = rich;
  if (!forza && modificaSup && ul.querySelector(".rs-modifica")) return; // casella aperta: niente ridisegno dal giro dei 2 s
  const ordine = (a, b) => (a.ora < b.ora ? 1 : a.ora > b.ora ? -1 : 0); // più recente in alto
  const elenco = [...rich.filter((q) => !fatta(q)).sort(ordine), ...rich.filter(fatta).sort(ordine)];
  ul.replaceChildren();
  elenco.forEach((q) => ul.append(rigaSup(ul, q)));
}
const ridisegnaSup = (ul) => scriviRigheSup(ul, richiesteSup, true);
function rigaSup(ul, q) {
  const aperta = righeSupAperte.has(q.id), finita = fatta(q);
  const li = el("li", `riga-sup${finita ? " conclusa" : ""}${aperta ? " aperta" : ""}`);
  if (modificaSup && modificaSup.id === q.id) return casellaModifica(ul, q, li);
  const b = el("button", "rs-testo");
  b.type = "button";
  b.setAttribute("aria-expanded", String(aperta));
  b.title = aperta ? "Clic per richiudere" : "Clic per leggere tutto";
  b.append(document.createTextNode(testoPiano(q.testo || "")));
  b.addEventListener("click", () => { aperta ? righeSupAperte.delete(q.id) : righeSupAperte.add(q.id); ridisegnaSup(ul); });
  const matita = el("button", "rs-matita", "✎");
  matita.type = "button";
  if (finita) { matita.hidden = true; } else {
    matita.title = "Modifica la richiesta"; matita.setAttribute("aria-label", "Modifica la richiesta");
    matita.addEventListener("click", () => { modificaSup = { id: q.id, bozza: q.testo || "" }; ridisegnaSup(ul); });
  }
  li.append(chipStato(q), b, matita, el("time", null, oraCorta(q.ora)));
  if (aperta) {
    const extra = el("div", "rs-extra");
    if (q.nota) { const pn = el("p", "r-nota"); pn.append(conLink(q.nota)); extra.append(pn); }
    const prima = q.prima || [];
    if (prima.length) {
      const pp = el("p", "rs-prima");
      pp.append(el("span", "rs-etic", `Versione precedente${prima.length > 1 ? ` (modificata ${prima.length} volte)` : ""}${q.modificata ? ` · modificata alle ${oraCorta(q.modificata)}` : ""}: `),
        document.createTextNode(testoPiano(prima[prima.length - 1])));
      extra.append(pp);
    }
    if (finita) {
      const di = el("button", "rs-dinuovo", "manda di nuovo");
      di.type = "button";
      di.title = "Il SUP ha già risposto: la richiesta non si modifica più, si rimanda come nuova (finisce nella casella in alto)";
      di.addEventListener("click", () => { const t = $("#al-sup-testo"); t.value = q.testo || ""; t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
      extra.append(di);
    }
    if (extra.childNodes.length) li.append(extra);
  }
  return li;
}
function casellaModifica(ul, q, li) {
  li.classList.add("in-modifica");
  const ta = el("textarea", "rs-modifica");
  ta.value = modificaSup.bozza; ta.maxLength = 4000; ta.rows = 3;
  ta.setAttribute("aria-label", "Modifica la richiesta");
  ta.addEventListener("input", () => { modificaSup.bozza = ta.value; });
  const chiudi = () => { modificaSup = null; ridisegnaSup(ul); };
  const salva = async () => {
    const testo = ta.value.trim();
    if (!testo || modificaSup.invio) return;
    if (testo === (q.testo || "").trim()) return chiudi();
    modificaSup.invio = true; ta.setAttribute("aria-busy", "true");
    try {
      const r = await fetch("/api/modifica", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: q.id, testo }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.errore || `HTTP ${r.status}`);
      ta.value = ""; modificaSup = null;
      etagMsg = null; await aggiornaMessaggi(); ridisegnaSup(ul);
    } catch (e) {
      modificaSup.invio = false; ta.removeAttribute("aria-busy");
      aiuto.textContent = e instanceof TypeError ? "Non salvata: il server della Regia non risponde. Il testo resta qui." : `Non salvata: ${e.message}`;
      aiuto.classList.add("errore");
    }
  };
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); ta.value = ""; chiudi(); }
    else if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); salva(); }
  });
  const stato = statoUnico(q);
  const aiuto = el("p", "rs-aiuto", stato.nome === "inviato" || stato.nome === "aspetta il SUP"
    ? "Il SUP non l'ha ancora letta: cambia e basta. Invio salva · Maiusc+Invio a capo · Esc annulla"
    : "Il SUP l'ha già letta: gli arriva come MODIFICA e la rivede (se l'ha girata, la gira lui all'agente). Invio salva · Esc annulla");
  li.append(chipStato(q), ta, aiuto);
  setTimeout(() => { if (document.contains(ta)) { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); } }, 0);
  return li;
}

/* ---------- riquadro fisso «Al superagente»: si riempiono solo i dati, la casella non viene mai toccata ---------- */
function disegnaSup(d) {
  const s = supSessione(d);
  $(".al-sup-testa").dataset.stato = s.stato;
  scriviMeta($("#al-sup-meta"), s);
  const asc = $("#sup-ascolto"), batt = d.ascolto && d.ascolto.ora;
  if (!batt) { asc.dataset.ok = "?"; asc.textContent = "Ascolto del SUP: ancora nessun controllo della coda registrato."; }
  else {
    const m = Math.floor(minutiDa(batt));
    asc.dataset.ok = m <= ASCOLTO_MAX_MIN ? "si" : "no";
    asc.textContent = m <= ASCOLTO_MAX_MIN ? `SUP in ascolto · ultimo controllo dei messaggi alle ${oraCorta(batt)}`
      : `SUP non in ascolto da ${fa(m)}: i messaggi restano in coda. Scrivigli in chat per svegliarlo.`;
  }
  // chat del SUP nello stesso stile delle altre → stessa disegnaChat:
  // i tuoi messaggi (stato unico nell'intestazione) e le risposte del SUP, la più recente in alto
  const tutte = d.sup.richieste || [], risp = d.sup.risposte || [];
  const vista_ = pref.viste[SUP] || "";
  const nonLette = risp.filter((x) => x.ora > vista_).length;
  $("#al-sup-risp-titolo").textContent = `Chat col SUP${nonLette ? ` · ${nonLette} ${nonLette === 1 ? "risposta nuova" : "risposte nuove"}` : ""}`;
  const voci = [...tutte.map((q) => ({ ...q, chi: "tu" })), ...risp.map((x) => ({ ora: x.ora, chi: "sup", testo: x.testo })), ...filoSup.voci]
    .sort((a, b) => (a.ora < b.ora ? -1 : a.ora > b.ora ? 1 : 0));
  $("#al-sup-chat").replaceChildren(disegnaChat(SUP, voci));
  scriviRigheSup($("#ultimo-invio"), tutte);
}

// nome -> id della sessione: una sessione che riparte (nome nuovo o id cambiato) va in cima da sola
let visti = null;
const idSessione = (s) => s.session_id || String(s.avviata || "");

function disegna() {
  if (!ultimo) return;
  const sessioni = vista(ultimo);
  disegnaTestata(ultimo);
  disegnaSup(ultimo);
  const ripartite = visti ? new Set(sessioni.filter((s) => visti.get(s.nome) !== idSessione(s)).map((s) => s.nome)) : new Set();
  visti = new Map(sessioni.map((s) => [s.nome, idSessione(s)]));
  const calcolato = ordina(sessioni);
  let ordinate = calcolato;
  if (mostrato) { // ordine stabile: quelle già a schermo restano dove sono; chi riparte in cima, le altre nuove in fondo
    const per = new Map(calcolato.map((s) => [s.nome, s]));
    const tenute = mostrato.filter((n) => per.has(n) && !ripartite.has(n)).map((n) => per.get(n));
    ordinate = [...calcolato.filter((s) => ripartite.has(s.nome)), ...tenute,
      ...calcolato.filter((s) => !mostrato.includes(s.nome) && !ripartite.has(s.nome))];
  }
  mostrato = ordinate.map((s) => s.nome);
  scriviNotaOrdine(sessioni);
  const cambiato = calcolato.map((s) => s.nome).join() !== mostrato.join();
  $("#riordina").classList.toggle("da-riordinare", cambiato);
  $("#riordina").textContent = cambiato ? "Riordina ●" : "Riordina";
  aggiornaBadge();
  disegnaSchede(sessioni);
  const vive = new Set(ordinate.map((s) => s.nome));
  for (const [nome, r] of righe) if (!vive.has(nome)) { r.remove(); righe.delete(nome); }
  const inTrascinamento = $(".riga.trascina", righeEl);
  // sposta solo le righe fuori posto: togliere dal DOM l'elemento che ha il fuoco lo fa perdere (testo digitato perso)
  const fuoco = document.activeElement, sel = fuoco && fuoco.selectionStart;
  ordinate.forEach((s, i) => {
    const r = righe.get(s.nome) || nuovaRiga(s.nome);
    riempi(r, s);
    if (!inTrascinamento && righeEl.children[i] !== r) righeEl.insertBefore(r, righeEl.children[i] || null);
  });
  if (fuoco && fuoco !== document.activeElement && document.contains(fuoco)) {
    fuoco.focus({ preventScroll: true });
    if (sel != null && fuoco.setSelectionRange) fuoco.setSelectionRange(sel, sel);
  }
  $("#vuoto").hidden = ordinate.length > 0;
}

/* ---------- aggiornamento della pagina ----------
   I file della pagina cambiano sul disco → il server manda un'altra X-Regia-Versione → si ricarica, ma solo quando
   nessuna casella ha testo scritto (una bozza non si perde mai): altrimenti si riprova al giro dopo. */
let versione = null;
function controllaVersione(v) {
  if (!v) return;
  if (versione === null) { versione = v; return; }
  if (v === versione) return;
  const bozza = [...document.querySelectorAll("textarea, input[type=text]")].some((x) => x.value.trim());
  if (!bozza) location.reload();
}

/* ---------- rete ---------- */
async function aggiorna() {
  try {
    const risp = await fetch("/api/stato", { cache: "no-store" });
    if (!risp.ok) throw new Error(`HTTP ${risp.status}`);
    const nuovo = await risp.json();
    controllaVersione(risp.headers.get("X-Regia-Versione"));
    avvisa(ultimo, nuovo);
    ultimo = nuovo;
    // /api/stato può avere fino a 5 s di cache: i messaggi arrivati nel frattempo sparirebbero e il giro da 2 s,
    // con l'ETag invariato (304), non li rimetterebbe più. Si azzera l'ETag e si rifonde subito.
    etagMsg = null;
    disegna();
    aggiornaMessaggi();
    $("#aggiornato").textContent = `Aggiornato alle ${new Date().toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`;
    $("#aggiornato").classList.remove("guasto");
  } catch (e) {
    $("#aggiornato").textContent = "Server della Regia non raggiungibile: riprovo ogni 12 secondi.";
    $("#aggiornato").classList.add("guasto");
  }
}

async function manda(sessione, testo, riga) {
  try {
    const r = await fetch("/api/richiesta", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sessione, testo }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.errore || `HTTP ${r.status}`);
    await aggiorna();
    return true;
  } catch (e) {
    if (riga) {
      let msg = $(".errore-invio", riga);
      if (!msg) { msg = el("p", "errore-invio"); $(".modulo", riga).after(msg); }
      msg.textContent = e instanceof TypeError ? "Non mandata: il server della Regia non risponde. Il testo resta qui." : `Non mandata: ${e.message}`;
      setTimeout(() => msg.remove(), 6000);
    }
    return false;
  }
}

/* ---------- comandi della testata ---------- */
$("#ordine").value = pref.ordine;
$("#fermi-in-cima").checked = pref.fermiInCima;
$("#ordine").addEventListener("change", (e) => { pref.ordine = e.target.value; salva(); riordina(); });
$("#fermi-in-cima").addEventListener("change", (e) => { pref.fermiInCima = e.target.checked; salva(); riordina(); });
$("#riordina").addEventListener("click", riordina);
$("#sospeso-apri").addEventListener("click", () => { pref.sospesoAperto = !pref.sospesoAperto; salva(); disegna(); });

{
  const form = $("#al-sup-modulo"), ta = $("#al-sup-testo");
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const testo = ta.value.trim();
    if (!testo || ta.readOnly) return;
    ta.readOnly = true; form.setAttribute("aria-busy", "true");
    const ok = await manda("SUP", testo, $("#al-sup"));
    ta.readOnly = false; form.removeAttribute("aria-busy");
    if (ok) ta.value = "";
    ta.focus({ preventScroll: true });
  });
  const leggi = () => { segnaViste(SUP); salva(); if (ultimo) disegnaSup(ultimo); };
  ta.addEventListener("focus", leggi);
  $(".al-sup-filo").addEventListener("click", leggi);
}

$("#inizio").addEventListener("click", async (e) => { // un clic solo; lo stato si vede sotto, in «Le tue richieste»
  const b = e.currentTarget;
  b.disabled = true; b.textContent = "…";
  const ok = await manda("SUP", INIZIO_LAVORI, $("#al-sup"));
  b.disabled = false;
  b.textContent = ok ? "Mandato al SUP ✓" : "Non mandato: riprova";
  setTimeout(() => { b.textContent = "Inizio lavori: riepilogo dal SUP"; }, 4000);
});

/* ---------- messaggi ogni 2 s: solo se cambiano (ETag → 304), la casella non viene toccata ---------- */
async function aggiornaMessaggi() {
  if (!ultimo) return;
  const filoNuovo = !document.hidden && await caricaFiloSup(); // filo unico del SUP, ETag/304
  try {
    const r = await fetch("/api/messaggi", { headers: etagMsg ? { "If-None-Match": etagMsg } : {} });
    if (r.status === 304 || !r.ok) { if (filoNuovo) disegna(); return; }
    etagMsg = r.headers.get("ETag");
    const m = await r.json(), vuoto = { richieste: [], risposte: [] };
    const prima = { ...ultimo, sup: { ...ultimo.sup } };
    ultimo.sup.richieste = (m.per.SUP || vuoto).richieste; // nei file il filo del superagente si chiama «SUP»
    ultimo.sup.risposte = (m.per.SUP || vuoto).risposte;
    ultimo.ascolto = m.ascolto;
    if ("pausa" in m) ultimo.pausa = m.pausa;
    for (const s of ultimo.sessioni || []) {
      const v = m.per[s.nome] || vuoto;
      s.richieste = v.richieste; s.risposte = v.risposte;
    }
    avvisa(prima, ultimo);
    disegna();
  } catch (_) { /* il giro da 12 s segnala il server spento */ }
}

/* ---------- app installata: numero sull'icona, avvisi di macOS ---------- */
function daGuardare(d) {
  if (!d) return 0;
  const vista_ = pref.viste[SUP] || "";
  // solo le risposte del SUP non lette
  return (d.sup.risposte || []).filter((x) => x.ora > vista_).length;
}
function aggiornaBadge() {
  if (!("setAppBadge" in navigator)) return;
  const n = daGuardare(ultimo);
  (n ? navigator.setAppBadge(n) : navigator.clearAppBadge()).catch(() => {});
}
function avvisa(prima, dopo) {
  if (!prima || !dopo || !pref.avvisi || !("Notification" in window) || Notification.permission !== "granted") return;
  if (document.hasFocus()) return; // stai guardando la Regia: niente avviso
  // SOLO i messaggi del SUP nella sua chat: niente più avvisi per sessioni ferme, fili di sessione o stati.
  const voci = [];
  const ultimaOra = (prima.sup.risposte || []).reduce((m, x) => (x.ora > m ? x.ora : m), "");
  for (const x of dopo.sup.risposte || []) if (x.ora > ultimaOra && ultimaOra) voci.push(["Il SUP ti ha risposto", senzaLink(x.testo).slice(0, 160), "sup-" + x.ora]);
  voci.slice(0, 3).forEach(([titolo, body, tag]) => {
    const o = { body, tag, icon: "/icone/regia-192.png" };
    if (navigator.serviceWorker && navigator.serviceWorker.controller) navigator.serviceWorker.ready.then((reg) => reg.showNotification(titolo, o)).catch(() => {});
    else try { new Notification(titolo, o); } catch (_) { /* niente */ }
  });
}
{
  const b = $("#notifiche");
  const scrivi = () => {
    const on = pref.avvisi && "Notification" in window && Notification.permission === "granted";
    b.setAttribute("aria-pressed", String(on));
    b.textContent = on ? "Avvisi macOS: accesi" : (window.Notification && Notification.permission === "denied" ? "Avvisi macOS: bloccati" : "Avvisi macOS: spenti");
  };
  if ("Notification" in window) {
    b.hidden = false; scrivi();
    b.addEventListener("click", async () => {
      if (pref.avvisi) pref.avvisi = false;
      else pref.avvisi = (await Notification.requestPermission()) === "granted";
      salva(); scrivi();
    });
  }
}
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});

aggiorna();
// finestra nascosta o ridotta: lo stato ogni minuto e i messaggi ogni 10 s, così avvisi e numero sull'icona restano vivi
let giro = 0;
setInterval(() => { giro += 1; if (!document.hidden || giro % 5 === 0) aggiorna(); }, OGNI_MS);
let giroMsg = 0;
setInterval(() => { giroMsg += 1; if (!document.hidden || giroMsg % 5 === 0) aggiornaMessaggi(); }, MESSAGGI_MS);
setInterval(aggiornaChat, MESSAGGI_MS); // chat delle sessioni aperte: 304 se niente è cambiato
document.addEventListener("visibilitychange", () => { if (!document.hidden) { aggiorna(); } });
document.addEventListener("visibilitychange", () => { if (!document.hidden) aggiorna(); });

/* ---------- barra fissa: schede delle sessioni vive ---------- */
// Ordine di apertura (stabile come le schede di Chrome), SUP sempre prima; spariscono quando la sessione muore.
/* chi aspetta te, sempre in vista nella barra fissa */
function disegnaAspettaTe(sessioni) {
  const box = $("#aspetta-te"), attese = sessioni.filter((s) => s.stato === "in attesa");
  box.replaceChildren();
  box.hidden = !attese.length;
  attese.forEach((s) => {
    const b = el("button", "aspetta-riga");
    b.type = "button"; b.dataset.nome = s.nome;
    b.title = "Clic per aprire la sessione. Ferma su un comando da più di 2 minuti: di solito una domanda di permesso nel suo terminale.";
    b.append(el("strong", "", `${s.nome} aspetta te`));
    const q = senzaLink(primaRiga(s.ultimo_testo)).slice(0, 140);
    if (q) b.append(document.createTextNode(`: ${q}`));
    const fila_ = el("div", "aspetta-fila");
    fila_.append(b, bottoneTerminale(s.nome));
    box.append(fila_);
  });
}
function disegnaSchede(sessioni) {
  disegnaAspettaTe(sessioni);
  const nav = $("#schede-sessioni");
  if (!nav) return;
  const sup = ((ultimo && ultimo.sessioni) || []).find((s) => s.nome === SUP); // vista() lo esclude: ha il suo riquadro
  const lista = [...sessioni.filter((s) => s.nome !== SUP), ...(sup ? [sup] : [])].sort((a, b) => (a.nome === SUP ? -1 : b.nome === SUP ? 1
    : inPausa(a) - inPausa(b) || String(a.avviata || "").localeCompare(String(b.avviata || "")) || a.nome.localeCompare(b.nome)));
  const chiave = lista.map((s) => `${s.nome}:${s.stato}:${aperta(s.nome)}`).join("|");
  if (nav.dataset.chiave === chiave) return; // niente ridisegno se non cambia nulla
  nav.dataset.chiave = chiave;
  nav.replaceChildren(...lista.map((s) => {
    const b = el("button", "scheda-s");
    b.type = "button";
    b.dataset.nome = s.nome;
    b.dataset.stato = s.stato;
    b.title = `${s.nome} · ${s.stato}`;
    if (s.nome !== SUP && aperta(s.nome)) b.classList.add("attiva");
    if (s.nome !== SUP && dormiente(s)) b.classList.add("dormiente");
    const p = el("span", "punto"); p.setAttribute("aria-hidden", "true");
    b.append(p, document.createTextNode(s.nome === SUP ? "SUP" : s.nome));
    return b;
  }));
}
$("#schede-sessioni").addEventListener("click", (e) => {
  const b = e.target.closest(".scheda-s");
  if (b) apriScheda(b.dataset.nome);
});
$("#aspetta-te").addEventListener("click", (e) => {
  if (e.target.closest(".apri-term")) return;
  const b = e.target.closest("[data-nome]");
  if (b) apriScheda(b.dataset.nome);
});
/* «Apri terminale» nei banner rossi: il server porta in primo piano la scheda di Terminal
   della sessione (pid → tty → scheda). Errore (permesso Automazione, scheda non trovata) scritto sul bottone. */
function bottoneTerminale(nome) {
  const b = el("button", "apri-term", "Apri terminale");
  b.type = "button"; b.dataset.term = nome; b.title = `Porta in primo piano la scheda di Terminal di ${nome}`;
  return b;
}
document.addEventListener("click", async (e) => {
  const b = e.target.closest(".apri-term");
  if (!b) return;
  e.stopPropagation();
  if (b.disabled) return;
  b.disabled = true;
  const scritta = b.querySelector("span") || b, prima = scritta.textContent, titolo = b.title;
  try {
    const r = await fetch("/api/terminale", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nome: b.dataset.term }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.errore || `HTTP ${r.status}`);
    scritta.textContent = d.prova ? "prova: non aperto" : "Aperto";
  } catch (err) {
    scritta.textContent = "Non riuscito"; b.title = String(err.message || err);
    const n = el("span", "term-errore", ` ${b.title}`); b.after(n); setTimeout(() => n.remove(), 15000);
  } finally {
    setTimeout(() => { b.disabled = false; scritta.textContent = prima; b.title = titolo; }, 4000);
  }
}, true);
function apriScheda(nome) {
  if (nome === SUP) {
    $("#al-sup").scrollIntoView({ behavior: "smooth", block: "start" });
    $("#al-sup-testo").focus({ preventScroll: true });
    return;
  }
  if (!aperta(nome)) {
    pref.aperte[nome] = true; segnaViste(nome); salva(); disegna();
    caricaChat(nome).then((ok) => { if (ok) disegna(); });
  }
  const r = righe.get(nome);
  if (r) r.scrollIntoView({ behavior: "smooth", block: "start" });
}
// altezza della barra fissa → margine per lo scorrimento (la riga non finisce sotto la barra)
{
  const f = $("#fissa");
  const fp = $(".fascia-prova"); // server di prova: la fascia rossa resta sopra, la barra sotto di lei
  const misura = () => {
    const h = fp ? fp.offsetHeight : 0;
    f.style.top = h + "px";
    document.documentElement.style.setProperty("--alt-fissa", (f.offsetHeight + h) + "px");
  };
  if ("ResizeObserver" in window) { const o = new ResizeObserver(misura); o.observe(f); if (fp) o.observe(fp); }
  misura();
}

/* altezza del riquadro SUP scelta trascinando l'angolo: ricordata (solo su schermo largo, dove si può allungare) */
(() => {
  const box = document.getElementById("al-sup");
  if (!box) return;
  if (pref.supAltezza && innerWidth > 980) box.style.height = pref.supAltezza;
  if (!("ResizeObserver" in window)) return;
  let t = 0;
  new ResizeObserver(() => {
    clearTimeout(t);
    t = setTimeout(() => {
      if (innerWidth > 980 && box.style.height && box.style.height !== pref.supAltezza) { pref.supAltezza = box.style.height; salva(); }
    }, 400);
  }).observe(box);
})();
