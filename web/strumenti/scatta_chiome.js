// Playwright (browser_run_code_unsafe con filename): per ogni vista sfondo senza alberi, impostore, albero vero.
// Tinte di prova in window.__provaTinte (impostate prima) -> applicate con __chioma. Scrive in anteprime/alberi/taratura.
async (page) => {
  const DIR = 'C:/Users/sebas/Downloads/Quartiere_Mercato/anteprime/alberi/taratura/';
  const viste = [
    ['olivo_sud', 169.6, -162.7, 1.7, 0, 6],
    ['olivo_nord', 169.6, -138.7, 1.7, 180, 6],
    ['jacaranda_sud', 140.6, 107.2, 1.7, 0, 10],
    ['jacaranda_nord', 140.6, 137.2, 1.7, 180, 10],
  ];
  if (!(await page.evaluate(() => !!window.__tutto))) {
    await page.goto('http://localhost:5199/?bench');
    await page.waitForFunction(() => window.__tutto, null, { timeout: 180000 });
  }
  await page.bringToFront();
  const tinte = await page.evaluate(() => {
    window.__vento({ fermo: true }); window.__tempoVento(0);
    const t = window.__provaTinte || {};
    for (const [sp, c] of Object.entries(t)) window.__chioma(sp, c);
    return { island_tree_02: window.__chioma('island_tree_02'), jacaranda_tree: window.__chioma('jacaranda_tree') };
  });
  const alberi = (vis) => page.evaluate((vis) => window.__scena.traverse((o) => {
    if (/^(impostori|alberi):/.test(o.name)) o.visible = vis;
  }), vis);
  for (const [n, x, y, z, yaw, pitch] of viste) {
    await page.evaluate(([x, y, z, yaw, pitch]) => window.__vista(x, y, z, yaw, pitch, true), [x, y, z, yaw, pitch]);
    await alberi(false); await page.waitForTimeout(500);
    await page.screenshot({ path: DIR + n + '_sfondo.png' });
    await alberi(true);
    await page.evaluate(() => window.__distanzaAlberi(0.001)); await page.waitForTimeout(500);
    await page.screenshot({ path: DIR + n + '_imp.png' });
    await page.evaluate(() => window.__distanzaAlberi(30)); await page.waitForTimeout(500);
    await page.screenshot({ path: DIR + n + '_vero.png' });
  }
  return tinte;
}
