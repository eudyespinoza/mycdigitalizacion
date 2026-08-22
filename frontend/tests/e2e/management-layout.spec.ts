import { expect, test } from "@playwright/test";


const routes = [
  ["/gestion", "Todo lo importante, en un solo lugar"],
  ["/gestion/catalogo", "Productos"],
  ["/gestion/inventario", "Inventario"],
  ["/gestion/pedidos", "Pedidos"],
  ["/gestion/clientes", "Personas y empresas"],
  ["/gestion/contenido", "Landing y campañas"],
  ["/gestion/promociones", "Promociones y cupones"],
  ["/gestion/envios", "Envíos y embalajes"],
  ["/gestion/integraciones", "Integraciones"],
  ["/gestion/usuarios", "Usuarios y permisos"],
  ["/gestion/auditoria", "Auditoría"],
  ["/gestion/configuracion", "Configuración general"],
] as const;


test("all management menus preserve a compact, usable shell", async ({ page }, testInfo) => {
  for (const [route, heading] of routes) {
    await page.goto(route);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1), route).toBe(true);
  }

  await page.goto("/gestion/configuracion");
  if (["360", "768"].includes(testInfo.project.name)) {
    const menu = page.getByRole("button", { name: "Configuración" });
    await expect(menu).toBeVisible();
    await menu.click();
    await expect(page.getByRole("navigation", { name: "Gestión de la tienda" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Configuración" })).toHaveAttribute("aria-current", "page");
    await menu.click();
  } else {
    await expect(page.getByRole("link", { name: "Configuración" })).toHaveAttribute("aria-current", "page");
  }
  const metrics = await page.evaluate(() => {
    const sidebar = document.querySelector<HTMLElement>(".management-sidebar");
    const main = document.querySelector<HTMLElement>(".management-main");
    const title = document.querySelector<HTMLElement>(".management-page-header h1");
    const section = document.querySelector<HTMLElement>(".management-form-section");
    const content = document.querySelector<HTMLElement>(".management-content-gap");
    const style = (node: HTMLElement | null) => node ? getComputedStyle(node) : null;
    return {
      sidebarWidth: sidebar?.getBoundingClientRect().width ?? 0,
      mainPadding: Number.parseFloat(style(main)?.paddingInlineStart ?? "0"),
      titleSize: Number.parseFloat(style(title)?.fontSize ?? "0"),
      sectionPadding: Number.parseFloat(style(section)?.paddingInlineStart ?? "0"),
      contentGap: Number.parseFloat(style(content)?.marginTop ?? "0"),
    };
  });

  if (testInfo.project.name === "1440") {
    expect(metrics.sidebarWidth).toBeLessThanOrEqual(240);
    expect(metrics.mainPadding).toBeLessThanOrEqual(40);
    expect(metrics.titleSize).toBeLessThanOrEqual(46);
    expect(metrics.sectionPadding).toBeLessThanOrEqual(22);
    expect(metrics.contentGap).toBeLessThanOrEqual(24);
  }
  if (testInfo.project.name === "1024") {
    expect(metrics.sidebarWidth).toBeLessThanOrEqual(220);
    expect(metrics.mainPadding).toBeLessThanOrEqual(28);
    expect(metrics.titleSize).toBeLessThanOrEqual(44);
  }

  await page.goto("/gestion/promociones");
  await page.screenshot({ path: `../.impeccable/review/management-${testInfo.project.name}.png`, fullPage: true });
});


test("operational layouts reflow before the sidebar squeezes their fields", async ({ page }, testInfo) => {
  await page.goto("/gestion/promociones");
  const columns = await page.locator(".promotion-management-grid").evaluate((node) => getComputedStyle(node).gridTemplateColumns.split(" ").length);
  if (["768", "1024"].includes(testInfo.project.name)) expect(columns).toBe(1);
  const checkboxAlignment = await page.locator(".promotion-management-grid .management-check").evaluateAll((labels) => labels.map((label) => {
    const input = label.querySelector("input")?.getBoundingClientRect();
    const copy = label.querySelector("span")?.getBoundingClientRect();
    return input && copy ? {
      centerDelta: Math.abs((input.top + input.height / 2) - (copy.top + copy.height / 2)),
      horizontal: input.right <= copy.left,
    } : null;
  }).filter(Boolean));
  expect(checkboxAlignment.length).toBeGreaterThan(0);
  for (const alignment of checkboxAlignment) {
    expect(alignment?.centerDelta).toBeLessThanOrEqual(2);
    expect(alignment?.horizontal).toBe(true);
  }

  await page.goto("/gestion/inventario");
  await page.getByRole("button", { name: /Ajustar stock/ }).click();
  const dialog = page.getByRole("form", { name: /Ajustar stock/ });
  await expect(dialog).toBeVisible();
  const dialogSafety = await dialog.evaluate((node) => {
    const layer = node.parentElement as HTMLElement;
    const layerStyle = getComputedStyle(layer);
    const dialogStyle = getComputedStyle(node);
    return {
      layerOverflow: layerStyle.overflowY,
      maxHeight: dialogStyle.maxHeight,
      overflow: dialogStyle.overflowY,
    };
  });
  expect(["auto", "scroll"]).toContain(dialogSafety.layerOverflow);
  expect(dialogSafety.maxHeight).not.toBe("none");
  expect(["auto", "scroll"]).toContain(dialogSafety.overflow);
});


test("the management menu scrolls independently on short laptop screens", async ({ page }) => {
  test.setTimeout(90_000);
  await page.setViewportSize({ width: 1366, height: 600 });
  await page.goto("/gestion", { waitUntil: "domcontentloaded" });

  const metrics = await page.evaluate(() => {
    const sidebar = document.querySelector<HTMLElement>(".management-sidebar");
    const nav = document.querySelector<HTMLElement>(".management-nav");
    const user = document.querySelector<HTMLElement>(".management-user");
    const navStyle = nav ? getComputedStyle(nav) : null;
    return {
      navClientHeight: nav?.clientHeight ?? 0,
      navScrollHeight: nav?.scrollHeight ?? 0,
      navOverflow: navStyle?.overflowY ?? "",
      sidebarBottom: sidebar?.getBoundingClientRect().bottom ?? 0,
      userBottom: user?.getBoundingClientRect().bottom ?? 0,
    };
  });

  expect(["auto", "scroll"]).toContain(metrics.navOverflow);
  expect(metrics.navScrollHeight).toBeGreaterThan(metrics.navClientHeight);
  expect(metrics.sidebarBottom).toBeLessThanOrEqual(600);
  expect(metrics.userBottom).toBeLessThanOrEqual(600);

  const settings = page.getByRole("link", { name: "Configuración" });
  await settings.scrollIntoViewIfNeeded();
  await expect(settings).toBeVisible();
  await expect(page.getByText("visual-admin@example.test")).toBeVisible();
});


test("Mercado Pago se conecta desde un único botón", async ({ page }) => {
  await page.route("https://auth.mercadopago.com/**", async (route) => {
    await route.fulfill({
      body: "<main><h1>Confirmar conexion con Mercado Pago</h1></main>",
      contentType: "text/html; charset=utf-8",
      status: 200,
    });
  });
  await page.goto("/gestion/integraciones/mercadopago");

  await expect(page.getByRole("heading", { level: 1, name: "Mercado Pago" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Conectar Mercado Pago" })).toBeVisible();
  await expect(page.getByText(/access token/i)).toHaveCount(0);
  await page.getByRole("button", { name: "Conectar Mercado Pago" }).click();

  await expect(page.getByRole("heading", { name: "Confirmar conexion con Mercado Pago" })).toBeVisible();
});
