import { expect, test, type APIRequestContext } from "@playwright/test";

const control = (request: APIRequestContext, body: Record<string, unknown>) =>
  request.post("http://127.0.0.1:4010/__control", { data: body });

test.beforeEach(async ({ request }) => {
  await control(request, { reset: true });
});

test("mobile hero keeps its campaign controls and facts inside a compact composition", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "360", "The compact hero contract is specific to the narrow mobile layout.");
  await page.goto("/");
  const hero = await page.locator(".hero").boundingBox();
  const copy = await page.locator(".hero-copy").boundingBox();
  const title = await page.locator(".hero-copy h1").boundingBox();
  const heroMedia = page.locator(".hero-media");
  const media = await heroMedia.boundingBox();
  const heroControls = page.locator(".hero-carousel-controls");
  await expect(heroControls).toBeVisible();
  const controls = await heroControls.evaluate((item) => {
    const rect = item.getBoundingClientRect();
    return { top: rect.top, right: rect.right, bottom: rect.bottom, left: rect.left };
  });
  const whatsapp = await page.locator(".whatsapp-float").boundingBox();
  const facts = await page.locator(".hero-facts > div").evaluateAll((items) =>
    items.map((item) => {
      const rect = item.getBoundingClientRect();
      return { top: rect.top, bottom: rect.bottom };
    }),
  );
  expect(hero?.height ?? 0).toBeLessThanOrEqual(560);
  expect(Math.abs((media?.y ?? 0) - (hero?.y ?? 0))).toBeLessThanOrEqual(1);
  expect(Math.abs((media?.height ?? 0) - (hero?.height ?? 0))).toBeLessThanOrEqual(1);
  expect(copy?.y ?? 0).toBeGreaterThanOrEqual(media?.y ?? Number.POSITIVE_INFINITY);
  expect((copy?.y ?? 0) + (copy?.height ?? 0)).toBeLessThanOrEqual((media?.y ?? 0) + (media?.height ?? 0));
  expect(title?.y ?? 0).toBeGreaterThanOrEqual((hero?.y ?? 0) + (hero?.height ?? 0) * 0.25);
  expect(Math.max(...facts.map((fact) => fact.bottom))).toBeLessThanOrEqual(controls.top - 8);
  expect(controls.bottom).toBeLessThanOrEqual((media?.y ?? 0) + (media?.height ?? 0) - 8);
  expect(controls.top).toBeGreaterThanOrEqual((media?.y ?? 0) + 8);
  expect(controls.right).toBeLessThanOrEqual((whatsapp?.x ?? Number.POSITIVE_INFINITY) - 8);
  expect(Math.max(...facts.map((fact) => fact.top)) - Math.min(...facts.map((fact) => fact.top))).toBeLessThanOrEqual(1);
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
  await expect(page.getByRole("heading", { name: "Encontrá lo que necesitás" })).toBeVisible();
  await page.getByRole("button", { name: "Contenido siguiente" }).click();
  await expect(page.getByRole("heading", { name: "Ideas para todos los días" })).toBeVisible();
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

test("desktop promotions and collection products occupy the public content width", async ({ page, request }, testInfo) => {
  test.skip(testInfo.project.name !== "1440", "The wide-shell proportion is a desktop layout contract.");
  await control(request, { collectionProductIds: [7, 8] });
  await page.goto("/");

  const proportions = await page.evaluate(() => {
    const width = (selector: string) => document.querySelector<HTMLElement>(selector)?.getBoundingClientRect().width ?? 0;
    const cards = [...document.querySelectorAll<HTMLElement>(".collection-products .product-card")].map((card) => card.getBoundingClientRect());
    const occupiedCollectionWidth = cards.length ? cards.at(-1)!.right - cards[0].left : 0;
    return {
      collectionProducts: occupiedCollectionWidth / width(".collection-products"),
      promotion: width(".promo-slide") / width(".promo-track"),
    };
  });

  expect(proportions.promotion).toBeGreaterThanOrEqual(0.98);
  expect(proportions.collectionProducts).toBeGreaterThanOrEqual(0.98);
});

test("desktop collections alternate image and copy while mobile keeps media first", async ({ page, request }, testInfo) => {
  test.skip(!["360", "1440"].includes(testInfo.project.name), "The alternation contract only needs one desktop and one mobile viewport.");
  await control(request, { multipleCollections: true });
  await page.goto("/");

  const layouts = await page.locator(".cms-collection").evaluateAll((collections) => collections.map((collection) => {
    const image = collection.querySelector<HTMLElement>(".collection-image")!.getBoundingClientRect();
    const copy = collection.querySelector<HTMLElement>(".collection-copy")!.getBoundingClientRect();
    return { imageX: image.x, imageY: image.y, copyX: copy.x, copyY: copy.y };
  }));

  expect(layouts).toHaveLength(2);
  if (testInfo.project.name === "1440") {
    expect(layouts[0].imageX).toBeLessThan(layouts[0].copyX);
    expect(layouts[1].imageX).toBeGreaterThan(layouts[1].copyX);
  } else {
    expect(layouts.every((layout) => layout.imageY < layout.copyY)).toBe(true);
  }
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
  await expect.poll(async () => (await (await request.get("http://127.0.0.1:4010/__requests")).json()).some((row: { method: string; path: string; csrf: string | null }) => row.method === "POST" && row.path === "/api/v1/auth/login" && row.csrf === "csrf-1")).toBe(true);
  await expect.poll(async () => (await (await request.get("http://127.0.0.1:4010/__requests")).json()).some((row: { method: string; path: string; csrf: string | null; body?: { dni?: string } }) => row.method === "PATCH" && row.path === "/api/v1/customers/me" && row.csrf === "csrf-2" && row.body?.dni === "30.125.678")).toBe(true);
});

test("address workflow supports postal lookup, near confirmation and explicit far reverse choice", async ({ page, request }, testInfo) => {
  test.skip(!["360", "1024"].includes(testInfo.project.name), "Map path runs once per mobile/desktop interaction mode.");
  await page.goto("/cuenta/direcciones");
  await page.getByRole("button", { name: /Casa Av\. Corrientes/ }).click();
  await expect(page.getByRole("heading", { name: "Confirmá el punto de entrega" })).not.toBeVisible();

  await page.getByRole("button", { name: "Agregar dirección" }).click();
  let dialog = page.getByRole("dialog", { name: "Agregar dirección" });
  await dialog.getByLabel("CP o CPA").fill("1043");
  await dialog.getByRole("button", { name: "Buscar localidad" }).click();
  await expect(dialog.getByLabel("Localidad y provincia")).toHaveValue("CABA|CABA");
  await dialog.getByLabel("Calle").fill("Av. Corrientes");
  await dialog.getByLabel("Número").fill("1234");
  await dialog.getByRole("button", { name: "Guardar y ubicar" }).click();
  await page.getByRole("button", { name: "Confirmar esta dirección" }).click();
  await expect(page.getByText(/lista para cotizar/)).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: /lista para cotizar/ })).toBeFocused();

  await page.getByRole("button", { name: "Agregar dirección" }).click();
  dialog = page.getByRole("dialog", { name: "Agregar dirección" });
  await dialog.getByLabel("CP o CPA").fill("1043");
  await dialog.getByRole("button", { name: "Buscar localidad" }).click();
  await dialog.getByLabel("Calle").fill("Av. Corrientes");
  await dialog.getByLabel("Número").fill("1234");
  await dialog.getByRole("button", { name: "Guardar y ubicar" }).click();
  await page.getByText("Ajustar manualmente (opcional)").click();
  await page.getByLabel("Ubicación norte/sur").fill("-34.6200000");
  await expect(page.getByText(/El punto quedó lejos/)).toBeVisible();
  await page.getByRole("button", { name: "Buscar dirección del punto" }).click();
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

test("desktop catalog filters update in place and keep keyboard context", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "1024", "A desktop interaction probe is sufficient for this navigation boundary.");
  await page.goto("/catalogo");
  await page.locator(".site-header").evaluate((node) => {
    (window as Window & { catalogHeader?: Element }).catalogHeader = node;
  });
  const brand = page.getByLabel(/Sur \(1\)/);

  await brand.click();

  await expect(page).toHaveURL(/brand=sur/);
  await expect(page.getByRole("button", { name: /Marca: sur/ })).toBeVisible();
  await expect(brand).toBeFocused();
  expect(await page.evaluate(() => (
    (window as Window & { catalogHeader?: Element }).catalogHeader
    === document.querySelector(".site-header")
  ))).toBe(true);

  await page.evaluate(() => window.history.back());
  await expect(page).toHaveURL(/\/catalogo$/);
  await expect(page.getByRole("button", { name: /Marca: sur/ })).toHaveCount(0);
  expect(await page.evaluate(() => (
    (window as Window & { catalogHeader?: Element }).catalogHeader
    === document.querySelector(".site-header")
  ))).toBe(true);
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

test("desktop and mobile complete the persisted shipping commerce journey through mocked Mercado Pago", async ({ page, request }, testInfo) => {
  test.setTimeout(90_000);
  test.skip(!["360", "1440"].includes(testInfo.project.name), "The complete journey runs once per phone and desktop class.");
  await control(request, { checkoutRedirect: true, payments: ["pending", "paid"] });

  await page.goto("/");
  await page.getByLabel("Buscar productos").fill("cuaderno");
  await page.getByRole("button", { name: "Buscar" }).click();
  await expect(page).toHaveURL(/\/catalogo\?q=cuaderno/);
  await page.waitForLoadState("networkidle");

  if (testInfo.project.name === "360") await page.getByRole("button", { name: "Filtrar" }).click();
  await page.getByLabel(/Sur \(1\)/).click();
  await expect(page).toHaveURL(/brand=sur/);
  if (testInfo.project.name === "360") {
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Filtros de catálogo" })).toBeHidden();
  }
  await page.getByRole("link", { name: "Ver Cuaderno A5" }).click();
  await page.getByLabel("Variante").selectOption("11");
  await page.getByRole("button", { name: "Agregar al carrito" }).click();
  await expect(page.getByRole("dialog", { name: "Tu carrito" })).toBeVisible();
  await page.keyboard.press("Escape");

  await page.goto("/cuenta/registro");
  await page.getByLabel("Nombre").fill("Ana");
  await page.getByLabel("Apellido").fill("Pérez");
  await page.getByLabel("Teléfono").fill("11 5555-1234");
  await page.getByLabel("Email").fill("ana.journey@example.com");
  await page.getByLabel("Contraseña").fill("Clave-segura-2026");
  await page.getByLabel(/Acepto la política/).check();
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByLabel("Código de 6 dígitos").fill("123456");
  await page.getByRole("button", { name: "Verificar email" }).click();
  await expect(page).toHaveURL(/\/cuenta\/ingresar/);
  await page.getByLabel("Email").fill("ana.journey@example.com");
  await page.getByLabel("Contraseña").fill("Clave-segura-2026");
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByRole("heading", { name: "Mi cuenta" })).toBeVisible();
  await expect(page.getByText("ana.journey@example.com")).toBeVisible();

  await page.goto("/checkout");
  await page.getByRole("button", { name: "Revisar cuenta" }).click();
  await expect(page.getByRole("heading", { name: "Elegí cómo recibir" })).toBeVisible();
  await expect(page.getByLabel("Dirección")).toHaveValue("2");
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByRole("button", { name: "Cotizar envío" }).click();
  await expect(page.getByRole("heading", { name: "Revisá antes de pagar" })).toBeVisible();
  await expect(page.getByText("Av. Corrientes 1234, CABA")).toBeVisible();
  await page.getByRole("button", { name: "Ir a Mercado Pago" }).click();

  await expect(page.getByRole("heading", { name: "Mercado Pago simulado" })).toBeVisible();
  await page.getByRole("link", { name: "Volver al comercio" }).click();
  await expect(page.getByRole("heading", { name: "Pago aprobado" })).toBeVisible({ timeout: 8_000 });
  await page.getByRole("link", { name: "Ver este pedido" }).click();
  await expect(page.getByText("Pedido despachado")).toBeVisible();
  await expect(page.getByText(/CP123AR/)).toBeVisible();

  const rows = await (await request.get("http://127.0.0.1:4010/__requests")).json();
  expect(rows).toContainEqual(expect.objectContaining({ method: "POST", path: "/api/v1/checkout", body: expect.objectContaining({ fulfillment_method: "shipping", address_id: 2, shipping_quote_id: "22222222-2222-4222-8222-222222222222" }) }));
});

test("configured pickup reaches review without requesting a shipping quote", async ({ page, request }, testInfo) => {
  test.skip(!["360", "1440"].includes(testInfo.project.name), "Pickup is covered once per phone and desktop class.");
  await page.goto("/producto/cuaderno-a5");
  await page.getByRole("button", { name: "Agregar al carrito" }).click();
  await page.keyboard.press("Escape");
  await page.goto("/checkout");
  await page.getByRole("button", { name: "Revisar cuenta" }).click();
  await page.getByLabel("Retiro central").check();
  await page.getByRole("button", { name: "Continuar" }).click();
  await expect(page.getByRole("heading", { name: "Retiro central" })).toBeVisible();
  await page.getByRole("button", { name: "Continuar" }).click();
  await expect(page.getByText("Av. Corrientes 1234")).toBeVisible();
  const rows = await (await request.get("http://127.0.0.1:4010/__requests")).json();
  expect(rows.filter((row: { path: string }) => row.path === "/api/v1/shipping/quote")).toHaveLength(0);
});
