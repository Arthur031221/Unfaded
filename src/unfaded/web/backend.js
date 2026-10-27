// Two interchangeable backends. Live talks to the local server. Demo reads precomputed files, so the
// GitHub Pages site works without a GPU and shows real output of the same pipeline.

async function json(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* body was not JSON */ }
    throw new Error(detail);
  }
  return res.json();
}

export class LiveBackend {
  constructor() { this.kind = "live"; this.sid = null; this.stamp = 0; }

  async info() { return json(await fetch("api/info")); }

  async upload(file) {
    const body = new FormData();
    body.append("file", file);
    const session = await json(await fetch("api/session", { method: "POST", body }));
    this.sid = session.id;
    session.sourceUrl = `api/session/${this.sid}/source.jpg`;
    return session;
  }

  async run(params) {
    const result = await json(await fetch(`api/session/${this.sid}/run`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(params),
    }));
    this.stamp += 1;
    return result;
  }

  async progress() { return json(await fetch(`api/session/${this.sid}/progress`)); }

  original(photo) { return `api/session/${this.sid}/photo/${photo.index}/original.jpg?v=${this.stamp}`; }

  step(photo, step, kind = "result") {
    const q = kind === "changes" ? "&heat=true" : kind === "invented" ? "&invented=true" : "";
    return `api/session/${this.sid}/photo/${photo.index}/step/${step.name}.jpg?v=${this.stamp}${q}`;
  }

  maskUrl(photo) { return `api/session/${this.sid}/photo/${photo.index}/mask.png?v=${this.stamp}`; }

  async putMask(photo, blob) {
    await json(await fetch(`api/session/${this.sid}/photo/${photo.index}/mask`, { method: "PUT", body: blob }));
  }

  async clearMask(photo) {
    await json(await fetch(`api/session/${this.sid}/photo/${photo.index}/mask`, { method: "DELETE" }));
  }

  downloadUrl(photo) { return `api/session/${this.sid}/photo/${photo.index}/download.jpg`; }
  downloadAllUrl() { return `api/session/${this.sid}/download.zip`; }
}

export class DemoBackend {
  constructor(index, base) {
    this.kind = "demo";
    this.index = index;
    this.base = base;
    this.example = null;
  }

  static async load(base = "demo/") {
    const index = await json(await fetch(`${base}index.json`));
    return new DemoBackend(index, base);
  }

  url(path) { return path ? this.base + path : null; }

  async info() {
    return { version: this.index.version, device: this.index.device, steps: this.index.steps, models: [] };
  }

  async open(id) {
    this.example = this.index.examples.find((e) => e.id === id);
    const e = this.example;
    return { id, name: e.name, width: e.width, height: e.height, quads: e.quads, note: e.note, sourceUrl: this.url(e.source) };
  }

  async run() {
    const e = this.example;
    return {
      seconds: e.seconds, note: e.note,
      photos: e.photos.map((p, index) => ({ ...p, index, has_mask: !!p.mask })),
    };
  }

  async progress() { return { state: "idle" }; }
  original(photo) { return this.url(this.example.photos[photo.index].original_url); }

  step(photo, step, kind = "result") {
    const key = kind === "changes" ? "heat" : kind === "invented" ? "inv" : "image";
    return this.url(step[key] || step.image);
  }

  fullFaces(photo) { return this.url(this.example.photos[photo.index].faces_full); }
  maskUrl(photo) { return this.url(this.example.photos[photo.index].mask); }
  async putMask() { throw new Error("demo"); }
  async clearMask() { throw new Error("demo"); }
  downloadUrl(photo) { return this.url(this.example.photos[photo.index].steps.at(-1).image); }
  downloadAllUrl() { return null; }
}
