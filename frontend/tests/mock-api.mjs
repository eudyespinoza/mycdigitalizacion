import http from "node:http";
import { readFileSync } from "node:fs";
import { URL } from "node:url";

const categories = [{ id: 1, name: "Tecnología", slug: "tecnologia", parent_id: null }, { id: 2, name: "Papelería", slug: "papeleria", parent_id: null }, { id: 3, name: "Cuadernos", slug: "cuadernos", parent_id: 2 }, { id: 4, name: "Hogar", slug: "hogar", parent_id: null }];
const pricing = { list_price: "15000.00", effective_price: "12500.00", discount_amount: "2500.00", discount_percentage: "16.67", on_offer: true };
const theme = { theme_palette: "pulso", theme_structure: "#020530", theme_action: "#BD1D59", theme_wayfinding: "#007F96", theme_background: "#FFFFFF", theme_text: "#020530" };
const variant = { id: 11, sku: "CUA-A5-AZ", name: "Azul", price: "15000.00", available_stock: 8, is_available: true, stock_is_infinite: false, purchase_limit: null, packaged_weight_grams: 300, length_cm: "21.00", width_cm: "15.00", height_cm: "2.00", volume_cm3: "630.000000", attributes: [{ name: "Color", slug: "color", type: "option", value: "azul" }], pricing };
const products = [{ id: 7, name: "Cuaderno A5", slug: "cuaderno-a5", description: "Cuaderno de tapa rígida para estudio y oficina.", category: categories[2], brand: { name: "Sur", slug: "sur" }, available_stock: 8, is_available: true, effective_price: "12500.00", on_offer: true, variants: [variant], media: [{ file: "/media/catalog/cuaderno.png", alt_text: "Cuadernos y útiles en tonos azul y cyan", order: 1 }] }];
const collectionExtraProduct = { ...products[0], id: 8, name: "Organizador de escritorio", slug: "organizador-escritorio", variants: [{ ...variant, id: 12, sku: "ORG-ESC-AZ" }] };
const facets = { categories: [{ name: "Papelería", slug: "papeleria", count: 1, children: [{ name: "Cuadernos", slug: "cuadernos", count: 1, children: [] }] }], brands: [{ name: "Sur", slug: "sur", count: 1 }], price: { min: "12500.00", max: "12500.00" }, availability: { in_stock: 1, out_of_stock: 0 }, offer: { on_offer: 1, regular: 0 }, attributes: [{ name: "Color", slug: "color", type: "option", values: [{ value: "azul", label: "Azul", count: 1 }] }] };
const addressBase = { id: 2, label: "Casa", raw_address: "Av. Corrientes 1234, CABA", normalized_address: "Avenida Corrientes 1234", street: "Av. Corrientes", number: "1234", postal_code: "1043", cpa: "C1043", locality: "CABA", province: "CABA", latitude: "-34.6037000", longitude: "-58.3816000", floor: "", apartment: "", reference: "", notes: "", geocode_source: "georef", geocode_confidence: "0.950", geocode_summary: {}, needs_review: false, reviewed_at: "2026-08-20T00:05:00Z", created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:05:00Z" };
const billing = [{ id: 3, label: "Personal", legal_name: "Cliente sintético de prueba", tax_condition: "consumidor_final", is_default: true, masked_cuit: "20-********-3" }];
const image = readFileSync(new URL("../public/campaigns/pulso-libreria-collection.png", import.meta.url));
const managementEditorProduct = {
  id: 7, sku: "600001", name: "Cuaderno A5", slug: "cuaderno-a5", description: "Cuaderno de tapa rígida para estudio y oficina. Datos sintéticos de prueba.",
  category: { ...categories[2], is_active: true }, brand: { id: 4, name: "Sur", slug: "sur" }, is_active: true, is_sellable: true,
  created_at: "2026-08-20T10:00:00Z", on_offer: false, active_offer_names: [],
  media: [{ id: 31, file_url: "/media/catalog/cuaderno.png", responsive_sources: [], alt_text: "Cuaderno azul, vista frontal", order: 0, variant_id: 11, variant_name: "Azul" }],
  variants: [
    { id: 11, sku: "600001-01", name: "Azul", price: "15000.00", cost: "8000.00", on_hand: 10, available_stock: 8, stock_is_infinite: false, max_purchase_quantity: 5, is_active: true, packaged_weight_grams: 300, length_cm: "21.00", width_cm: "15.00", height_cm: "2.00", attributes: [] },
    { id: 12, sku: "600001-02", name: "Tapa flexible · edición de prueba con una presentación de nombre extenso", price: "17500.00", cost: "9000.00", on_hand: 15, available_stock: 15, stock_is_infinite: false, max_purchase_quantity: null, is_active: true, packaged_weight_grams: 250, length_cm: "21.00", width_cm: "15.00", height_cm: "1.50", attributes: [] },
  ],
};
const horizontalLogoImage = readFileSync(new URL("../public/campaigns/pulso-comercial-hero.png", import.meta.url));

const supportStaff = { id: 90, email: "visual-admin@example.test", name: "Ana Gestión" };
const supportTimestamp = "2026-08-23T14:30:00Z";
const supportCase = (public_id, status = "waiting_staff") => ({
  public_id,
  case_number: public_id.startsWith("222") ? "PRO-2026-000124" : "CON-2026-000123",
  kind: public_id.startsWith("222") ? "problem" : "consultation",
  subject: public_id.startsWith("222") ? "Problema cerrado de prueba" : "Consulta de prueba",
  category: public_id.startsWith("222") ? "sitio" : "productos",
  status,
  priority: "normal",
  contact_name: "Ana Pérez",
  contact_email: "ana@example.test",
  contact_phone: "1155551234",
  customer: { id: 5, email: "cliente@example.com", name: "Ana Pérez" },
  assigned_to: supportStaff,
  message_count: 1,
  unread: status !== "closed",
  created_at: "2026-08-23T13:30:00Z",
  updated_at: supportTimestamp,
  order_id: null,
  product_id: 7,
  source_url: "",
  resolved_at: null,
  closed_at: status === "closed" ? supportTimestamp : null,
  staff_last_read_at: null,
  messages: [{
    id: 1,
    author: null,
    author_role: "guest",
    body: "Necesito ayuda con este producto.",
    created_at: "2026-08-23T13:30:00Z",
    attachments: [{
      public_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      original_name: "captura.png",
      detected_mime_type: "image/png",
      size_bytes: 2048,
      is_image: true,
      preview_url: "/api/v1/support/attachments/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/?preview=1",
      created_at: "2026-08-23T13:30:00Z",
    }],
  }],
});
const supportSummary = (item) => (({ public_id, case_number, kind, subject, category, status, updated_at }) => ({ public_id, case_number, kind, subject, category, status, updated_at }))(item);
const supportMessage = (message) => (({ id, author_role, body, created_at, attachments }) => ({ id, author_role, body, created_at, attachments }))(message);
const supportPublicDetail = (item, recovery_code) => ({ ...supportSummary(item), created_at: item.created_at, messages: item.messages.map(supportMessage), ...(recovery_code ? { recovery_code } : {}) });
const supportManagementDetail = (item) => ({ ...item, messages: item.messages.map((message) => ({ ...message, author: message.author ?? (message.author_role === "staff" ? supportStaff : null) })) });

let state;
const reset = () => { state = { csrf: "csrf-1", loggedIn: true, cmsError: false, pickupEnabled: true, checkoutRedirect: false, fastCampaigns: false, popupEnabled: false, popupFrequency: "once_session", popupDismissible: true, socialEnabled: true, multipleCollections: false, logoUrl: "/brand/mycdigitalizacion-logo.png", faviconUrl: "/brand/mycdigitalizacion-logo.png", collectionProductIds: [7], address: { ...addressBase }, customer: { id: 5, email: "cliente@example.com", email_verified_at: "2026-08-20T10:00:00Z", is_staff: false, profile: { first_name: "Ana", last_name: "Pérez", phone: "1155551234" }, masked_dni: "••••5678", masked_cuit: "" }, cart: { lines: [], subtotal: "0.00", discount: "0.00", total: "0.00", cart_token: "mock-cart-token", coupon: null }, payments: ["pending", "pending", "paid"], supportCases: [supportCase("11111111-1111-4111-8111-111111111111"), supportCase("22222222-2222-4222-8222-222222222222", "closed")], requests: [] }; };
reset();
const json = (response, status, body, headers = {}) => { response.writeHead(status, { "content-type": "application/json", ...headers }); response.end(body === undefined ? "" : JSON.stringify(body)); };
const customerSessionCookie = "myc_sessionid=authorized; Path=/; SameSite=Lax";
const supportGuestSessionCookie = "myc_support_session=authorized; Path=/; SameSite=Lax";
const read = (request) => new Promise((resolve) => { let data = ""; request.on("data", (chunk) => { data += chunk; }); request.on("end", () => { try { resolve(data ? JSON.parse(data) : {}); } catch { resolve({ __raw: data }); } }); });
const unsafe = (method) => !["GET", "HEAD", "OPTIONS"].includes(method ?? "GET");
const validateCsrf = (request, response) => { if (unsafe(request.method) && request.headers["x-csrftoken"] !== state.csrf) { json(response, 403, { code: "csrf_failed", detail: "La sesión de seguridad venció. Actualizá la página e intentá nuevamente." }); return false; } return true; };
const line = (quantity) => ({ id: 1, variant_id: 11, sku: "CUA-A5-AZ", product_name: "Cuaderno A5", variant_name: "Azul", quantity, unit_price: "12500.00", line_subtotal: `${12500 * quantity}.00`, line_discount: "0.00", line_total: `${12500 * quantity}.00`, availability: "available", available_stock: 8, stock_is_infinite: false, purchase_limit: null, notices: [] });
const setCart = (quantity) => { state.cart = quantity > 0 ? { ...state.cart, lines: [line(quantity)], subtotal: `${12500 * quantity}.00`, total: `${12500 * quantity}.00` } : { ...state.cart, lines: [], subtotal: "0.00", total: "0.00" }; return state.cart; };
const supportFormValue = (body, name) => {
  if (typeof body[name] === "string") return body[name];
  const raw = body.__raw ?? "";
  const marker = raw.indexOf(`name="${name}"`);
  if (marker < 0) return "";
  const valueStart = raw.indexOf("\r\n\r\n", marker);
  if (valueStart < 0) return "";
  const valueEnd = raw.indexOf("\r\n--", valueStart + 4);
  return raw.slice(valueStart + 4, valueEnd < 0 ? undefined : valueEnd);
};
const supportCaseFor = (publicId) => state.supportCases.find((item) => item.public_id === publicId);
const supportAttachmentExists = (publicId) => state.supportCases.some((item) => item.messages.some((message) => message.attachments.some((attachment) => attachment.public_id === publicId)));
const supportAttachmentIdFrom = (path) => path.split("/").filter(Boolean).at(-1);
const hasPublicAttachmentAccess = (request) => request.headers["x-mock-support-session"] === "authorized" || ["myc_support_session=authorized", "myc_sessionid=authorized"].some((cookie) => (request.headers.cookie ?? "").includes(cookie));
const hasManagementAttachmentAccess = (request) => request.headers["x-mock-management-session"] === "authorized" || (request.headers.cookie ?? "").includes("myc_sessionid=authorized");
const supportNextMessage = (item, role, body) => {
  const message = { id: item.messages.length + 1, author: role === "staff" ? supportStaff : null, author_role: role, body, created_at: new Date(Date.parse(item.updated_at) + 60_000).toISOString(), attachments: [] };
  item.messages.push(message);
  item.message_count = item.messages.length;
  item.updated_at = message.created_at;
  item.status = role === "staff" ? "waiting_customer" : "waiting_staff";
  item.unread = role !== "staff";
  return message;
};

http.createServer(async (request, response) => {
  const url = new URL(request.url, "http://127.0.0.1:4010"); const path = url.pathname.replace(/\/$/, "");
  if (path === "/mock-mercado-pago") { response.writeHead(200, { "content-type": "text/html; charset=utf-8" }); response.end(`<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Mercado Pago simulado</title></head><body><main><h1>Mercado Pago simulado</h1><p>Entorno determinístico de prueba. No representa un pago aprobado.</p><a href="http://127.0.0.1:3000/pedido/resultado?external_reference=33333333-3333-4333-8333-333333333333">Volver al comercio</a></main></body></html>`); return; }
  if (path.startsWith("/media/")) { response.writeHead(200, { "content-type": "image/png", "cache-control": "public,max-age=3600" }); response.end(path.includes("logo/horizontal") ? horizontalLogoImage : image); return; }
  if (path === "/__control") { const body = await read(request); if (body.reset) reset(); Object.assign(state, body); return json(response, 200, state); }
  if (path === "/__requests") return json(response, 200, state.requests);
  if (request.method === "OPTIONS") return json(response, 204);
  const body = unsafe(request.method) ? await read(request) : {};
  state.requests.push({ method: request.method, path, body, csrf: request.headers["x-csrftoken"] ?? null, cookie: request.headers.cookie ?? "" });
  if (path === "/api/v1/management/session") return json(response, 200, { user: { id: 90, email: "visual-admin@example.test", first_name: "Ana", last_name: "Gestión", is_staff: true, is_superuser: true, permissions: [] } }, { "set-cookie": customerSessionCookie });
  if (path === "/api/v1/management/dashboard") return json(response, 200, { metrics: { active_products: 24, low_stock_variants: 3, orders_requiring_attention: 2, integration_incidents: 1 } });
  if (path === "/api/v1/management/support/assignees" && request.method === "GET") return json(response, 200, { results: [supportStaff] });
  if (path === "/api/v1/management/support/summary" && request.method === "GET") return json(response, 200, { pending: state.supportCases.filter((item) => ["new", "waiting_staff"].includes(item.status)).length, unread: state.supportCases.filter((item) => item.unread).length });
  if (path === "/api/v1/management/support/cases" && request.method === "GET") {
    const kind = url.searchParams.get("kind");
    const status = url.searchParams.get("status");
    const priority = url.searchParams.get("priority");
    const assignee = url.searchParams.get("assignee");
    const pending = ["1", "true"].includes((url.searchParams.get("pending") ?? "").toLowerCase());
    const unread = ["1", "true"].includes((url.searchParams.get("unread") ?? "").toLowerCase());
    const search = url.searchParams.get("search")?.toLowerCase();
    const results = state.supportCases.filter((item) => (
      (!kind || item.kind === kind)
      && (!status || item.status === status)
      && (!priority || item.priority === priority)
      && (!assignee || (assignee === "unassigned" ? item.assigned_to === null : String(item.assigned_to?.id ?? "") === assignee))
      && (!pending || ["new", "waiting_staff"].includes(item.status))
      && (!unread || item.unread)
      && (!search || `${item.case_number} ${item.subject} ${item.contact_name} ${item.contact_email}`.toLowerCase().includes(search))
    ));
    return json(response, 200, { count: results.length, next: null, previous: null, results });
  }
  if (path.startsWith("/api/v1/management/support/attachments/") && request.method === "GET") {
    const attachmentId = supportAttachmentIdFrom(path);
    if (!attachmentId || !supportAttachmentExists(attachmentId) || !hasManagementAttachmentAccess(request)) return json(response, 404, { detail: "Adjunto no encontrado." });
    response.writeHead(200, {
      "content-type": url.searchParams.get("preview") === "1" ? "image/webp" : "image/png",
      "content-disposition": `${url.searchParams.get("preview") === "1" ? "inline" : "attachment"}; filename="adjunto.png"`,
      "x-content-type-options": "nosniff",
    });
    response.end(image);
    return;
  }
  if (path.startsWith("/api/v1/management/support/cases/") && path.endsWith("/messages") && request.method === "POST") {
    if (!validateCsrf(request, response)) return;
    const item = supportCaseFor(path.split("/")[6]);
    if (!item) return json(response, 404, { detail: "Consulta no encontrada." });
    return json(response, 201, supportNextMessage(item, "staff", supportFormValue(body, "body") || "Respuesta del equipo"));
  }
  if (path.startsWith("/api/v1/management/support/cases/") && request.method === "PATCH") {
    if (!validateCsrf(request, response)) return;
    const item = supportCaseFor(path.split("/")[6]);
    if (!item) return json(response, 404, { detail: "Consulta no encontrada." });
    if (body.status) item.status = body.status;
    if (body.priority) item.priority = body.priority;
    if (Object.hasOwn(body, "assigned_to")) item.assigned_to = body.assigned_to ? supportStaff : null;
    return json(response, 200, supportManagementDetail(item));
  }
  if (path.startsWith("/api/v1/management/support/cases/") && request.method === "GET") {
    const item = supportCaseFor(path.split("/")[6]);
    if (!item) return json(response, 404, { detail: "Consulta no encontrada." });
    item.staff_last_read_at = new Date().toISOString();
    item.unread = false;
    return json(response, 200, supportManagementDetail(item));
  }
  if (path === "/api/v1/support/configuration" && request.method === "GET") return json(response, 200, { authenticated: state.loggedIn, email_available: false, categories: { consultation: [{ value: "productos", label: "Productos" }, { value: "compra", label: "Compra" }, { value: "envios", label: "Envíos" }, { value: "pagos", label: "Pagos" }, { value: "facturacion", label: "Facturación" }, { value: "otra", label: "Otra consulta" }], problem: [{ value: "pedido", label: "Pedido" }, { value: "pago", label: "Pago" }, { value: "envio", label: "Envío" }, { value: "producto", label: "Producto" }, { value: "cuenta", label: "Cuenta" }, { value: "sitio", label: "Sitio web" }, { value: "otro", label: "Otro problema" }] }, limits: { max_files: 5, max_file_size_bytes: 10485760, max_total_size_bytes: 31457280 } }, state.loggedIn ? { "set-cookie": customerSessionCookie } : {});
  if (path === "/api/v1/support/cases" && request.method === "GET") return json(response, 200, { results: state.supportCases.map(supportSummary) });
  if (path === "/api/v1/support/cases" && request.method === "POST") {
    if (!validateCsrf(request, response)) return;
    const publicId = "33333333-3333-4333-8333-333333333333";
    const created = supportCase(publicId);
    created.kind = supportFormValue(body, "kind") || "consultation";
    created.case_number = created.kind === "problem" ? "PRO-2026-000125" : "CON-2026-000125";
    created.subject = supportFormValue(body, "subject") || "Consulta creada";
    created.category = supportFormValue(body, "category") || "productos";
    created.messages[0].body = supportFormValue(body, "body") || "Mensaje inicial";
    state.supportCases.unshift(created);
    return json(response, 201, supportPublicDetail(created, "REC-1234"));
  }
  if (path === "/api/v1/support/access" && request.method === "POST") {
    if (!validateCsrf(request, response)) return;
    const item = state.supportCases.find((candidate) => candidate.case_number === body.case_number);
    return item && body.code === "REC-1234" ? json(response, 200, supportPublicDetail(item), { "set-cookie": supportGuestSessionCookie }) : json(response, 400, { code: ["El código privado no es válido."] });
  }
  if (path.startsWith("/api/v1/support/attachments/") && request.method === "GET") {
    const attachmentId = supportAttachmentIdFrom(path);
    if (!attachmentId || !supportAttachmentExists(attachmentId) || !hasPublicAttachmentAccess(request)) return json(response, 404, { detail: "Adjunto no encontrado." });
    response.writeHead(200, {
      "content-type": url.searchParams.get("preview") === "1" ? "image/webp" : "image/png",
      "content-disposition": `${url.searchParams.get("preview") === "1" ? "inline" : "attachment"}; filename="adjunto.png"`,
      "x-content-type-options": "nosniff",
    });
    response.end(image);
    return;
  }
  if (path.startsWith("/api/v1/support/cases/") && path.endsWith("/claim") && request.method === "POST") {
    if (!validateCsrf(request, response)) return;
    const item = supportCaseFor(path.split("/")[5]);
    if (!item || body.code !== "REC-1234") return json(response, 400, { code: ["El código privado no es válido."] });
    item.customer = { id: state.customer.id, email: state.customer.email, name: `${state.customer.profile.first_name} ${state.customer.profile.last_name}`.trim() };
    return json(response, 200, supportPublicDetail(item));
  }
  if (path.startsWith("/api/v1/support/cases/") && path.endsWith("/messages") && request.method === "POST") {
    if (!validateCsrf(request, response)) return;
    const item = supportCaseFor(path.split("/")[5]);
    if (!item || item.status === "closed") return json(response, 404, { detail: "Consulta no encontrada." });
    return json(response, 201, supportMessage(supportNextMessage(item, "guest", supportFormValue(body, "body") || "Mensaje de prueba")));
  }
  if (path.startsWith("/api/v1/support/cases/") && request.method === "GET") {
    const item = supportCaseFor(path.split("/")[5]);
    return item ? json(response, 200, supportPublicDetail(item)) : json(response, 404, { detail: "Consulta no encontrada." });
  }
  if (path === "/api/v1/management/products") return json(response, 200, { count: 1, next: null, previous: null, results: [{ id: 7, name: "Cuaderno A5", slug: "cuaderno-a5", description: "Cuaderno rayado", category: { ...categories[2], is_active: true }, brand: { id: 4, name: "Sur", slug: "sur" }, is_active: true, is_sellable: true, created_at: "2026-08-20T10:00:00Z", on_offer: true, active_offer_names: ["Vuelta al cole"], media: [], variants: [{ id: 11, sku: "CUA-A5-AZ", name: "Azul", price: "15000.00", cost: "8000.00", on_hand: 10, available_stock: 8, stock_is_infinite: false, max_purchase_quantity: 5, is_active: true, packaged_weight_grams: 300, length_cm: "21.00", width_cm: "15.00", height_cm: "2.00", attributes: [] }] }] });
  if (path === "/api/v1/management/inventory") return json(response, 200, { count: 1, next: null, previous: null, results: [{ id: 11, sku: "CUA-A5-AZ", name: "Azul", price: "15000.00", cost: "8000.00", on_hand: 10, available_stock: 8, stock_is_infinite: false, max_purchase_quantity: 5, is_active: true, packaged_weight_grams: 300, length_cm: "21.00", width_cm: "15.00", height_cm: "2.00", product: { id: 7, name: "Cuaderno A5" }, recent_movements: [] }] });
  if (path === "/api/v1/management/orders") return json(response, 200, { count: 1, next: null, previous: null, results: [{ public_id: "33333333-3333-4333-8333-333333333333", customer: { id: 5, name: "Ana Pérez", email: "ana@example.com", phone: "1155551234" }, identity_status: "verified", payment_status: "paid", fulfillment_status: "preparing", fulfillment_method: "shipping", total: "17000.00", created_at: "2026-08-20T10:00:00Z" }] });
  if (path === "/api/v1/management/customers") return json(response, 200, { count: 1, next: null, previous: null, results: [{ id: 5, name: "Ana Pérez", email: "ana@example.com", phone: "1155551234", masked_dni: "••••5678", email_verified: true, order_count: 2, total_spent: "30000.00" }] });
  if (path.startsWith("/api/v1/management/content/")) return json(response, 200, { results: [] });
  if (path === "/api/v1/management/promotions/rules") return json(response, 200, { results: [{ id: 1, name: "Vuelta al cole", discount_type: "percentage", value: "15.00", starts_at: "2026-08-20T10:00:00Z", ends_at: "2026-08-27T10:00:00Z", enabled: true, product_ids: [7], category_ids: [] }] });
  if (path === "/api/v1/management/promotions/coupons") return json(response, 200, { results: [{ id: 2, code: "VUELTA10", discount_type: "percentage", value: "10.00", starts_at: "2026-08-20T10:00:00Z", ends_at: "2026-08-27T10:00:00Z", enabled: true, combinable: false, max_redemptions: 100, used_redemptions: 12, reserved_redemptions: 2 }] });
  if (path === "/api/v1/management/promotions/scope-options") return json(response, 200, { products: [{ id: 7, label: "Cuaderno A5", description: "Cuadernos" }], categories: [{ id: 3, label: "Cuadernos" }] });
  if (path === "/api/v1/management/shipping/boxes") return json(response, 200, { results: [{ id: 1, code: "CAJA-S", inner_length_cm: "25.00", inner_width_cm: "18.00", inner_height_cm: "8.00", tare_weight_grams: 120, max_weight_grams: 2000, enabled: true }] });
  if (path === "/api/v1/management/integrations") return json(response, 200, { results: [{ provider: "mercadopago", label: "Mercado Pago", enabled: true, environment: "sandbox", status: "configured", public_config: {}, secret_fields: { access_token: true }, version: 1, updated_at: "2026-08-20T10:00:00Z", updated_by: "visual-admin@example.test", last_test_status: "success", last_tested_at: "2026-08-20T10:00:00Z", last_test_message: "Conexión verificada" }, { provider: "correo_argentino", label: "API MiCorreo", enabled: false, environment: "qa", status: "incomplete", public_config: {}, secret_fields: {}, version: 1, updated_at: null, updated_by: "", last_test_status: "", last_tested_at: null, last_test_message: "" }, { provider: "andreani", label: "Andreani", enabled: false, environment: "qa", status: "incomplete", public_config: {}, secret_fields: {}, version: 1, updated_at: null, updated_by: "", last_test_status: "", last_tested_at: null, last_test_message: "" }] });
  if (path === "/api/v1/management/integrations/mercadopago" && request.method === "GET") return json(response, 200, { provider: "mercadopago", label: "Mercado Pago", enabled: false, environment: "sandbox", status: "incomplete", public_config: {}, secret_fields: { access_token: false, refresh_token: false, webhook_secret: false }, version: 0, updated_at: null, updated_by: "", last_test_status: "", last_tested_at: null, last_test_message: "", oauth_ready: true, oauth_status: "disconnected", oauth_callback_url: "http://127.0.0.1:3000/api/v1/payments/mercadopago/oauth/callback/", connected_account_id: "", oauth_connected_at: null });
  if (path === "/api/v1/management/integrations/arca_a13" && request.method === "GET") return json(response, 200, { provider: "arca_a13", label: "Identidad fiscal ARCA · Padrón A13", enabled: true, environment: "production", status: "configured", public_config: { represented_cuit: "20123456786", wsaa_url: "", a13_url: "" }, secret_fields: { certificate_pem: false, private_key_pem: false, private_key_passphrase: false, pfx_base64: true, pfx_password: true }, version: 1, updated_at: "2026-08-27T10:00:00Z", updated_by: "visual-admin@example.test", last_test_status: "success", last_tested_at: "2026-08-27T10:01:00Z", last_test_message: "Conexión verificada." });
  if (path === "/api/v1/management/integrations/mercadopago/oauth/start" && request.method === "POST") { if (!validateCsrf(request, response)) return; return json(response, 200, { authorization_url: "https://auth.mercadopago.com/authorization?state=mock-safe-state", callback_url: "http://127.0.0.1:3000/api/v1/payments/mercadopago/oauth/callback/" }); }
  if (path === "/api/v1/management/integrations/mercadopago/oauth/disconnect" && request.method === "POST") { if (!validateCsrf(request, response)) return; return json(response, 200, { provider: "mercadopago", label: "Mercado Pago", enabled: false, environment: "sandbox", status: "disabled", public_config: {}, secret_fields: {}, version: 2, updated_at: "2026-08-21T10:00:00Z", updated_by: "visual-admin@example.test", last_test_status: "", last_tested_at: "2026-08-21T10:00:00Z", last_test_message: "Mercado Pago fue desconectado.", oauth_ready: true, oauth_status: "disconnected", oauth_callback_url: "http://127.0.0.1:3000/api/v1/payments/mercadopago/oauth/callback/", connected_account_id: "", oauth_connected_at: null }); }
  if (path === "/api/v1/management/users") return json(response, 200, { results: [{ id: 90, email: "visual-admin@example.test", first_name: "Ana", last_name: "Gestión", is_active: true, is_superuser: true, role_names: [], last_login: "2026-08-20T10:00:00Z" }] });
  if (path === "/api/v1/management/roles") return json(response, 200, { results: [{ name: "catalog", label: "Catálogo", permission_count: 8 }] });
  if (path === "/api/v1/management/audit") return json(response, 200, { count: 1, next: null, previous: null, results: [{ id: 1, actor: "visual-admin@example.test", action: "product.updated", resource: "product", object_reference: "7", metadata: {}, created_at: "2026-08-20T10:00:00Z" }] });
  if (path === "/api/v1/management/settings/general") return json(response, 200, { public_name: "mycdigitalizacion", announcement: "Envíos a todo el país", contact_email: "ventas@example.com", pickup_enabled: true, pickup_label: "Retiro central", pickup_address: "Av. Corrientes 1234", pickup_hours: "Lunes a viernes de 10 a 18", instagram_url: "https://instagram.com/mycdigitalizacion", facebook_url: "", tiktok_url: "", youtube_url: "", linkedin_url: "", whatsapp_enabled: true, whatsapp_number: "5491155551234", whatsapp_message: "Hola, quiero consultar por un producto", logo_url: "/brand/mycdigitalizacion-logo.png", favicon_url: "/brand/mycdigitalizacion-logo.png", ...theme });
  if (path === "/api/v1/management/products/7") return json(response, 200, managementEditorProduct);
  if (path === "/api/v1/management/categories") return json(response, 200, { results: categories.map((category) => ({ ...category, is_active: true })) });
  if (path === "/api/v1/management/brands") return json(response, 200, { results: [{ id: 4, name: "Sur", slug: "sur" }] });
  if (path === "/api/v1/management/attributes") return json(response, 200, { results: [{ id: 1, name: "Color", slug: "color", value_type: "option", is_filterable: true, options: [{ id: 1, label: "Azul", value: "azul" }] }] });
  if (path === "/api/v1/storefront/home") {
    if (state.cmsError) return json(response, 503, { code: "provider_down", detail: "CMS no disponible" });
    const shared = { alt_text: "Campaña comercial en azul, blanco y magenta", desktop_image_url: "/media/cms/hero.png", mobile_image_url: "/media/cms/hero-mobile.png", desktop_responsive_sources: [], mobile_responsive_sources: [], cta_label: "Explorar catálogo", cta_url: "/catalogo", focal_x: "58", focal_y: "50", safe_height_mobile: 390, safe_height_tablet: 520, safe_height_desktop: 570, starts_at: null, ends_at: null };
    const hero_slides = [
      { ...shared, id: 1, title: "Todo lo que buscás, en un solo lugar", body: "Tecnología, papelería, hogar y más para descubrir.", alt_text: "Cuaderno, botella y accesorios de escritorio en azul, blanco y magenta", order: 1, interval_ms: state.fastCampaigns ? 1_000 : 30_000, pause_on_reduced_motion: true },
      { ...shared, id: 2, title: "Elegí a tu ritmo", body: "Encontrá productos publicados por la tienda.", order: 2, interval_ms: state.fastCampaigns ? 2_500 : 30_000, pause_on_reduced_motion: true },
    ];
    const promotion_slides = [
      { ...shared, id: 3, title: "Beneficio publicado", body: "Consultá la selección vigente.", order: 1, interval_ms: state.fastCampaigns ? 1_200 : 30_000, pause_on_reduced_motion: true },
      { ...shared, id: 5, title: "Otra forma de descubrir", body: "Recorré el catálogo actual.", order: 2, interval_ms: state.fastCampaigns ? 2_800 : 30_000, pause_on_reduced_motion: false },
    ];
    const promotion_popups = state.popupEnabled ? [{ ...shared, id: 8, title: "Beneficio vigente", body: "Contenido publicado por la tienda.", alt_text: "Beneficio vigente en azul", order: 1, frequency: state.popupFrequency, display_delay_ms: 50, dismissible: state.popupDismissible, version: 1 }] : [];
    const collections = [{ ...shared, id: 4, title: "Ideas para estudio y oficina", body: "Una selección publicada por el equipo de la tienda.", alt_text: "Cuadernos y útiles para estudio", desktop_image_url: "/media/cms/collection.png", mobile_image_url: "/media/cms/collection-mobile.png", focal_x: "50", focal_y: "50", safe_height_mobile: 420, safe_height_tablet: 500, safe_height_desktop: 520, cta_label: "Explorar papelería", cta_url: "/catalogo?category=papeleria", order: 1, product_ids: state.collectionProductIds }];
    if (state.multipleCollections) collections.push({ ...shared, id: 6, title: "Organización para cada espacio", body: "Otra colección administrable de la tienda.", alt_text: "Elementos para organizar el escritorio", desktop_image_url: "/media/cms/collection-2.png", mobile_image_url: "/media/cms/collection-2-mobile.png", focal_x: "50", focal_y: "50", safe_height_mobile: 420, safe_height_tablet: 500, safe_height_desktop: 520, cta_label: "Ver colección", cta_url: "/catalogo?category=organizacion", order: 2, product_ids: [] });
    return json(response, 200, { settings: { public_name: "mycdigitalizacion", announcement: "", contact_email: "", pickup_enabled: state.pickupEnabled, pickup_label: "Retiro central", pickup_address: "Av. Corrientes 1234", pickup_hours: "Lunes a viernes de 10 a 18", instagram_url: state.socialEnabled ? "https://instagram.com/mycdigitalizacion" : "", facebook_url: "", tiktok_url: "", youtube_url: "", linkedin_url: "", whatsapp_enabled: state.socialEnabled, whatsapp_number: state.socialEnabled ? "5491155551234" : "", whatsapp_message: "Hola, quiero consultar por un producto", logo_url: state.logoUrl, logo_responsive_sources: [], favicon_url: state.faviconUrl, ...theme }, hero_slides, promotion_slides, collections, promotion_popups });
  }
  if (path === "/api/v1/storefront/catalog-content") {
    const shared = { body: "Explorá productos para estudiar, crear y organizar cada espacio.", alt_text: "Cuadernos y útiles organizados sobre un escritorio", desktop_image_url: "/media/cms/catalog.png", mobile_image_url: "/media/cms/catalog-mobile.png", desktop_responsive_sources: [], mobile_responsive_sources: [], cta_label: "Ver ofertas", cta_url: "/catalogo?offer=true", focal_x: "60", focal_y: "50", safe_height_mobile: 240, safe_height_tablet: 210, safe_height_desktop: 220, starts_at: null, ends_at: null, interval_ms: 30_000, pause_on_reduced_motion: true };
    return json(response, 200, { slides: [{ ...shared, id: 21, title: "Encontrá lo que necesitás", order: 1 }, { ...shared, id: 22, title: "Ideas para todos los días", order: 2 }] });
  }
  if (path === "/api/v1/categories") return json(response, 200, categories);
  if (path === "/api/v1/products" || path === "/api/v1/search") { const visibleProducts = state.collectionProductIds.includes(8) ? [...products, collectionExtraProduct] : products; return json(response, 200, { count: visibleProducts.length, next: null, previous: null, results: visibleProducts, facets }); }
  if (path === "/api/v1/products/cuaderno-a5") return json(response, 200, products[0]);
  if (path === "/api/v1/auth/csrf") return json(response, 200, { csrf_token: state.csrf }, { "set-cookie": `csrftoken=${state.csrf}; Path=/; SameSite=Lax` });
  if (path === "/api/v1/auth/config" && request.method === "GET") return json(response, 200, { email_verification_required: true, google_enabled: false, google_client_id: "" });
  if (path === "/api/v1/auth/login" && request.method === "POST") { if (!validateCsrf(request, response)) return; state.loggedIn = true; state.csrf = "csrf-2"; return json(response, 200, state.customer, { "set-cookie": "csrftoken=csrf-2; Path=/; SameSite=Lax" }); }
  if (path === "/api/v1/auth/logout" && request.method === "POST") { if (!validateCsrf(request, response)) return; state.loggedIn = false; state.csrf = "csrf-3"; return json(response, 204, undefined, { "set-cookie": "csrftoken=csrf-3; Path=/; SameSite=Lax" }); }
  if (path === "/api/v1/auth/register" && request.method === "POST") { if (!validateCsrf(request, response)) return; if (!body.first_name || !body.last_name || !body.phone) return json(response, 400, { first_name: ["Requerido para la tienda."], last_name: ["Requerido para la tienda."], phone: ["Requerido para la tienda."] }); state.customer = { ...state.customer, email: body.email, email_verified_at: null, profile: { first_name: body.first_name, last_name: body.last_name, phone: body.phone } }; return json(response, 201, { ...state.customer, masked_dni: "" }); }
  if (path === "/api/v1/auth/email-verify" && request.method === "POST") { if (!validateCsrf(request, response)) return; state.customer = { ...state.customer, email_verified_at: "2026-08-20T12:00:00Z" }; return json(response, 200, { status: "verified" }); }
  if (path === "/api/v1/customers/me" && request.method === "GET") return json(response, 200, state.customer);
  if (path === "/api/v1/customers/me" && request.method === "PATCH") { if (!validateCsrf(request, response)) return; state.customer = { ...state.customer, profile: { first_name: body.first_name ?? state.customer.profile.first_name, last_name: body.last_name ?? state.customer.profile.last_name, phone: body.phone ?? state.customer.profile.phone }, masked_dni: body.dni ? `••••${String(body.dni).replace(/\D/g, "").slice(-4)}` : state.customer.masked_dni }; return json(response, 200, state.customer); }
  if (path === "/api/v1/cart") { if (request.method !== "GET" && !validateCsrf(request, response)) return; if (request.method === "POST" && body.variant_id) setCart(body.quantity); if (request.method === "PATCH") setCart(body.quantity); if (request.method === "DELETE") setCart(0); return json(response, request.method === "POST" ? 201 : 200, state.cart); }
  if (path === "/api/v1/identity/status") return json(response, 200, { status: "approved", can_validate: false });
  if (path === "/api/v1/identity/validate") { if (!validateCsrf(request, response)) return; return json(response, 200, { status: "approved", can_validate: false }); }
  if (path === "/api/v1/locations/map-config") return json(response, 200, { provider: "openstreetmap", google_maps_browser_key: "", google_maps_map_id: "" });
  if (path === "/api/v1/locations/postal-lookup") return json(response, 200, [{ postal_code: "1043", cpa: "C1043", locality: "CABA", province: "CABA" }]);
  if (path === "/api/v1/addresses" && request.method === "GET") return json(response, 200, [state.address]);
  if (path === "/api/v1/addresses" && request.method === "POST") { if (!validateCsrf(request, response)) return; state.address = { ...addressBase, ...body, needs_review: true, reviewed_at: null }; return json(response, 201, state.address); }
  if (path === "/api/v1/locations/geocode") { if (!validateCsrf(request, response)) return; state.address = { ...state.address, latitude: "-34.6037000", longitude: "-58.3816000", needs_review: true, reviewed_at: null, geocode_source: "georef" }; return json(response, 200, state.address); }
  if (path === "/api/v1/locations/reverse-geocode") { if (!validateCsrf(request, response)) return; state.address = { ...state.address, latitude: String(body.latitude), longitude: String(body.longitude), normalized_address: "Avenida Rivadavia 2000", geocode_source: "manual", needs_review: true, reviewed_at: null }; return json(response, 200, { address: state.address, location: { formatted_address: "Avenida Rivadavia 2000, CABA" } }); }
  if (path === `/api/v1/addresses/${state.address.id}/confirm`) { if (!validateCsrf(request, response)) return; if (!['written', 'reverse'].includes(body.address_choice)) return json(response, 400, { address_choice: ["Opción inválida"] }); state.address = { ...state.address, latitude: body.latitude, longitude: body.longitude, needs_review: false, reviewed_at: "2026-08-20T11:00:00Z" }; return json(response, 200, state.address); }
  if (path === "/api/v1/billing-profiles") return json(response, 200, billing);
  if (path === "/api/v1/orders") return json(response, 200, []);
  if (path === "/api/v1/shipping/quote") { if (!validateCsrf(request, response)) return; return json(response, 200, { public_id: "22222222-2222-4222-8222-222222222222", service: "correo_argentino", parcels: [], base_amount: "4500.00", surcharge_amount: "0.00", total_amount: "4500.00", currency: "ARS", expires_at: "2026-08-20T23:59:00Z" }); }
  if (path === "/api/v1/shipping/quotes") { if (!validateCsrf(request, response)) return; return json(response, 200, { results: [{ public_id: "22222222-2222-4222-8222-222222222222", provider: "correo_argentino", provider_label: "API MiCorreo", service: "CP", parcels: [], base_amount: "4500.00", surcharge_amount: "0.00", total_amount: "4500.00", amount_pending: false, currency: "ARS", expires_at: "2026-08-20T23:59:00Z" }], errors: [], manual_fallback: false }); }
  if (path === "/api/v1/checkout") { if (!validateCsrf(request, response)) return; if (body.fulfillment_method === "pickup" && !state.pickupEnabled) return json(response, 400, { code: "pickup_unavailable", detail: "El retiro no está disponible en este momento." }); return json(response, 202, { order_id: "33333333-3333-4333-8333-333333333333", identity_status: state.checkoutRedirect ? "verified" : "pending_identity", payment_status: "not_started", shipping_cost_status: "ready", checkout_url: state.checkoutRedirect ? "http://127.0.0.1:4010/mock-mercado-pago" : "" }); }
  if (path.startsWith("/api/v1/payments/") && path.endsWith("/status")) return json(response, 200, { status: state.payments.length > 1 ? state.payments.shift() : state.payments[0] ?? "pending" });
  if (path.startsWith("/api/v1/orders/")) return json(response, 200, { public_id: path.split("/").at(-1), identity_status: "verified", payment_status: "paid", fulfillment_status: "shipped", fulfillment_method: "shipping", shipping_cost_status: "ready", customer_snapshot: {}, address_snapshot: { raw_address: "Av. Corrientes 1234, CABA" }, fiscal_snapshot: billing[0], coupon_code_snapshot: "", subtotal_snapshot: "12500.00", discount_snapshot: "0.00", shipping_amount_snapshot: "4500.00", total_snapshot: "17000.00", items: [{ product_name_snapshot: "Cuaderno A5", variant_name_snapshot: "Azul", sku_snapshot: "CUA-A5-AZ", quantity: 1, unit_price_snapshot: "12500.00", discount_snapshot: "0.00", line_total_snapshot: "12500.00" }], timeline: [{ status: "order_created", label: "Pedido creado", occurred_at: "2026-08-20T10:00:00Z" }, { status: "payment_paid", label: "Pago confirmado", occurred_at: "2026-08-20T10:05:00Z" }, { status: "fulfillment_shipped", label: "Pedido despachado", occurred_at: "2026-08-20T12:00:00Z" }], shipment: { carrier: "API MiCorreo", tracking_number: "CP123AR", status: "in_transit", updated_at: "2026-08-20T12:00:00Z" }, pickup_information: null, created_at: "2026-08-20T10:00:00Z" });
  return json(response, 404, { code: "not_found", detail: "Mock route not found" });
}).listen(Number(globalThis.process?.env.MOCK_PORT ?? 4010), globalThis.process?.env.MOCK_HOST ?? "127.0.0.1");
