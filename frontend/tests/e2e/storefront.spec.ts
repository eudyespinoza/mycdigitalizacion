import { expect, test, type APIRequestContext } from "@playwright/test";

const control = (request: APIRequestContext, body: Record<string, unknown>) =>
  request.post("http://127.0.0.1:4010/__control", { data: body });

test.beforeEach(async ({ request }) => {
  await control(request, { reset: true });
});

test("responsive landing, optimized media, product and keyboard-safe cart drawer", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /todo lo que buscás/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Ideas para estudio y oficina" })).toBeVisible();
  const heroMedia = page.locator(".hero-media");
  await expect(heroMedia.locator("img")).toHaveCount(1);
  await expect(heroMedia.locator("picture source")).toHaveCount(1);
  expect(await heroMedia.locator("img").evaluate((image) => getComputedStyle(image).objectPosition)).toBe("58% 50%");
  const sparseCard = await page.locator(".home-grid.count-1 .product-card").boundingBox();
  expect(sparseCard?.width ?? 0).toBeGreaterThan(testInfo.project.name === "360" ? 300 : 520);
  await page.screenshot({ path: `../.impeccable/review/${testInfo.project.name}.png`, fullPage: true });
  if (testInfo.project.name === "1440") {
    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.screenshot({ path: "../.impeccable/review/hero-repro.png" });
  }
  await page.getByRole("link", { name: "Explorar catálogo" }).first().click();
  await expect(page.getByRole("heading", { name: "Todo el catálogo" })).toBeVisible();
  const productImage = page.getByRole("img", { name: /cuadernos y útiles/i }).first();
  await expect(productImage).toHaveAttribute("src", /_next\/image\?url=%2Fmedia%2F/);
  await page.getByRole("link", { name: "Ver Cuaderno A5" }).click();
  await expect(page.getByRole("heading", { name: "Cuaderno A5" })).toBeVisible();
  await page.getByRole("button", { name: "Agregar al carrito" }).click();
  const drawer = page.getByRole("dialog", { name: "Tu carrito" });
  await expect(drawer).toBeVisible();
  await expect(page.getByRole("button", { name: "Cerrar carrito" })).toBeFocused();
  await expect(drawer.getByRole("strong").filter({ hasText: "$" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect(page.getByRole("button", { name: "Agregar al carrito" })).toBeFocused();
});

test("registration sends the complete storefront profile and focuses the first invalid field", async ({ page, request }) => {
  await page.goto("/cuenta/registro");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page.getByLabel("Nombre")).toBeFocused();
  await page.getByLabel("Nombre").fill("Ana");
  await page.getByLabel("Apellido").fill("Pérez");
  await page.getByLabel("Teléfono").fill("11 5555-1234");
  await page.getByLabel("Email").fill("ana@example.com");
  await page.getByLabel("Contraseña").fill("Clave-segura-2026");
  await page.getByLabel(/Acepto la política/).check();
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page).toHaveURL(/\/cuenta\/verificar\?email=ana%40example.com/);
  const rows = await (await request.get("http://127.0.0.1:4010/__requests")).json();
  expect(rows).toContainEqual(expect.objectContaining({ method: "POST", path: "/api/v1/auth/register", csrf: "csrf-1", body: expect.objectContaining({ first_name: "Ana", last_name: "Pérez", phone: "11 5555-1234", email: "ana@example.com" }) }));
});

test("login rotates CSRF and profile persists the masked DNI before checkout", async ({ page, request }) => {
  await page.goto("/cuenta/ingresar");
  await page.getByLabel("Email").fill("cliente@example.com");
  await page.getByLabel("Contraseña").fill("Clave-segura-2026");
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByRole("heading", { name: "Mi cuenta" })).toBeVisible();
  await page.getByLabel("DNI").fill("30.125.678");
  await page.getByRole("button", { name: "Guardar perfil" }).click();
  await expect(page.getByText("DNI guardado: ••••5678")).toBeVisible();
  const rows = await (await request.get("http://127.0.0.1:4010/__requests")).json();
  expect(rows).toContainEqual(expect.objectContaining({ method: "POST", path: "/api/v1/auth/login", csrf: "csrf-1" }));
  expect(rows).toContainEqual(expect.objectContaining({ method: "PATCH", path: "/api/v1/customers/me", csrf: "csrf-2", body: expect.objectContaining({ dni: "30.125.678" }) }));
});

test("address workflow supports postal lookup, near confirmation and explicit far reverse choice", async ({ page, request }, testInfo) => {
  test.skip(!["360", "1024"].includes(testInfo.project.name), "Map path runs once per mobile/desktop interaction mode.");
  await page.goto("/cuenta/direcciones");
  await page.getByRole("button", { name: /Casa Av\. Corrientes/ }).click();
  await expect(page.getByText(/Esta dirección ya fue confirmada/)).toBeVisible();
  await page.getByLabel("CP o CPA").fill("1043");
  await page.getByRole("button", { name: "Buscar localidad" }).click();
  await expect(page.getByLabel("Localidad y provincia")).toHaveValue("CABA|CABA");
  await page.getByLabel("Calle").fill("Av. Corrientes");
  await page.getByLabel("Número").fill("1234");
  await page.getByRole("button", { name: "Guardar y ubicar" }).click();
  await page.getByRole("button", { name: "Confirmar esta dirección" }).click();
  await expect(page.getByText(/lista para cotizar/)).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: /lista para cotizar/ })).toBeFocused();
  await page.getByRole("button", { name: "Guardar y ubicar" }).click();
  await page.getByLabel("Latitud").fill("-34.6200000");
  await expect(page.getByText(/más de 150 metros/)).toBeVisible();
  await page.getByRole("button", { name: "Consultar dirección del punto" }).click();
  await expect(page.getByText(/Dirección encontrada:/)).toBeVisible();
  await page.getByRole("button", { name: "Usar dirección encontrada" }).click();
  await expect(page.getByText(/lista para cotizar/)).toBeVisible();
  const rows = await (await request.get("http://127.0.0.1:4010/__requests")).json();
  const confirms = rows.filter((row: { path: string }) => row.path.endsWith("/confirm"));
  expect(confirms).toEqual(expect.arrayContaining([
    expect.objectContaining({ body: { latitude: "-34.6037000", longitude: "-58.3816000", address_choice: "written" } }),
    expect.objectContaining({ body: { latitude: "-34.6200000", longitude: "-58.3816000", address_choice: "reverse" } }),
  ]));
});

test("mobile catalog sheet traps focus and server URL state produces removable chips", async ({ page }, testInfo) => {
  test.skip(!["360", "768"].includes(testInfo.project.name), "The catalog sheet is a mobile/tablet-only control.");
  await page.goto("/catalogo");
  const trigger = page.getByRole("button", { name: "Filtrar" });
  await trigger.click();
  await expect(page.getByRole("dialog", { name: "Filtros de catálogo" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Cerrar filtros" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await trigger.click();
  await page.getByLabel(/Sur \(1\)/).click();
  await expect(page).toHaveURL(/brand=sur/);
  await expect(page.getByRole("button", { name: /Marca: sur/ })).toBeVisible();
});

test("CMS failure is distinct from empty content and leaves catalog recovery available", async ({ page, request }) => {
  await control(request, { cmsError: true });
  await page.goto("/");
  await expect(page.getByRole("alert").filter({ hasText: "No pudimos cargar las novedades" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Explorar catálogo" })).toBeVisible();
});

test("checkout reviews authoritative data and stops at server pending review", async ({ page, request }) => {
  await page.goto("/producto/cuaderno-a5");
  await page.getByRole("button", { name: "Agregar al carrito" }).click();
  await expect(page.getByRole("dialog", { name: "Tu carrito" }).getByText("Cuaderno A5 · Azul")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.goto("/checkout");
  await page.getByRole("button", { name: "Revisar cuenta" }).click();
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByRole("button", { name: "Cotizar envío" }).click();
  await expect(page.getByRole("heading", { name: "Revisá antes de pagar" })).toBeVisible();
  await expect(page.getByText("Cuaderno A5 · Azul · 1")).toBeVisible();
  await expect(page.getByText("Av. Corrientes 1234, CABA")).toBeVisible();
  await expect(page.getByText("Cliente sintético de prueba")).toBeVisible();
  await page.getByRole("button", { name: "Ir a Mercado Pago" }).click();
  await expect(page.getByRole("heading", { name: "Validación en revisión" })).toBeVisible();
  await expect(page.getByText(/pago aprobado/i)).toHaveCount(0);
  const rows = await (await request.get("http://127.0.0.1:4010/__requests")).json();
  expect(rows).toContainEqual(expect.objectContaining({ method: "POST", path: "/api/v1/checkout", body: expect.objectContaining({ fulfillment_method: "shipping", address_id: 2, billing_profile_id: 3, shipping_quote_id: "22222222-2222-4222-8222-222222222222" }) }));
});

test("checkout hides pickup when storefront settings disable it", async ({ page, request }) => {
  await control(request, { pickupEnabled: false });
  await page.goto("/producto/cuaderno-a5");
  await page.getByRole("button", { name: "Agregar al carrito" }).click();
  await page.keyboard.press("Escape");
  await page.goto("/checkout");
  await page.getByRole("button", { name: "Revisar cuenta" }).click();
  await expect(page.getByRole("heading", { name: "Elegí cómo recibir" })).toBeVisible();
  await expect(page.getByLabel("Retiro")).toHaveCount(0);
});

test("payment result polling is bounded, manually retryable, and order detail uses server timeline", async ({ page, request }, testInfo) => {
  test.skip(!["1024", "1440"].includes(testInfo.project.name), "Bounded polling is viewport-independent; desktop and tablet cover result composition.");
  await control(request, { payments: ["pending", "pending", "pending", "pending", "pending", "pending"] });
  const id = "33333333-3333-4333-8333-333333333333";
  await page.goto(`/pedido/resultado?external_reference=${id}`);
  await expect(page.getByRole("button", { name: "Consultar nuevamente" })).toBeVisible({ timeout: 12_000 });
  await control(request, { payments: ["paid"] });
  await page.getByRole("button", { name: "Consultar nuevamente" }).click();
  await expect(page.getByRole("heading", { name: "Pago aprobado" })).toBeVisible();
  await page.getByRole("link", { name: "Ver este pedido" }).click();
  await expect(page.getByText(`Pedido ${id}`)).toBeVisible();
  await expect(page.getByText("Pedido despachado")).toBeVisible();
  await expect(page.getByText(/CP123AR/)).toBeVisible();
});

test("accessible interaction colors meet required contrast", async ({ page }) => {
  await page.goto("/");
  await page.goto("/producto/cuaderno-a5");
  await page.getByRole("button", { name: "Agregar al carrito" }).click();
  await page.keyboard.press("Escape");
  await expect(page.locator(".header-actions b")).toBeVisible();
  const ratios = await page.evaluate(() => {
    const parse = (color: string) => color.startsWith("#") ? [1, 3, 5].map((index) => Number.parseInt(color.slice(index, index + 2), 16) / 255) : (color.match(/[\d.]+/g)?.slice(0, 3).map((value) => Number(value) / 255) ?? [0, 0, 0]);
    const lum = (color: string) => parse(color).map((value) => value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4).reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0);
    const ratio = (a: string, b: string) => { const [light, dark] = [lum(a), lum(b)].sort((x, y) => y - x); return (light + 0.05) / (dark + 0.05); };
    const styles = getComputedStyle(document.documentElement);
    const badge = getComputedStyle(document.querySelector<HTMLElement>(".header-actions b")!);
    return { primary: ratio(styles.getPropertyValue("--magenta-action").trim(), "#ffffff"), focus: ratio(styles.getPropertyValue("--cyan-action").trim(), "#ffffff"), badge: ratio(badge.backgroundColor, badge.color) };
  });
  expect(ratios.primary).toBeGreaterThanOrEqual(4.5);
  expect(ratios.focus).toBeGreaterThanOrEqual(3);
  expect(ratios.badge).toBeGreaterThanOrEqual(4.5);
});
