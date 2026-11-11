/* Underfilled: everything runs in the browser from data/bundle.json. */
(function () {
  "use strict";

  const $ = (s, el = document) => el.querySelector(s);
  const fmt = (n) => n.toLocaleString("en-US");
  const pct = (p, d = 1) => (p * 100).toFixed(d) + "%";
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const NS = "http://www.w3.org/2000/svg";
  const kfmt = (n) => (n >= 1000 ? (n / 1000).toFixed(1).replace(/\.0$/, "") + "k" : String(n));

  const ITYPES = [
    ["DRUG", "Drug"], ["BIOLOGICAL", "Biologic"], ["DEVICE", "Device"], ["PROCEDURE", "Procedure"],
    ["BEHAVIORAL", "Behavioral"], ["RADIATION", "Radiation"], ["DIETARY_SUPPLEMENT", "Supplement"],
  ];
  const PRESETS = {
    academic: { phase: "2", sponsor: "academic", area: "cancer", itypes: ["DRUG"], sites: 1, countries: 1, n_inc: 12, n_exc: 18,
      healthy: false, upper_age: false, kids_only: false, older_only: false, one_sex: false, randomized: false, blinded: false, arms: 1, n_primary: 1 },
    industry: { phase: "3", sponsor: "industry", area: "metabolic", itypes: ["DRUG"], sites: 80, countries: 8, n_inc: 6, n_exc: 14,
      healthy: false, upper_age: true, kids_only: false, older_only: false, one_sex: false, randomized: true, blinded: true, arms: 2, n_primary: 1 },
    rare: { phase: "1/2", sponsor: "academic", area: "congenital", itypes: ["BIOLOGICAL"], sites: 3, countries: 1, n_inc: 9, n_exc: 15,
      healthy: false, upper_age: true, kids_only: true, older_only: false, one_sex: false, randomized: false, blinded: false, arms: 1, n_primary: 2 },
  };
  let B = null;

  fetch("data/bundle.json").then((r) => r.json()).then((b) => { B = b; init(); })
    .catch(() => { $("#r-pct").textContent = "n/a"; $("#r-vs").textContent = "Could not load data/bundle.json. Serve this folder over HTTP."; });

  function init() {
    bindNumbers();
    drawReasons();
    buildForm();
    drawCharts();
    drawCard();
    let lastW = window.innerWidth;
    window.addEventListener("resize", () => { if (Math.abs(window.innerWidth - lastW) > 40) { lastW = window.innerWidth; drawCharts(); } });
    update();
  }

  // ---------- Section A ----------
  function bindNumbers() {
    const c = B.cohort;
    const set = (k, v) => document.querySelectorAll(`[data-bind="${k}"]`).forEach((el) => (el.textContent = v));
    set("lowAccrual", fmt(c.low_accrual));
    set("terminated", fmt(c.terminated));
    set("cohortN", fmt(c.n));
    set("shareOfTerm", pct(c.low_accrual / c.terminated, 0));
    set("baseRate", "1 in " + Math.round(c.n / c.low_accrual));
    set("nFeat", B.model.names.length);
    if (B.model.holdout.auc_no_sites) set("aucNoSites", B.model.holdout.auc_no_sites.toFixed(2));
  }

  function drawReasons() {
    const max = B.reasons[0].n;
    const total = B.cohort.terminated;
    $("#reasons").innerHTML = B.reasons.map((r) =>
      `<li class="${r.k === "low accrual" ? "is-key" : ""}"><span>${esc(cap(r.k))}</span>` +
      `<span class="reasons__bar" aria-hidden="true"><i style="width:${(r.n / max) * 100}%"></i></span>` +
      `<span class="reasons__n" title="${fmt(r.n)} trials">${pct(r.n / total, 0)}</span></li>`).join("");
  }
  const cap = (s) => (s === "covid-19" ? "COVID-19" : s.charAt(0).toUpperCase() + s.slice(1));

  // ---------- Section B: form ----------
  function buildForm() {
    const sel = $("#area");
    sel.innerHTML = B.areas.map((a) => `<option value="${a.k}">${esc(a.label)}</option>`).join("") +
      `<option value="">None of these</option>`;
    sel.value = "cancer";
    $("#itypes").innerHTML = ITYPES.map(([k, l]) =>
      `<label><input type="checkbox" name="it_${k}" ${k === "DRUG" ? "checked" : ""} /><span>${l}</span></label>`).join("");
    const form = $("#crf");
    form.addEventListener("input", update);
    form.addEventListener("change", update);
    form.addEventListener("submit", (e) => e.preventDefault());
    document.querySelectorAll(".preset").forEach((b) => b.addEventListener("click", () => applyPreset(PRESETS[b.dataset.preset])));
    $("#elig").addEventListener("input", (e) => {
      const { inc, exc } = countCriteria(e.target.value);
      if (!e.target.value.trim()) { $("#elig-out").textContent = "Counts bullet lines under each heading, the same way the registry data was counted."; return; }
      form.n_inc.value = inc; form.n_exc.value = exc;
      $("#elig-out").textContent = `Counted ${inc} inclusion and ${exc} exclusion criteria.`;
      update();
    });
  }

  function applyPreset(p) {
    const f = $("#crf");
    f.querySelector(`input[name=phase][value="${p.phase}"]`).checked = true;
    f.querySelector(`input[name=sponsor][value="${p.sponsor}"]`).checked = true;
    f.area.value = p.area;
    ITYPES.forEach(([k]) => (f[`it_${k}`].checked = p.itypes.includes(k)));
    ["sites", "countries", "n_inc", "n_exc", "arms", "n_primary"].forEach((k) => (f[k].value = p[k]));
    ["healthy", "upper_age", "kids_only", "older_only", "one_sex", "randomized", "blinded"].forEach((k) => (f[k].checked = p[k]));
    update();
  }

  const BULLET = /^\s*(\*|-|•|·|‣|\d{1,2}[.)]|[a-zA-Z][.)]|\(\w{1,3}\))\s+/;
  function countBlock(text) {
    const lines = text.split("\n").filter((l) => l.trim());
    let n = lines.filter((l) => BULLET.test(l)).length;
    if (!n) n = lines.filter((l) => !/criteria\s*:?\s*$/i.test(l)).length;
    return n;
  }
  function countCriteria(text) {
    const parts = text.split(/exclusion criteria\s*:?/i);
    const inc = parts[0].replace(/^\s*inclusion criteria\s*:?/i, "");
    return { inc: countBlock(inc), exc: parts.length > 1 ? countBlock(parts.slice(1).join(" ")) : 0 };
  }

  function readForm() {
    const f = $("#crf");
    const num = (k, lo, hi) => Math.max(lo, Math.min(hi, parseInt(f[k].value, 10) || lo));
    return {
      phase: f.querySelector("input[name=phase]:checked").value,
      sponsor: f.querySelector("input[name=sponsor]:checked").value,
      area: f.area.value,
      itypes: ITYPES.map(([k]) => k).filter((k) => f[`it_${k}`].checked),
      sites: num("sites", 1, 2000), countries: num("countries", 1, 100),
      n_inc: num("n_inc", 0, 60), n_exc: num("n_exc", 0, 80),
      healthy: f.healthy.checked, upper_age: f.upper_age.checked || f.kids_only.checked, kids_only: f.kids_only.checked,
      older_only: f.older_only.checked, one_sex: f.one_sex.checked,
      randomized: f.randomized.checked, blinded: f.blinded.checked,
      arms: num("arms", 1, 20), n_primary: num("n_primary", 1, 20),
    };
  }

  const siteBucket = (n) => (n <= 1 ? "1" : n <= 5 ? "2-5" : n <= 20 ? "6-20" : n <= 100 ? "21-100" : "100+");

  function featurize(d) {
    const sb = siteBucket(d.sites);
    const f = {
      "phase 1/2": d.phase === "1/2", "phase 2/3": d.phase === "2/3", "phase 3": d.phase === "3",
      "industry sponsor": d.sponsor === "industry", "government sponsor": d.sponsor === "government",
      "log inclusion criteria": Math.log1p(Math.min(d.n_inc, 60)), "log exclusion criteria": Math.log1p(Math.min(d.n_exc, 80)),
      "sites 2-5": sb === "2-5", "sites 6-20": sb === "6-20", "sites 21-100": sb === "21-100", "sites 100+": sb === "100+",
      multinational: d.countries > 1, "healthy volunteers": d.healthy, "upper age limit": d.upper_age,
      "children only": d.kids_only, "older adults only": d.older_only, "one sex only": d.one_sex,
      "open label": !d.blinded, randomized: d.randomized, "3+ arms": d.arms >= 3,
      "log primary outcomes": Math.log1p(Math.min(d.n_primary, 20)),
    };
    B.areas.forEach((a) => (f["area: " + a.k] = d.area === a.k));
    ITYPES.forEach(([k]) => (f["uses " + k.toLowerCase().replace("_", " ")] = d.itypes.includes(k)));
    return B.model.names.map((n) => +f[n]);
  }

  function score(x) {
    const m = B.model;
    let z = m.w[0];
    const contrib = x.map((v, i) => { const c = (m.w[i + 1] * (v - m.mu[i])) / m.sd[i]; z += c; return c; });
    return { p: 1 / (1 + Math.exp(-z)), contrib };
  }

  function percentile(p) {
    const q = B.model.pctl;
    let i = 0;
    while (i < 100 && q[i + 1] < p) i++;
    return i;
  }

  function update() {
    if (!B) return;
    const d = readForm();
    const x = featurize(d);
    const { p, contrib } = score(x);
    const base = B.cohort.low_accrual / B.cohort.n;
    $("#r-pct").textContent = pct(p);
    const ratio = p / base;
    $("#r-vs").innerHTML = ratio >= 1.15
      ? `<b>${ratio.toFixed(1)}x</b> the cohort average of ${pct(base)}.`
      : ratio <= 0.87 ? `<b>${(1 / ratio).toFixed(1)}x lower</b> than the cohort average of ${pct(base)}.`
      : `About the cohort average of ${pct(base)}.`;
    const pc = percentile(p);
    $("#r-meter").style.left = pc + "%";
    const avgPc = percentile(base);
    $("#r-avg").style.left = avgPc + "%";
    $("#r-avg").textContent = "average";
    $("#r-pctl").textContent = `riskier than ${pc}% of registered designs`;
    // the holdout test overestimated the riskiest tenth, so say so where it applies
    const cal = B.model.holdout.calibration[9];
    $("#r-calib").textContent = pc >= 90
      ? `Designs in the riskiest tenth were overestimated in testing: ${pct(cal.pred)} predicted vs ${pct(cal.obs)} observed on 2017 to 2019 trials. Read this as "high," not as an exact number.`
      : "";

    // what moves it: contributions vs the average registered trial, grouped by form field
    const names = B.model.names;
    const groups = {};
    const add = (g, text, c) => { groups[g] = groups[g] || { text, c: 0 }; groups[g].c += c; };
    const spLab = { industry: "Industry sponsor", academic: "Academic or hospital sponsor", government: "Government sponsor" };
    const areaName = d.area ? B.areas.find((a) => a.k === d.area).label.toLowerCase() : "none of the listed areas";
    const itLab = d.itypes.length ? ITYPES.filter(([k]) => d.itypes.includes(k)).map(([, l]) => l.toLowerCase()).join(", ") : "none ticked";
    const FLAG = {
      multinational: ["More than one country", "One country only"],
      "healthy volunteers": ["Accepts healthy volunteers", "No healthy volunteers"],
      "upper age limit": ["Has an upper age limit", "No upper age limit"],
      "children only": ["Children only", "Not limited to children"],
      "older adults only": ["Adults 60+ only", "Not limited to older adults"],
      "one sex only": ["One sex only", "Open to all sexes"],
      "open label": ["Open label", "Blinded"],
      randomized: ["Randomized", "Not randomized"],
      "3+ arms": ["Three or more arms", "One or two arms"],
    };
    contrib.forEach((c, i) => {
      const n = names[i];
      if (n.startsWith("phase")) add("phase", "Phase " + d.phase, c);
      else if (n.endsWith("sponsor")) add("sponsor", spLab[d.sponsor], c);
      else if (n.startsWith("sites")) add("sites", d.sites === 1 ? "1 site" : fmt(d.sites) + " sites", c);
      else if (n.startsWith("area: ")) add("area", "Area: " + areaName, c);
      else if (n.startsWith("uses ")) add("itype", "Intervention: " + itLab, c);
      else if (n === "log inclusion criteria") add(n, `${d.n_inc} inclusion criteria (typical: ${B.medians.n_inc})`, c);
      else if (n === "log exclusion criteria") add(n, `${d.n_exc} exclusion criteria (typical: ${B.medians.n_exc})`, c);
      else if (n === "log primary outcomes") add(n, d.n_primary === 1 ? "1 primary outcome" : `${d.n_primary} primary outcomes`, c);
      else if (FLAG[n]) add(n, FLAG[n][x[i] ? 0 : 1], c);
    });
    const ranked = Object.values(groups).filter((g) => Math.abs(g.c) > 0.04).sort((a, b) => Math.abs(b.c) - Math.abs(a.c)).slice(0, 6);
    $("#r-moves").innerHTML = ranked.length ? ranked.map((g) => {
      const f = Math.exp(g.c);
      return `<li><span>${esc(g.text)}</span><span class="dir ${g.c > 0 ? "up" : "down"}" title="multiplies the odds vs the average registered trial">x${f.toFixed(2)}</span></li>`;
    }).join("") : `<li><span>Close to the average registered design on every field.</span><span></span></li>`;

    // what-if edits
    const edits = [];
    const tryEdit = (text, patch) => {
      const d2 = Object.assign({}, d, patch);
      const p2 = score(featurize(d2)).p;
      if (p2 < p - 0.002) edits.push({ text, p2 });
    };
    if (d.n_exc > 5) tryEdit(`Cut 5 exclusion criteria (${d.n_exc} to ${d.n_exc - 5})`, { n_exc: d.n_exc - 5 });
    if (d.n_inc > 4) tryEdit(`Cut 3 inclusion criteria (${d.n_inc} to ${d.n_inc - 3})`, { n_inc: d.n_inc - 3 });
    const nextSites = d.sites <= 1 ? 6 : d.sites <= 5 ? 6 : d.sites <= 20 ? 21 : d.sites <= 100 ? 101 : null;
    if (nextSites) tryEdit(`Open ${nextSites} sites instead of ${d.sites}`, { sites: nextSites });
    if (d.countries <= 1 && d.sites > 1) tryEdit("Recruit in a second country", { countries: 2 });
    edits.sort((a, b) => a.p2 - b.p2);
    $("#r-whatif").innerHTML = edits.length
      ? edits.slice(0, 3).map((e) => `<li>${esc(e.text)}: <b>${pct(p)} to ${pct(e.p2)}</b></li>`).join("")
      : `<li>None of the simple edits (fewer criteria, more sites, a second country) lowers the estimate for this design.</li>`;

    // trials like yours
    const key = `${d.phase}|${d.sponsor}|${d.area || "unmapped"}`;
    const cell = B.cube[key];
    const areaLabel = d.area ? B.areas.find((a) => a.k === d.area).label.toLowerCase() : "unmapped";
    const spon = { industry: "industry", academic: "academic or hospital", government: "government" }[d.sponsor];
    if (cell && cell[1] >= 30) {
      $("#r-like").innerHTML = `Of <b>${fmt(cell[1])}</b> Phase ${d.phase} ${spon} trials in ${esc(areaLabel)} in this cohort, <b>${fmt(cell[0])}</b> (${pct(cell[0] / cell[1])}) stopped for low accrual. Below are real low-accrual stops closest to your design.`;
    } else if (cell) {
      $("#r-like").innerHTML = `Only ${fmt(cell[1])} registered Phase ${d.phase} ${spon} trials in ${esc(areaLabel)}, too few for a stable rate. ${fmt(cell[0])} stopped for low accrual.`;
    } else {
      $("#r-like").textContent = `No registered Phase ${d.phase} ${spon} trials in ${areaLabel} in this cohort.`;
    }
    const ex = B.examples.filter((e) => e.ph === d.phase && (d.area ? e.a.includes(d.area) : e.a.length === 0));
    const pick = ex.filter((e) => e.sp === d.sponsor).concat(ex.filter((e) => e.sp !== d.sponsor));
    // nearest by sites and exclusion count, so the list reacts to the form
    pick.sort((a, b) => (a.sp !== d.sponsor) - (b.sp !== d.sponsor) ||
      (Math.abs(Math.log1p(a.sites) - Math.log1p(d.sites)) + Math.abs(a.exc - d.n_exc) / 10) -
      (Math.abs(Math.log1p(b.sites) - Math.log1p(d.sites)) + Math.abs(b.exc - d.n_exc) / 10));
    $("#r-examples").innerHTML = pick.length === 0
      ? `<li>No low-accrual stops in this cohort match this phase and area.</li>`
      : pick.slice(0, 3).map((e) =>
      `<li><a class="ex-id" href="https://clinicaltrials.gov/study/${e.nct}">${e.nct}</a> &middot; ${esc(e.t)}` +
      `<q>${esc(e.why)}</q></li>`).join("");
  }

  // ---------- Section C ----------
  function drawCharts() {
    const base = B.cohort.low_accrual / B.cohort.n;
    const T = B.tables;
    const areaLab = Object.fromEntries(B.areas.map((a) => [a.k, a.label])); areaLab.unmapped = "No mapped area";
    const specs = [
      { t: "Inclusion criteria", s: "More reasons to say yes is also more ways to say no.", rows: T.inclusion },
      { t: "Exclusion criteria", s: "Rises fast, then flattens after about ten.", rows: T.exclusion },
      { t: "Registered sites", s: "Single-site and small studies stop far more often.", rows: T.sites },
      { t: "Lead sponsor", s: "Academic studies stop for accrual about three times as often as industry.", rows: T.sponsor.map((r) => ({ ...r, k: cap(r.k) })) },
      { t: "Phase", s: "Phase 2 stops most often.", rows: T.phase.map((r) => ({ ...r, k: "Phase " + r.k })) },
      { t: "Masking", s: "Open-label trials stop about twice as often.", rows: T.masking.map((r) => ({ ...r, k: cap(r.k) })) },
      { t: "Condition area", s: "Cancer leads. Areas overlap, so a trial can count in several.", rows: T.area.map((r) => ({ ...r, k: areaLab[r.k] || r.k })), wide: true, horiz: true },
    ];
    const host = $("#charts");
    host.innerHTML = "";
    specs.forEach((sp) => {
      const fig = document.createElement("figure");
      fig.className = "chart" + (sp.wide ? " chart--wide" : "");
      fig.innerHTML = `<figcaption>${esc(sp.t)}</figcaption><p class="sub">${esc(sp.s)}</p>`;
      host.appendChild(fig);
      fig.appendChild(sp.horiz ? hbars(sp.rows, base, fig.clientWidth - 32) : vbars(sp.rows, base));
    });
  }

  function el(tag, attrs, text) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }

  function vbars(rows, base) {
    const W = 300, H = 170, padL = 4, padB = 30, padT = 18;
    const max = Math.max(...rows.map((r) => r.ci[1]), base) * 1.08;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": rows.map((r) => `${r.k}: ${pct(r.rate)}`).join(", ") });
    const bw = (W - padL) / rows.length;
    const y = (v) => H - padB - (v / max) * (H - padB - padT);
    rows.forEach((r, i) => {
      const x = padL + i * bw + bw * 0.18, w = bw * 0.64;
      svg.appendChild(el("rect", { x, y: y(r.rate), width: w, height: H - padB - y(r.rate), fill: r.rate > base ? "#c8431f" : "#2f4a6d" }));
      const cx = x + w / 2;
      svg.appendChild(el("line", { x1: cx, x2: cx, y1: y(r.ci[0]), y2: y(r.ci[1]), stroke: "#17212b", "stroke-width": 1 }));
      svg.appendChild(el("text", { x: cx, y: y(r.ci[1]) - 4, "text-anchor": "middle", class: "v" }, pct(r.rate)));
      svg.appendChild(el("text", { x: cx, y: H - padB + 14, "text-anchor": "middle" }, r.k));
      svg.appendChild(el("text", { x: cx, y: H - padB + 26, "text-anchor": "middle", "font-size": "9" }, "n=" + kfmt(r.n)));
    });
    svg.appendChild(el("line", { x1: 0, x2: W, y1: y(base), y2: y(base), stroke: "#17212b", "stroke-dasharray": "3 3", "stroke-width": 1 }));
    svg.appendChild(el("line", { x1: 0, x2: W, y1: H - padB, y2: H - padB, stroke: "#a9aea4" }));
    return svg;
  }

  function hbars(rows, base, avail) {
    const narrow = avail < 520;
    const W = narrow ? Math.max(300, avail) : 640, rowH = narrow ? 22 : 19, padL = narrow ? 160 : 190, padR = narrow ? 92 : 110, H = rows.length * rowH + 22;
    const max = Math.max(...rows.map((r) => r.ci[1])) * 1.05;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": rows.map((r) => `${r.k}: ${pct(r.rate)}`).join(", ") });
    const x = (v) => padL + (v / max) * (W - padL - padR);
    rows.forEach((r, i) => {
      const yy = 6 + i * rowH;
      svg.appendChild(el("text", { x: padL - 8, y: yy + 11, "text-anchor": "end" }, r.k));
      svg.appendChild(el("rect", { x: padL, y: yy + 2, width: x(r.rate) - padL, height: rowH - 7, fill: r.rate > base ? "#c8431f" : "#2f4a6d" }));
      svg.appendChild(el("line", { x1: x(r.ci[0]), x2: x(r.ci[1]), y1: yy + 8, y2: yy + 8, stroke: "#17212b" }));
      svg.appendChild(el("text", { x: x(r.ci[1]) + 6, y: yy + 11, class: "v" }, pct(r.rate)));
      svg.appendChild(el("text", { x: W, y: yy + 11, "text-anchor": "end", "font-size": "9" }, "n=" + kfmt(r.n)));
    });
    svg.appendChild(el("line", { x1: x(base), x2: x(base), y1: 0, y2: H - 14, stroke: "#17212b", "stroke-dasharray": "3 3" }));
    svg.appendChild(el("text", { x: x(base), y: H - 2, "text-anchor": "middle", "font-size": "9" }, "average " + pct(base)));
    return svg;
  }

  // ---------- Section D ----------
  function drawCard() {
    const h = B.model.holdout;
    const stat = (t, v, s) => `<div><dt>${t}</dt><dd>${v}<small>${s}</small></dd></div>`;
    $("#stats").innerHTML =
      stat("Holdout AUC", h.auc.toFixed(2), "0.5 is a coin flip, 1.0 is perfect") +
      stat("Top-tenth lift", h.top_decile_lift.toFixed(1) + "x", `riskiest tenth caught ${pct(h.top_decile_share, 0)} of stops`) +
      stat("Test trials", fmt(h.n_test), `started 2017 to 2019, base rate ${pct(h.base_rate)}`) +
      stat("Brier score", h.brier.toFixed(4), `vs ${h.brier_base.toFixed(4)} guessing the base rate`);
    const W = 420, H = 190, padB = 24, padT = 10, padL = 32;
    const cal = h.calibration;
    const max = Math.max(...cal.map((c) => Math.max(c.pred, c.obs))) * 1.1;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Predicted versus observed low-accrual stop rate by decile" });
    const bw = (W - padL) / cal.length;
    const y = (v) => H - padB - (v / max) * (H - padB - padT);
    [0, 0.05, 0.1, 0.15].filter((t) => t < max).forEach((t) => {
      svg.appendChild(el("line", { x1: padL, x2: W, y1: y(t), y2: y(t), stroke: "#cdd0c8" }));
      svg.appendChild(el("text", { x: padL - 4, y: y(t) + 3, "text-anchor": "end" }, pct(t, 0)));
    });
    cal.forEach((c, i) => {
      const x0 = padL + i * bw + bw * 0.14, w = bw * 0.34;
      svg.appendChild(el("rect", { x: x0, y: y(c.pred), width: w, height: H - padB - y(c.pred), fill: "#a9aea4" }));
      svg.appendChild(el("rect", { x: x0 + w, y: y(c.obs), width: w, height: H - padB - y(c.obs), fill: "#c8431f" }));
      svg.appendChild(el("text", { x: x0 + w, y: H - padB + 14, "text-anchor": "middle" }, String(c.decile)));
    });
    const fig = $("#calib");
    fig.innerHTML = `<p class="key"><span><i style="background:#a9aea4"></i>predicted</span><span><i style="background:#c8431f"></i>observed</span><span>x axis: risk tenth</span></p>`;
    fig.appendChild(svg);
  }
})();
