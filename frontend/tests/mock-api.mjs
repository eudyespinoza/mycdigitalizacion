import http from "node:http";
import { URL } from "node:url";

const categories = [
  { id: 1, name: "Tecnología", slug: "tecnologia", parent_id: null },
  { id: 2, name: "Papelería", slug: "papeleria", parent_id: null },
  { id: 3, name: "Hogar", slug: "hogar", parent_id: null },
];
const variant = { id: 11, sku: "CUA-A5-AZ", name: "Azul", price: "12500.00", packaged_weight_grams: 300, length_cm: "21.00", width_cm: "15.00", height_cm: "2.00", volume_cm3: "630.000000" };
const products = [{ id: 7, name: "Cuaderno A5", slug: "cuaderno-a5", description: "Cuaderno de tapa rígida para estudio y oficina.", category: categories[1], variants: [variant], media: [{ file: "/campaigns/pulso-libreria-collection.png", alt_text: "Cuadernos y útiles en tonos azul y cyan", order: 1 }] }];
let cart = { lines: [], subtotal: "0.00", discount: "0.00", total: "0.00", cart_token: "mock-cart-token", coupon: null };
const json = (response, status, body) => { response.writeHead(status, { "content-type": "application/json", "access-control-allow-origin": "*" }); response.end(body === undefined ? "" : JSON.stringify(body)); };
const read = (request) => new Promise((resolve) => { let data = ""; request.on("data", (chunk) => { data += chunk; }); request.on("end", () => { try { resolve(data ? JSON.parse(data) : {}); } catch { resolve({}); } }); });

http.createServer(async (request, response) => {
  const url = new URL(request.url, "http://127.0.0.1:4010");
  const path = url.pathname.replace(/\/$/, "");
  if (request.method === "OPTIONS") return json(response, 204);
  if (path === "/api/v1/storefront/home") return json(response, 200, { settings: { public_name: "mycdigitalizacion", announcement: "", contact_email: "" }, hero_slides: [{ id: 1, title: "Todo lo que buscás, en un solo lugar", body: "Tecnología, papelería, hogar y más para descubrir.", alt_text: "Cuaderno, botella y accesorios de escritorio en azul, blanco y magenta", desktop_image_url: "/campaigns/pulso-comercial-hero.png", mobile_image_url: "", cta_label: "Explorar catálogo", cta_url: "/catalogo", focal_x: 50, focal_y: 50, safe_height_mobile: 420, safe_height_tablet: 520, safe_height_desktop: 620, starts_at: null, ends_at: null, order: 1 }], promotion_slides: [], collections: [], promotion_popups: [] });
  if (path === "/api/v1/categories") return json(response, 200, categories);
  if (path === "/api/v1/products" || path === "/api/v1/search") return json(response, 200, products);
  if (path === "/api/v1/products/cuaderno-a5") return json(response, 200, products[0]);
  if (path === "/api/v1/auth/csrf") return json(response, 200, { csrf_token: "mock-csrf" });
  if (path === "/api/v1/cart") {
    const body = await read(request);
    if (request.method === "POST" && body.variant_id) cart = { ...cart, lines: [{ id: 1, variant_id: 11, sku: "CUA-A5-AZ", quantity: body.quantity, unit_price: "12500.00" }], subtotal: String(12500 * body.quantity) + ".00", total: String(12500 * body.quantity) + ".00" };
    if (request.method === "PATCH") cart = body.quantity > 0 ? { ...cart, lines: cart.lines.map((line) => ({ ...line, quantity: body.quantity })), subtotal: String(12500 * body.quantity) + ".00", total: String(12500 * body.quantity) + ".00" } : { ...cart, lines: [], subtotal: "0.00", total: "0.00" };
    return json(response, request.method === "POST" ? 201 : 200, cart);
  }
  if (path === "/api/v1/addresses") return json(response, 200, [{ id: 2, label: "Casa", raw_address: "Av. Corrientes 1234, CABA", normalized_address: "Avenida Corrientes 1234", street: "Av. Corrientes", number: "1234", postal_code: "1043", cpa: "C1043", locality: "CABA", province: "CABA", latitude: "-34.6037000", longitude: "-58.3816000", floor: "", apartment: "", reference: "", notes: "", geocode_source: "georef", geocode_confidence: "0.950", geocode_summary: {}, needs_review: false, reviewed_at: null, created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z" }]);
  if (path === "/api/v1/billing-profiles") return json(response, 200, [{ id: 3, label: "Personal", legal_name: "Cliente sintético de prueba", tax_condition: "consumidor_final", is_default: true, masked_cuit: "20-********-3" }]);
  if (path === "/api/v1/shipping/quote") return json(response, 200, { public_id: "22222222-2222-4222-8222-222222222222", service: "correo_argentino", parcels: [], base_amount: "4500.00", surcharge_amount: "0.00", total_amount: "4500.00", currency: "ARS", expires_at: "2026-08-20T23:59:00Z" });
  if (path === "/api/v1/checkout") return json(response, 202, { order_id: "33333333-3333-4333-8333-333333333333", identity_status: "pending_review", payment_status: "pending", checkout_url: "" });
  return json(response, 404, { code: "not_found", detail: "Mock route not found" });
}).listen(4010, "127.0.0.1");
