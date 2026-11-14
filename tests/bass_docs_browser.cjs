// Drives the Bass Documents sheet (bass_ui_docs.py) in a real headless browser on the in-page simulator: no network, no key, no proxy.
// node bass_docs_browser.cjs <page.html> <shots dir or ""> [chromium|webkit]   -> prints one JSON line {ok, checks:[...]}
const { chromium, webkit } = require("playwright");
const [page_, shots, which] = process.argv.slice(2);
const checks = [];
const ok = (name, cond, extra) => checks.push({ name, ok: !!cond, extra: extra === undefined ? null : extra });

(async () => {
  const kind = which === "webkit" ? webkit : chromium;
  const browser = await kind.launch();
  const ctx = await browser.newContext({ viewport: { width: 1180, height: 760 } });
  const p = await ctx.newPage();
  const errors = [];
  p.on("pageerror", (e) => errors.push(String(e)));
  p.on("request", (r) => { if (!r.url().startsWith("file:")) errors.push("network: " + r.url()); });
  const url = "file://" + page_;
  const go = async (state, w, h) => {
    await p.setViewportSize({ width: w || 1180, height: h || 760 });
    await p.goto("about:blank");                                 // a fresh document: the simulator's library starts from its demo state
    await p.goto(url + "#bass=" + state);
    await p.waitForFunction(() => window._altoBass);
    await p.evaluate((s) => window._altoBass.dev(s), state);
    await p.waitForTimeout(250);
  };
  const shot = async (name) => { if (shots) await p.screenshot({ path: shots + "/" + name + ".png" }); };
  const text = () => p.evaluate(() => document.getElementById("bass-root").innerText);

  // the sheet: classes, outlines with the class count reaching them, groups, the chosen class's files, caps, Anthropic line
  await go("docs");
  let t = await text();
  ok("sheet lists classes and groups", /Classes[\s\S]*Torts[\s\S]*Contracts[\s\S]*Groups[\s\S]*Midterm prep/i.test(t));
  ok("outlines under the class show +3", /Torts outline\s*\+3/.test(t) && /Torts timeline\s*\+3/.test(t), t.slice(0, 300));
  ok("files of Torts with 'Bass is using this'", (t.match(/Bass is using this/g) || []).length === 3);
  ok("caps line (no pictures in the beta, D4)", /PDF, Word, text · 7 of 20 files used/.test(t) && !/pictures/i.test(t) && !(await p.$eval("#bs-dfile", (i) => /png|jpe?g|webp|heic/.test(i.accept))));
  ok("Anthropic line + Privacy Policy", /The text of a document goes to Anthropic when Bass uses it\.\s*Privacy Policy/.test(t));
  ok("switches are real switches", await p.$$eval('.bs-dsheet [role="switch"]', (a) => a.length === 3 && a.every((b) => b.getAttribute("aria-checked") === "true")));
  ok("touch targets >= 40px", await p.$$eval(".bs-sc, .bs-dsheet .bs-btn, .bs-dsheet .bs-ib", (a) => a.filter((b) => b.offsetParent).every((b) => b.getBoundingClientRect().height >= 36)));
  await shot("docs-class-desktop");

  // switching one off changes what Bass uses; the outline's "Using" follows
  await p.click('[data-a="d-use"][data-v="d2"]'); await p.waitForTimeout(200);
  ok("switch off reads Not used", /Not used/.test(await text()));
  let u = await p.evaluate(() => window._altoBass.call("docs", { op: "using", scope_id: "tol" }));
  ok("outline uses the 2 class files left", u.label === "Using: Torts outline, 2 documents", u.label);
  await p.click('[data-a="d-use"][data-v="d2"]'); await p.waitForTimeout(200);

  // the outline: own explanation, the per-outline class switch
  await p.click('[data-a="d-sel"][data-v="tol"]'); await p.waitForTimeout(150);
  t = await text();
  ok("outline explanation", /Bass uses these only in this outline, plus the Torts class documents\./.test(t));
  ok("class-documents switch row", /Also use the Torts class documents\s*3 files shared with every Torts outline and timeline/.test(t));
  await shot("docs-outline-desktop");
  await p.click('[data-a="d-cls"][data-v="tol"]'); await p.waitForTimeout(250);
  u = await p.evaluate(() => window._altoBass.call("docs", { op: "using", scope_id: "tol" }));
  ok("off switch: the outline uses none of the class files", u.files.length === 0 && /Torts outline\s*\n?\s*Torts timeline\s*\+3/.test(await text()), u.label);
  u = await p.evaluate(() => window._altoBass.call("docs", { op: "using", scope_id: "tot" }));
  ok("the other outline keeps them", u.files.length === 3);
  await p.click('[data-a="d-cls"][data-v="tol"]'); await p.waitForTimeout(200);

  // other classes never see Torts files
  u = await p.evaluate(() => window._altoBass.call("docs", { op: "using", scope_id: "con" }));
  ok("Contracts uses only its own", u.files.map((f) => f.id).join() === "d4,d5", u.files.map((f) => f.id).join());

  // new class, rename, move, delete, restore
  await p.click('[data-a="d-new"]'); await p.waitForTimeout(100);
  await p.fill(".bs-dnav .bs-dnn", "Evidence"); await p.click('.bs-dnav [data-a="d-newok"]'); await p.waitForTimeout(250);
  t = await text();
  ok("new class appears and is selected", /Evidence[\s\S]*No documents here yet/.test(t) && await p.$eval(".bs-sc.sel", (b) => b.innerText.includes("Evidence")));
  await p.click('[data-a="d-sel"][data-v="tor"]'); await p.waitForTimeout(150);
  await p.click('[data-a="d-menu"][data-v="d2"]'); await p.waitForTimeout(100);
  await shot("docs-menu-desktop");
  await p.fill("#bs-dfn", "Lin feedback.docx"); await p.click('[data-a="d-ren"][data-v="d2"]'); await p.waitForTimeout(250);
  ok("rename", /Lin feedback\.docx/.test(await text()));
  await p.click('[data-a="d-menu"][data-v="d2"]'); await p.waitForTimeout(100);
  await p.selectOption('select[data-a="d-mv"][data-v="d2"]', { label: "Midterm prep" }); await p.waitForTimeout(300);
  ok("move out of Torts", !/Lin feedback\.docx/.test(await text()));
  await p.click('[data-a="d-menu"][data-v="d1"]'); await p.waitForTimeout(100);
  await p.click('[data-a="d-del"][data-v="d1"]'); await p.waitForTimeout(250);
  t = await text();
  ok("delete goes to Recently deleted with 7 days", /Recently deleted[\s\S]*Midterm 2, graded\.pdf[\s\S]*Gone for good in 7 days/i.test(t));
  await shot("docs-deleted-desktop");
  await p.click('[data-a="d-res"][data-v="d1"]'); await p.waitForTimeout(250);
  ok("restore", !/Recently deleted/i.test(await text()) && (await text()).includes("Midterm 2, graded.pdf"));

  // upload a text file through the real file input
  await p.setInputFiles("#bs-dfile", { name: "Week 9.txt", mimeType: "text/plain", buffer: Buffer.from("Res ipsa loquitur") });
  await p.waitForTimeout(400);
  ok("upload adds the file to the chosen class", /Week 9\.txt[\s\S]*Bass is using this/.test(await text()));
  await p.setInputFiles("#bs-dfile", { name: "virus.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ") });
  await p.waitForTimeout(400);
  ok("unsupported type: friendly message", /Bass can read PDF, Word \(\.docx\) and plain-text files/.test(await text()));

  // the edit panel: Using line, chips, the cross switches one off for here, + Add opens the sheet
  await go("using");
  t = await text();
  ok("Using: Torts outline, 3 documents", /Using:\s*Torts outline, 3 documents/.test(t), t.slice(0, 200));
  await shot("using-panel-desktop");
  await p.click('[data-a="d-uoff"][data-v="d1"]'); await p.waitForTimeout(300);
  ok("panel header keeps its close button inside", await p.$eval('.bs-panel [data-a="close"]', (b) => { const r = b.getBoundingClientRect(), q = b.closest(".bs-panel").getBoundingClientRect(); return r.right <= q.right; }));
  ok("the cross switches one off here", /Using:\s*Torts outline, 2 documents/.test(await text()));
  await p.click('.bs-using [data-a="d-open"]'); await p.waitForTimeout(250);
  ok("+ Add opens the sheet on the outline with Use here", await p.$eval(".bs-sc.sel", (b) => b.innerText.includes("Torts outline")) && /Bass uses these here/.test(await text()));
  // phone: one column, picker on top, no horizontal scroll
  await go("docs", 390, 844);
  ok("phone: picker shown, nav hidden", await p.evaluate(() => getComputedStyle(document.querySelector(".bs-dpick")).display !== "none" && getComputedStyle(document.querySelector(".bs-dnav")).display === "none"));
  ok("phone: targets >= 44px", await p.$$eval(".bs-dsheet .bs-btn, .bs-dsheet .bs-ib, .bs-dpick", (a) => a.filter((b) => b.offsetParent).every((b) => b.getBoundingClientRect().height >= 44)));
  ok("phone: every file row contains its switch and menu button", await p.$$eval(".bs-drow", (a) => a.every((r) => { const q = r.getBoundingClientRect(); return [...r.querySelectorAll(".bs-sw, .bs-more")].every((e) => { const b = e.getBoundingClientRect(); return b.top >= q.top - 0.5 && b.bottom <= q.bottom + 0.5; }); })));
  ok("phone: the switch and the menu button never overlap", await p.$$eval(".bs-drow", (a) => a.every((r) => { const s = r.querySelector(".bs-sw"), m = r.querySelector(".bs-more"); if (!s || !m) return true; const x = s.getBoundingClientRect(), y = m.getBoundingClientRect(); return x.bottom <= y.top || y.bottom <= x.top || x.right <= y.left || y.right <= x.left; })));
  ok("phone: no horizontal scroll", await p.evaluate(() => { const s = document.querySelector(".bs-dmain"); return s.scrollWidth <= s.clientWidth + 1; }));
  await shot("docs-phone");
  await p.selectOption(".bs-dpick", "tol"); await p.waitForTimeout(200);
  ok("phone: picking the outline shows its switch", /Also use the Torts class documents/.test(await text()));
  await shot("docs-outline-phone");
  // dark theme
  await p.emulateMedia({ colorScheme: "dark" });
  await go("docs");
  await p.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
  await shot("docs-class-dark");

  ok("no page errors and no network", errors.length === 0, errors);
  await browser.close();
  console.log(JSON.stringify({ ok: checks.every((c) => c.ok), checks }));
})().catch((e) => { console.log(JSON.stringify({ ok: false, error: String(e && e.stack || e), checks })); process.exit(0); });
