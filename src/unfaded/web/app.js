import { LANGUAGES, apply, detect, has, language, setLanguage, t } from "./i18n.js";
import { DemoBackend, LiveBackend } from "./backend.js";

const $ = (id) => document.getElementById(id);
const STEPS = ["split", "fade", "repair", "faces", "color", "upscale"];
const DEFAULT_ON = new Set(["split", "fade", "repair", "faces"]);
const NS = "http://www.w3.org/2000/svg";

const state = {
  backend: null,
  session: null,
  quads: [],
  turns: {},
  selected: 0,
  enabled: new Set(DEFAULT_ON),
  result: null,
  photo: 0,
  step: "all",
  view: "result",
  faceStrengths: {},
  masking: false,
  brush: "paint",
  zoom: { z: 1, x: 0, y: 0 },
  busy: false,
};

// ---------- setup ----------

async function boot() {
  const langSelect = $("lang");
  for (const [code, name] of Object.entries(LANGUAGES)) langSelect.add(new Option(name, code));
  const lang = detect();
  langSelect.value = lang;
  langSelect.addEventListener("change", async () => { await setLanguage(langSelect.value); renderAll(); });
  await setLanguage(lang);

  $("theme").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("unfaded.theme", next);
  });

  const params = new URLSearchParams(location.search);
  const wantDemo = params.has("demo") || document.body.dataset.demo === "1";
  try {
    if (wantDemo) throw new Error("demo requested");
    state.backend = new LiveBackend();
    const info = await state.backend.info();
    $("device").textContent = info.device;
    $("version").textContent = info.version;
  } catch {
    try {
      state.backend = await DemoBackend.load();
      const info = await state.backend.info();
      $("device").textContent = info.device;
      $("version").textContent = info.version;
      $("demo-banner").hidden = false;
      $("drop").hidden = true;
      $("examples-wrap").hidden = false;
      buildExamples();
    } catch (err) {
      $("status").textContent = err.message;
    }
  }
  buildStepList();
  wire();
  renderAll();
}

function buildExamples() {
  const box = $("examples");
  box.replaceChildren();
  for (const ex of state.backend.index.examples) {
    const b = document.createElement("button");
    b.className = "example";
    b.type = "button";
    const img = new Image();
    img.src = state.backend.url(ex.thumb);
    img.alt = "";
    const label = document.createElement("span");
    label.textContent = ex.name;
    b.append(img, label);
    b.addEventListener("click", () => openDemo(ex.id));
    box.append(b);
  }
}

function buildStepList() {
  const list = $("step-list");
  list.replaceChildren();
  const legend = document.createElement("legend");
  legend.className = "sr";
  legend.dataset.i18n = "controls.steps";
  list.append(legend);
  for (const name of STEPS) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = state.enabled.has(name);
    input.dataset.step = name;
    input.disabled = state.backend?.kind === "demo";
    input.addEventListener("change", () => {
      input.checked ? state.enabled.add(name) : state.enabled.delete(name);
      renderControls();
    });
    const text = document.createElement("span");
    const title = document.createElement("span");
    title.dataset.i18n = `steps.${name}`;
    const hint = document.createElement("small");
    hint.dataset.i18n = `steps.${name}.hint`;
    text.append(title, hint);
    label.append(input, text);
    list.append(label);
  }
}

function wire() {
  const drop = $("drop");
  const pick = () => $("file").click();
  $("browse").addEventListener("click", (e) => { e.stopPropagation(); pick(); });
  drop.addEventListener("click", pick);
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
  $("file").addEventListener("change", () => $("file").files[0] && openFile($("file").files[0]));
  for (const ev of ["dragenter", "dragover"]) drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); });
  for (const ev of ["dragleave", "drop"]) drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); });
  drop.addEventListener("drop", (e) => { const f = e.dataTransfer.files[0]; if (f) openFile(f); });
  window.addEventListener("paste", (e) => {
    const f = [...(e.clipboardData?.files || [])].find((x) => x.type.startsWith("image/"));
    if (f && state.backend.kind === "live") openFile(f);
  });

  $("face-strength").addEventListener("input", () => { $("face-out").textContent = $("face-strength").value; });
  $("face-strength").addEventListener("change", onFaceStrength);
  $("color-strength").addEventListener("input", () => { $("color-out").textContent = $("color-strength").value; });
  $("color-strength").addEventListener("change", () => state.backend.kind === "live" && state.result && rerun());
  $("scale").addEventListener("change", () => state.backend.kind === "live" && state.result && rerun());
  $("force-fade").addEventListener("change", () => state.backend.kind === "live" && state.result && rerun());
  $("run").addEventListener("click", () => rerun());
  $("new").addEventListener("click", reset);

  for (const tab of document.querySelectorAll("#mode-tabs button")) tab.addEventListener("click", () => setMode(tab.dataset.mode));
  $("add-quad").addEventListener("click", addQuad);
  $("remove-quad").addEventListener("click", removeQuad);
  $("rotate-quad").addEventListener("click", rotateQuad);

  for (const b of document.querySelectorAll("#view-seg button")) {
    b.addEventListener("click", () => { state.view = b.dataset.view; renderResult(); });
  }
  $("edit-mask").addEventListener("click", startMask);
  $("mask-cancel").addEventListener("click", stopMask);
  $("mask-apply").addEventListener("click", applyMask);
  $("mask-auto").addEventListener("click", async () => { await state.backend.clearMask(currentPhoto()); stopMask(); await rerun(); });
  for (const b of document.querySelectorAll("#brush-seg button")) {
    b.addEventListener("click", () => {
      state.brush = b.dataset.brush;
      document.querySelectorAll("#brush-seg button").forEach((x) => x.classList.toggle("on", x === b));
    });
  }
  wireCompare();
  wireMaskPaint();
}

// ---------- session ----------

async function openFile(file) {
  setStatus(t("status.reading"), true);
  try {
    const session = await state.backend.upload(file);
    startSession(session);
  } catch (err) {
    setStatus(err.message, false, true);
  }
}

async function openDemo(id) {
  const session = await state.backend.open(id);
  startSession(session);
  const result = await state.backend.run();
  state.result = result;
  state.step = "all";
  state.photo = 0;
  setMode("result");
  renderAll();
}

function startSession(session) {
  state.session = session;
  state.quads = session.quads.map((q) => ({ points: q.points.map((p) => [...p]), score: q.score }));
  state.turns = {};
  state.result = null;
  state.selected = 0;
  state.faceStrengths = {};
  state.photo = 0;
  state.step = "all";
  state.masking = false;
  $("landing").hidden = true;
  $("workspace").hidden = false;
  $("scan-img").src = session.sourceUrl;
  setStatus("");
  setMode("scan");
  renderAll();
}

function reset() {
  state.session = null;
  state.result = null;
  $("workspace").hidden = true;
  $("landing").hidden = false;
  $("file").value = "";
  setStatus("");
}

function setMode(mode) {
  const hasResult = !!state.result;
  if (mode === "result" && !hasResult) mode = "scan";
  state.mode = mode;
  $("scan-view").hidden = mode !== "scan";
  $("result-view").hidden = mode !== "result";
  document.querySelectorAll("#mode-tabs button").forEach((b) => {
    b.setAttribute("aria-selected", String(b.dataset.mode === mode));
    if (b.dataset.mode === "result") b.disabled = !hasResult;
  });
  if (mode === "result") renderResult();
  if (mode === "scan") renderScan();
}

function setStatus(text, busy = false, error = false) {
  const el = $("status");
  el.className = "status" + (error ? " error" : "");
  el.textContent = text;
  if (busy) { const bar = document.createElement("span"); bar.className = "bar"; el.append(bar); }
}

// ---------- running ----------

function params() {
  const steps = [...state.enabled];
  return {
    steps,
    face_strength: +$("face-strength").value,
    face_strengths: Object.fromEntries(Object.entries(state.faceStrengths).map(([k, v]) => [k, v])),
    color_strength: +$("color-strength").value,
    scale: +$("scale").value,
    quads: state.enabled.has("split") ? state.quads.map((q) => ({ points: q.points, score: q.score ?? 1 })) : [],
    quarter_turns: state.turns,
    force_fade: $("force-fade").checked,
  };
}

async function rerun() {
  if (state.busy || !state.session) return;
  state.busy = true;
  $("run").disabled = true;
  setStatus(t("status.working"), true);
  const timer = setInterval(async () => {
    try {
      const p = await state.backend.progress();
      if (p.state === "running" && p.step !== "start") {
        setStatus(t("status.step", { step: t(`steps.${p.step}`), n: (p.photo ?? 0) + 1 }), true);
      }
    } catch { /* progress is cosmetic */ }
  }, 350);
  try {
    const keepStep = state.step;
    const result = await state.backend.run(params());
    state.result = result;
    state.photo = Math.min(state.photo, result.photos.length - 1);
    state.step = result.photos[state.photo].steps.some((s) => s.name === keepStep) ? keepStep : "all";
    setStatus(t("status.done", { s: result.seconds.toFixed(1) }));
    setMode("result");
  } catch (err) {
    setStatus(err.message, false, true);
  } finally {
    clearInterval(timer);
    state.busy = false;
    $("run").disabled = false;
  }
}

function onFaceStrength() {
  const value = +$("face-strength").value;
  state.faceStrengths = {};
  if (state.backend.kind === "live") { if (state.result) rerun(); return; }
  state.demoFace = value;
  renderResult();
}

// ---------- scan view (outline editing) ----------

function renderScan() {
  const s = state.session;
  if (!s) return;
  const svg = $("scan-svg");
  svg.setAttribute("viewBox", `0 0 ${s.width} ${s.height}`);
  svg.replaceChildren();
  const r = Math.max(s.width, s.height) * 0.011;
  svg.style.setProperty("--hr", r);
  $("scan-note").textContent = state.quads.length ? t("scan.found", { n: state.quads.length }) : t("scan.none");
  state.quads.forEach((q, i) => {
    const poly = document.createElementNS(NS, "polygon");
    poly.setAttribute("points", q.points.map((p) => p.join(",")).join(" "));
    poly.setAttribute("class", "quad" + (i === state.selected ? " sel" : ""));
    poly.style.setProperty("--sw", 3);
    poly.style.pointerEvents = "all";
    poly.addEventListener("pointerdown", (e) => { state.selected = i; renderScan(); e.stopPropagation(); startDrag(e, i, null); });
    svg.append(poly);
    const cx = q.points.reduce((a, p) => a + p[0], 0) / 4;
    const cy = q.points.reduce((a, p) => a + p[1], 0) / 4;
    const label = document.createElementNS(NS, "text");
    label.setAttribute("x", cx); label.setAttribute("y", cy);
    label.setAttribute("class", "qlabel");
    label.setAttribute("font-size", r * 2.6);
    label.setAttribute("text-anchor", "middle");
    label.textContent = `${i + 1}${state.turns[i] ? " ↻" + state.turns[i] * 90 : ""}`;
    svg.append(label);
  });
  state.quads.forEach((q, i) => {
    q.points.forEach((p, k) => {
      const c = document.createElementNS(NS, "circle");
      c.setAttribute("cx", p[0]); c.setAttribute("cy", p[1]); c.setAttribute("r", r);
      c.setAttribute("class", "handle");
      c.style.pointerEvents = "all";
      c.addEventListener("pointerdown", (e) => { state.selected = i; e.stopPropagation(); startDrag(e, i, k); });
      svg.append(c);
    });
  });
}

function svgPoint(svg, e) {
  const pt = svg.createSVGPoint();
  pt.x = e.clientX; pt.y = e.clientY;
  return pt.matrixTransform(svg.getScreenCTM().inverse());
}

function startDrag(e, quadIndex, corner) {
  const svg = $("scan-svg");
  const s = state.session;
  const start = svgPoint(svg, e);
  const base = state.quads[quadIndex].points.map((p) => [...p]);
  const clamp = (v, hi) => Math.min(Math.max(v, 0), hi);
  const move = (ev) => {
    const p = svgPoint(svg, ev);
    const q = state.quads[quadIndex];
    if (corner === null) {
      const dx = p.x - start.x, dy = p.y - start.y;
      q.points = base.map(([x, y]) => [clamp(x + dx, s.width), clamp(y + dy, s.height)]);
    } else {
      q.points[corner] = [clamp(p.x, s.width), clamp(p.y, s.height)];
    }
    renderScan();
  };
  const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function addQuad() {
  const { width: w, height: h } = state.session;
  const m = 0.3;
  state.quads.push({ points: [[w * m, h * m], [w * (1 - m), h * m], [w * (1 - m), h * (1 - m)], [w * m, h * (1 - m)]], score: 1 });
  state.selected = state.quads.length - 1;
  renderScan();
}

function removeQuad() {
  if (!state.quads.length) return;
  state.quads.splice(state.selected, 1);
  const turns = {};
  Object.entries(state.turns).forEach(([k, v]) => { if (+k !== state.selected) turns[+k > state.selected ? +k - 1 : k] = v; });
  state.turns = turns;
  state.selected = Math.max(0, state.selected - 1);
  renderScan();
}

function rotateQuad() {
  if (!state.quads.length) return;
  state.turns[state.selected] = ((state.turns[state.selected] || 0) + 1) % 4;
  renderScan();
}

// ---------- result view ----------

const currentPhoto = () => state.result.photos[state.photo];
const currentStep = () => currentPhoto().steps.find((s) => s.name === state.step);

function renderResult() {
  if (!state.result) return;
  const photo = currentPhoto();
  const tabs = $("photo-tabs");
  tabs.replaceChildren();
  state.result.photos.forEach((p, i) => {
    const b = document.createElement("button");
    b.role = "tab";
    b.setAttribute("aria-selected", String(i === state.photo));
    b.textContent = t("result.photo", { n: i + 1 });
    b.addEventListener("click", () => { state.photo = i; state.step = "all"; state.masking = false; renderResult(); });
    tabs.append(b);
  });
  tabs.hidden = state.result.photos.length < 2;

  const bar = $("pipeline");
  bar.replaceChildren();
  const addChip = (name, title, badge, cls, onClick, pressed) => {
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip" + (cls ? " " + cls : "");
    b.setAttribute("aria-pressed", String(pressed));
    const strong = document.createElement("b");
    strong.textContent = title;
    b.append(strong);
    for (const [text, kind] of badge) {
      const el = document.createElement(kind ? "span" : "small");
      if (kind) el.className = `tagline-badge ${kind}`;
      el.textContent = text;
      b.append(el);
    }
    b.addEventListener("click", onClick);
    li.append(b);
    bar.append(li);
  };
  addChip("all", t("result.whole"), [[t("result.wholeHint"), null]], "", () => { state.step = "all"; state.masking = false; renderResult(); }, state.step === "all");
  for (const s of photo.steps) {
    const badge = [];
    if (s.skipped) badge.push([t("chip.skipped"), null]);
    else {
      badge.push([t("chip.changed", { p: s.changed_percent }), null]);
      badge.push([s.invented ? t("chip.invented") : t("chip.measured"), s.invented ? "invented" : "measured"]);
    }
    addChip(s.name, t(`steps.${s.name}`), badge, s.skipped ? "skipped" : "", () => { state.step = s.name; state.masking = false; renderResult(); }, state.step === s.name);
  }

  const step = state.step === "all" ? null : currentStep();
  const note = $("step-note");
  if (step && step.code && has(`note.${step.code}`)) note.textContent = t(`note.${step.code}`, step.detail || {});
  else if (step) note.textContent = t(`steps.${step.name}.hint`);
  else note.textContent = t("result.wholeNote", { s: state.result.seconds.toFixed(1) });

  document.querySelectorAll("#view-seg button").forEach((b) => {
    b.classList.toggle("on", b.dataset.view === state.view);
    b.disabled = !step && b.dataset.view !== "result";
  });
  $("edit-mask").hidden = !(photo.has_mask && state.backend.kind === "live");
  $("download").href = state.backend.downloadUrl(photo) || "#";
  const all = state.backend.downloadAllUrl();
  $("download-all").hidden = !all || state.result.photos.length < 2;
  if (all) $("download-all").href = all;

  renderImages(photo, step);
  renderFaces(photo);
  renderFaceList(photo);
  renderLegend(step);
  $("color-wrap").hidden = !state.enabled.has("color") && state.backend.kind === "live";
}

function renderImages(photo, step) {
  const be = state.backend;
  const before = $("img-before"), after = $("img-after");
  const view = step ? state.view : "result";
  const idx = step ? photo.steps.indexOf(step) : -1;
  let beforeUrl, afterUrl;
  if (state.masking) {
    const prev = photo.steps.find((s) => s.name === "fade");
    beforeUrl = afterUrl = prev ? be.step(photo, prev) : be.original(photo);
  } else if (!step) {
    beforeUrl = be.original(photo);
    afterUrl = be.step(photo, photo.steps.at(-1) || { name: "none" }) ;
    if (!photo.steps.length) afterUrl = beforeUrl;
  } else {
    beforeUrl = idx > 0 ? be.step(photo, photo.steps[idx - 1]) : be.original(photo);
    afterUrl = be.step(photo, step, view);
    if (view !== "result") beforeUrl = be.step(photo, step);
  }
  if (be.kind === "demo" && step?.name === "faces" && view === "result" && state.demoFace !== undefined && be.fullFaces(photo)) {
    crossfade(beforeUrl, be.fullFaces(photo), state.demoFace / 100).then((u) => { after.src = u; });
    before.src = beforeUrl;
  } else {
    before.src = beforeUrl;
    after.src = afterUrl;
  }
  $("divider").hidden = state.masking;
  $("img-after").style.visibility = state.masking ? "hidden" : "visible";
  document.querySelector(".tag.before").hidden = state.masking;
  document.querySelector(".tag.after").hidden = state.masking;
  $("split").hidden = state.masking;
}

const cache = new Map();
function loadImage(url) {
  if (!cache.has(url)) {
    cache.set(url, new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = url;
    }));
  }
  return cache.get(url);
}

async function crossfade(a, b, t01) {
  const [ia, ib] = await Promise.all([loadImage(a), loadImage(b)]);
  const c = document.createElement("canvas");
  c.width = ia.naturalWidth; c.height = ia.naturalHeight;
  const g = c.getContext("2d");
  g.drawImage(ia, 0, 0);
  g.globalAlpha = t01;
  g.drawImage(ib, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.9);
}

function renderFaces(photo) {
  const svg = $("face-svg");
  svg.replaceChildren();
  if (state.step !== "faces" || state.masking) return;
  const [w, h] = photo.original;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  photo.faces.forEach((f, i) => {
    const [x, y, bw, bh] = f.box;
    const r = document.createElementNS(NS, "rect");
    r.setAttribute("x", x); r.setAttribute("y", y); r.setAttribute("width", bw); r.setAttribute("height", bh);
    r.setAttribute("class", "face-box");
    const label = document.createElementNS(NS, "text");
    label.setAttribute("x", x + 4); label.setAttribute("y", y - 6);
    label.setAttribute("font-size", Math.max(14, w / 60));
    label.setAttribute("class", "face-num");
    label.textContent = String(i + 1);
    svg.append(r, label);
  });
}

function renderFaceList(photo) {
  const box = $("face-list");
  box.replaceChildren();
  if (state.backend.kind !== "live" || !photo.faces.length) return;
  photo.faces.forEach((f, i) => {
    const label = document.createElement("label");
    const name = document.createElement("span");
    name.textContent = t("faces.n", { n: i + 1 });
    const input = document.createElement("input");
    input.type = "range"; input.min = 0; input.max = 100; input.value = f.strength ?? 35;
    const out = document.createElement("output");
    out.textContent = `${input.value}%`;
    input.addEventListener("input", () => { out.textContent = `${input.value}%`; });
    input.addEventListener("change", () => {
      const list = state.faceStrengths[photo.index] || photo.faces.map((x) => x.strength ?? +$("face-strength").value);
      list[i] = +input.value;
      state.faceStrengths[photo.index] = list;
      state.step = "faces";
      rerun();
    });
    label.append(name, input, out);
    box.append(label);
  });
}

function renderLegend(step) {
  const el = $("legend");
  el.replaceChildren();
  const add = (color, text) => {
    const span = document.createElement("span");
    const i = document.createElement("i");
    i.style.background = color;
    span.append(i, document.createTextNode(text));
    el.append(span);
  };
  if (state.masking) { add("rgb(255,40,90)", t("mask.legend")); return; }
  if (step && state.view === "changes") add("#f1b43e", t("legend.changes"));
  else if (step && state.view === "invented") add("var(--invented)", t("legend.invented"));
  else el.append(document.createTextNode(t("legend.drag")));
}

// ---------- compare slider and zoom ----------

function setSplit(pct) {
  const v = Math.min(100, Math.max(0, pct));
  $("compare").style.setProperty("--pos", `${v}%`);
  $("split").value = v;
}

function applyZoom() {
  const { z, x, y } = state.zoom;
  const el = $("zoom");
  el.style.setProperty("--z", z);
  el.style.setProperty("--tx", `${x}px`);
  el.style.setProperty("--ty", `${y}px`);
}

function wireCompare() {
  const box = $("compare");
  $("split").addEventListener("input", () => setSplit(+$("split").value));
  let mode = null, last = null;
  box.addEventListener("pointerdown", (e) => {
    if (state.masking) return;
    const zr = $("zoom").getBoundingClientRect();
    const pos = ((e.clientX - zr.left) / zr.width) * 100;
    const near = Math.abs(e.clientX - (zr.left + (parseFloat(getComputedStyle(box).getPropertyValue("--pos")) / 100) * zr.width)) < 28;
    mode = state.zoom.z > 1 && !near ? "pan" : "split";
    last = [e.clientX, e.clientY];
    box.setPointerCapture(e.pointerId);
    if (mode === "split") setSplit(pos);
  });
  box.addEventListener("pointermove", (e) => {
    if (!mode) return;
    if (mode === "split") {
      const zr = $("zoom").getBoundingClientRect();
      setSplit(((e.clientX - zr.left) / zr.width) * 100);
    } else {
      state.zoom.x += e.clientX - last[0]; state.zoom.y += e.clientY - last[1];
      last = [e.clientX, e.clientY];
      clampPan(); applyZoom();
    }
  });
  const end = () => { mode = null; };
  box.addEventListener("pointerup", end);
  box.addEventListener("pointercancel", end);
  box.addEventListener("wheel", (e) => {
    e.preventDefault();
    const rect = box.getBoundingClientRect();
    const px = e.clientX - rect.left, py = e.clientY - rect.top;
    const old = state.zoom.z;
    const z = Math.min(8, Math.max(1, old * Math.exp(-e.deltaY * 0.0015)));
    state.zoom.x = px - ((px - state.zoom.x) / old) * z;
    state.zoom.y = py - ((py - state.zoom.y) / old) * z;
    state.zoom.z = z;
    clampPan(); applyZoom();
  }, { passive: false });
  box.addEventListener("dblclick", () => { state.zoom = { z: 1, x: 0, y: 0 }; applyZoom(); });
}

function clampPan() {
  const box = $("compare").getBoundingClientRect();
  const z = state.zoom.z;
  state.zoom.x = Math.min(0, Math.max(box.width - box.width * z, state.zoom.x));
  state.zoom.y = Math.min(0, Math.max(box.height - $("zoom").offsetHeight * z, state.zoom.y));
}

// ---------- mask editor ----------

async function startMask() {
  const photo = currentPhoto();
  state.masking = true;
  state.step = "repair";
  $("mask-tools").hidden = false;
  const canvas = $("mask-canvas");
  const img = await loadImage(state.backend.maskUrl(photo));
  canvas.width = img.naturalWidth; canvas.height = img.naturalHeight;
  const g = canvas.getContext("2d", { willReadFrequently: true });
  g.clearRect(0, 0, canvas.width, canvas.height);
  g.drawImage(img, 0, 0);
  const data = g.getImageData(0, 0, canvas.width, canvas.height);
  for (let i = 0; i < data.data.length; i += 4) {
    const on = data.data[i] > 127;
    data.data[i] = 255; data.data[i + 1] = 40; data.data[i + 2] = 90; data.data[i + 3] = on ? 255 : 0;
  }
  g.putImageData(data, 0, 0);
  canvas.hidden = false;
  renderResult();
}

function stopMask() {
  state.masking = false;
  $("mask-canvas").hidden = true;
  $("mask-tools").hidden = true;
  if (state.result) renderResult();
}

async function applyMask() {
  const canvas = $("mask-canvas");
  const g = canvas.getContext("2d", { willReadFrequently: true });
  const src = g.getImageData(0, 0, canvas.width, canvas.height);
  const out = new ImageData(canvas.width, canvas.height);
  for (let i = 0; i < src.data.length; i += 4) {
    const v = src.data[i + 3] > 127 ? 255 : 0;
    out.data[i] = out.data[i + 1] = out.data[i + 2] = v; out.data[i + 3] = 255;
  }
  const tmp = document.createElement("canvas");
  tmp.width = canvas.width; tmp.height = canvas.height;
  tmp.getContext("2d").putImageData(out, 0, 0);
  const blob = await new Promise((r) => tmp.toBlob(r, "image/png"));
  try {
    await state.backend.putMask(currentPhoto(), blob);
    stopMask();
    state.step = "repair";
    await rerun();
  } catch (err) {
    setStatus(err.message, false, true);
  }
}

function wireMaskPaint() {
  const canvas = $("mask-canvas");
  let drawing = false, prev = null;
  const point = (e) => {
    const r = canvas.getBoundingClientRect();
    return [((e.clientX - r.left) / r.width) * canvas.width, ((e.clientY - r.top) / r.height) * canvas.height, canvas.width / r.width];
  };
  const stroke = (e) => {
    const [x, y, k] = point(e);
    const g = canvas.getContext("2d");
    g.globalCompositeOperation = state.brush === "erase" ? "destination-out" : "source-over";
    g.strokeStyle = g.fillStyle = "rgb(255,40,90)";
    g.lineCap = "round";
    g.lineWidth = +$("brush-size").value * k;
    g.beginPath();
    g.moveTo(...(prev || [x, y]));
    g.lineTo(x, y);
    g.stroke();
    prev = [x, y];
  };
  canvas.addEventListener("pointerdown", (e) => { if (e.shiftKey) return; drawing = true; prev = null; canvas.setPointerCapture(e.pointerId); stroke(e); e.stopPropagation(); });
  canvas.addEventListener("pointermove", (e) => { if (drawing) stroke(e); });
  const end = () => { drawing = false; prev = null; };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
}

// ---------- rendering of static text ----------

function renderControls() {
  const demo = state.backend?.kind === "demo";
  document.querySelectorAll("#step-list input").forEach((i) => { i.checked = state.enabled.has(i.dataset.step); });
  $("run").hidden = demo;
  $("scale").disabled = demo;
  $("force-fade").disabled = demo;
  $("color-wrap").hidden = demo ? true : !state.enabled.has("color");
  $("face-strength").closest("label").hidden = false;
  apply(document);
}

function renderAll() {
  renderControls();
  if (state.session && state.mode === "scan") renderScan();
  if (state.result && state.mode === "result") renderResult();
  if (state.session) setMode(state.mode || "scan");
  document.title = `Unfaded · ${t("app.tagline")}`;
  void language;
}

boot();
