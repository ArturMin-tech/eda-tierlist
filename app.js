// Тир-лист еды. Каталог — products.json (его ведёт Claude),
// оценки — tiers.json (его коммитит этот сайт через GitHub API).

const TIERS = [
  { id: "S", color: "#ff7f7f" },
  { id: "A", color: "#ffbf7f" },
  { id: "B", color: "#ffdf7f" },
  { id: "C", color: "#bfff7f" },
  { id: "D", color: "#7fbfff" },
  { id: "F", color: "#bf7fff" },
];

const LS = { draft: "eda-tiers-draft", token: "eda-gh-token", repo: "eda-gh-repo" };

const $ = (id) => document.getElementById(id);
let products = new Map();
let dirty = false;
let dragging = false;
let currentId = null;

// localStorage может быть недоступен (приватный режим) — не падаем.
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  del(k) { try { localStorage.removeItem(k); } catch {} },
};

function repo() {
  const saved = store.get(LS.repo);
  if (saved) return saved;
  // На GitHub Pages адрес вида owner.github.io/repo/
  const m = location.hostname.match(/^([^.]+)\.github\.io$/);
  const name = location.pathname.split("/").filter(Boolean)[0];
  return m && name ? `${m[1]}/${name}` : "";
}

const b64decode = (s) =>
  new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g, "")), (c) => c.charCodeAt(0)));
const b64encode = (s) => {
  const bytes = new TextEncoder().encode(s);
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin);
};

function ghHeaders() {
  const h = { Accept: "application/vnd.github+json" };
  const token = store.get(LS.token);
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

async function fetchRemoteTiers() {
  const r = repo();
  if (r) {
    // API отдаёт свежую версию сразу после коммита, а Pages обновляется с задержкой.
    try {
      const res = await fetch(`https://api.github.com/repos/${r}/contents/tiers.json`, {
        headers: ghHeaders(),
        cache: "no-store",
      });
      if (res.ok) return JSON.parse(b64decode((await res.json()).content));
    } catch {}
  }
  const res = await fetch(`tiers.json?t=${Date.now()}`, { cache: "no-store" });
  return res.ok ? res.json() : { tiers: {} };
}

function emptyTiers() {
  return Object.fromEntries(TIERS.map((t) => [t.id, []]));
}

function readBoard() {
  const tiers = emptyTiers();
  document.querySelectorAll(".tier .items").forEach((el) => {
    tiers[el.dataset.tier] = [...el.children].map((c) => c.dataset.id);
  });
  return tiers;
}

function setStatus(text, cls = "") {
  const el = $("status");
  el.textContent = text;
  el.className = `status ${cls}`;
}

function markDirty() {
  dirty = true;
  store.set(LS.draft, JSON.stringify(readBoard()));
  setStatus("● есть несохранённые изменения", "dirty");
  updatePoolCount();
}

function toast(text, isError = false) {
  const el = $("toast");
  el.textContent = text;
  el.className = `toast show${isError ? " error" : ""}`;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (el.className = "toast"), 3500);
}

function updatePoolCount() {
  $("poolCount").textContent = $("pool").children.length;
}

function makeCard(p) {
  const el = document.createElement("div");
  el.className = "card";
  el.dataset.id = p.id;
  el.title = p.name;
  const img = document.createElement("img");
  img.src = p.image_hd || p.image;
  img.alt = p.name;
  img.loading = "lazy";
  el.append(img);
  el.addEventListener("click", () => !dragging && openSheet(p.id));
  return el;
}

function render(tiers) {
  const board = $("board");
  board.innerHTML = "";
  const placed = new Set();

  for (const t of TIERS) {
    const row = document.createElement("div");
    row.className = "tier";
    const label = document.createElement("div");
    label.className = "tier-label";
    label.style.background = t.color;
    label.textContent = t.id;
    const items = document.createElement("div");
    items.className = "items";
    items.dataset.tier = t.id;
    for (const id of tiers[t.id] || []) {
      if (products.has(id) && !placed.has(id)) {
        items.append(makeCard(products.get(id)));
        placed.add(id);
      }
    }
    row.append(label, items);
    board.append(row);
  }

  const pool = $("pool");
  pool.innerHTML = "";
  for (const p of products.values()) if (!placed.has(p.id)) pool.append(makeCard(p));
  updatePoolCount();

  document.querySelectorAll(".items").forEach((el) =>
    Sortable.create(el, {
      group: "tiers",
      animation: 150,
      delay: 120,
      delayOnTouchOnly: true,
      onStart: () => (dragging = true),
      onEnd: () => {
        setTimeout(() => (dragging = false), 50);
        markDirty();
      },
    })
  );
}

function containerOf(id) {
  return document.querySelector(`.card[data-id="${CSS.escape(id)}"]`)?.parentElement;
}

function openSheet(id) {
  const p = products.get(id);
  currentId = id;
  $("sheetImg").src = p.image_hd || p.image;
  $("sheetName").textContent = p.name;
  $("sheetPrice").innerHTML = "";
  $("sheetPrice").append(`$${p.price.toFixed(2)}`);
  if (p.old_price) {
    const s = document.createElement("s");
    s.textContent = `$${p.old_price.toFixed(2)}`;
    $("sheetPrice").append(s);
  }
  const current = containerOf(id)?.dataset.tier || "";
  const box = $("sheetTiers");
  box.innerHTML = "";
  for (const t of TIERS) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = t.id;
    b.style.background = t.color;
    if (t.id === current) b.classList.add("current");
    b.onclick = () => moveTo(t.id);
    box.append(b);
  }
  const un = document.createElement("button");
  un.type = "button";
  un.className = "unrank";
  un.textContent = "Убрать в «Не оценено»";
  un.onclick = () => moveTo("");
  box.append(un);
  $("sheet").showModal();
}

function moveTo(tier) {
  const card = document.querySelector(`.card[data-id="${CSS.escape(currentId)}"]`);
  const target = tier ? document.querySelector(`.tier .items[data-tier="${tier}"]`) : $("pool");
  target.append(card);
  $("sheet").close();
  markDirty();
}

async function save() {
  const r = repo();
  const token = store.get(LS.token);
  if (!r || !token) {
    openSettings();
    return;
  }
  const btn = $("saveBtn");
  btn.disabled = true;
  setStatus("сохраняю…");
  try {
    const url = `https://api.github.com/repos/${r}/contents/tiers.json`;
    const head = await fetch(url, { headers: ghHeaders(), cache: "no-store" });
    const sha = head.ok ? (await head.json()).sha : undefined;
    const body = {
      updated: new Date().toISOString(),
      tiers: readBoard(),
    };
    const res = await fetch(url, {
      method: "PUT",
      headers: { ...ghHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({
        message: "Update tier ratings",
        content: b64encode(JSON.stringify(body, null, 2) + "\n"),
        sha,
      }),
    });
    if (!res.ok) throw new Error(`${res.status} ${(await res.json()).message || ""}`);
    dirty = false;
    store.del(LS.draft);
    setStatus("✓ сохранено", "saved");
    toast("Оценки сохранены в GitHub");
  } catch (e) {
    setStatus("● есть несохранённые изменения", "dirty");
    toast(`Не удалось сохранить: ${e.message}`, true);
  } finally {
    btn.disabled = false;
  }
}

function openSettings() {
  $("repoInput").value = repo();
  $("tokenInput").value = store.get(LS.token) || "";
  $("settings").showModal();
}

$("settings").addEventListener("close", () => {
  if ($("settings").returnValue !== "ok") return;
  const r = $("repoInput").value.trim();
  const t = $("tokenInput").value.trim();
  r ? store.set(LS.repo, r) : store.del(LS.repo);
  t ? store.set(LS.token, t) : store.del(LS.token);
  toast("Настройки сохранены");
});

$("saveBtn").addEventListener("click", save);
$("settingsBtn").addEventListener("click", openSettings);
window.addEventListener("beforeunload", (e) => {
  if (dirty) e.preventDefault();
});

async function init() {
  const list = await (await fetch(`products.json?t=${Date.now()}`, { cache: "no-store" })).json();
  products = new Map(list.map((p) => [p.id, p]));

  // Несохранённый черновик в этом браузере важнее версии из репозитория.
  const draft = store.get(LS.draft);
  if (draft) {
    render(JSON.parse(draft));
    dirty = true;
    setStatus("● есть несохранённые изменения", "dirty");
    return;
  }
  const remote = await fetchRemoteTiers();
  render({ ...emptyTiers(), ...(remote.tiers || {}) });
  setStatus(remote.updated ? `обновлено ${new Date(remote.updated).toLocaleDateString("ru")}` : "");
}

init().catch((e) => toast(`Ошибка загрузки: ${e.message}`, true));
