import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { CartDrawer } from "@/components/cart/cart-drawer";
import { CartProvider } from "@/components/cart/cart-provider";
import { ProductCard } from "@/components/product/product-card";
import { clearCsrfToken } from "@/lib/api";
import type { Cart, Product } from "@/lib/types";

const product: Product = {
  id: 1,
  name: "Mochila urbana",
  slug: "mochila-urbana",
  description: "Mochila de uso diario",
  category: { id: 1, name: "Mochilas", slug: "mochilas", parent_id: null },
  brand: null,
  available_stock: 5,
  is_available: true,
  effective_price: "35000.00",
  on_offer: false,
  variants: [
    {
      id: 11,
      sku: "MOC-AZ",
      name: "Azul",
      price: "35000.00",
      available_stock: 2,
      is_available: true,
      stock_is_infinite: false,
      purchase_limit: 2,
      attributes: [],
      pricing: { list_price: "35000.00", effective_price: "35000.00", discount_amount: "0.00", discount_percentage: "0.00", on_offer: false },
      packaged_weight_grams: 800,
      length_cm: "45.00",
      width_cm: "30.00",
      height_cm: "18.00",
      volume_cm3: "24300.000000",
    },
    {
      id: 12,
      sku: "MOC-RO",
      name: "Rosa",
      price: "35000.00",
      available_stock: 3,
      is_available: true,
      stock_is_infinite: false,
      purchase_limit: 3,
      attributes: [],
      pricing: { list_price: "35000.00", effective_price: "35000.00", discount_amount: "0.00", discount_percentage: "0.00", on_offer: false },
      packaged_weight_grams: 800,
      length_cm: "45.00",
      width_cm: "30.00",
      height_cm: "18.00",
      volume_cm3: "24300.000000",
    },
  ],
  media: [],
};

const emptyCart: Cart = {
  cart_token: "cart-token",
  coupon: null,
  subtotal: "0.00",
  discount: "0.00",
  total: "0.00",
  active_checkout: null,
  lines: [],
};

function cartWithLines(lines: Cart["lines"]): Cart {
  return {
    ...emptyCart,
    subtotal: "105000.00",
    total: "105000.00",
    lines,
  };
}

function line(variantId: number, variantName: string, quantity: number): Cart["lines"][number] {
  return {
    id: variantId,
    variant_id: variantId,
    sku: `SKU-${variantId}`,
    product_name: product.name,
    variant_name: variantName,
    quantity,
    unit_price: "35000.00",
    line_subtotal: String(35000 * quantity),
    line_discount: "0.00",
    line_total: String(35000 * quantity),
    availability: "available",
    available_stock: 5,
    stock_is_infinite: false,
    purchase_limit: 5,
    notices: [],
  };
}

function stubCart(initial: Cart, afterAdd = initial) {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/auth/csrf/")) {
      return new Response(JSON.stringify({ csrf_token: "csrf-card" }), { status: 200 });
    }
    if (url.endsWith("/cart/") && init?.method === "POST") {
      return new Response(JSON.stringify(afterAdd), { status: 200 });
    }
    if (url.endsWith("/cart/")) {
      return new Response(JSON.stringify(initial), { status: 200 });
    }
    return new Response(null, { status: 404 });
  }));
}

describe("compra desde las tarjetas de producto", () => {
  beforeEach(() => {
    clearCsrfToken();
    sessionStorage.clear();
  });

  afterEach(() => vi.unstubAllGlobals());

  test("agrega directamente una variante única y mantiene cerrado el carrito lateral", async () => {
    const singleVariantProduct = { ...product, variants: [product.variants[0]] };
    stubCart(emptyCart, cartWithLines([line(11, "Azul", 1)]));

    render(<CartProvider><ProductCard product={singleVariantProduct} /><CartDrawer /></CartProvider>);

    const card = screen.getByRole("article", { name: product.name });
    const add = within(card).getByRole("button", { name: "Agregar al carrito" });
    await waitFor(() => expect(add).toBeEnabled());
    fireEvent.click(add);

    expect(await within(card).findByText("En carrito · 1")).toBeVisible();
    expect(card).toHaveClass("is-in-cart");
    expect(within(card).getByRole("button", { name: "Agregar otro" })).toBeVisible();
    expect(screen.queryByRole("dialog", { name: "Tu carrito" })).not.toBeInTheDocument();
  });

  test("solicita elegir una variante antes de agregar un producto con opciones", async () => {
    stubCart(emptyCart, cartWithLines([line(12, "Rosa", 1)]));

    render(<CartProvider><ProductCard product={product} /></CartProvider>);

    const card = screen.getByRole("article", { name: product.name });
    const choose = within(card).getByRole("button", { name: "Elegir opción" });
    await waitFor(() => expect(choose).toBeEnabled());
    fireEvent.click(choose);

    fireEvent.change(within(card).getByLabelText(`Opción para ${product.name}`), { target: { value: "12" } });
    fireEvent.click(within(card).getByRole("button", { name: "Agregar Rosa" }));

    expect(await within(card).findByText("En carrito · 1")).toBeVisible();
    expect(within(card).getByRole("button", { name: "Agregar otro" })).toBeVisible();
  });

  test("suma en la card las cantidades de todas las variantes del producto", async () => {
    stubCart(cartWithLines([line(11, "Azul", 2), line(12, "Rosa", 1)]));

    render(<CartProvider><ProductCard product={product} /></CartProvider>);

    const card = screen.getByRole("article", { name: product.name });
    expect(await within(card).findByText("En carrito · 3")).toBeVisible();
    expect(card).toHaveClass("is-in-cart");
  });

  test("deshabilita la compra cuando el producto no tiene variantes disponibles", async () => {
    stubCart(emptyCart);
    const unavailable = {
      ...product,
      is_available: false,
      variants: product.variants.map((variant) => ({ ...variant, is_available: false })),
    };

    render(<CartProvider><ProductCard product={unavailable} /></CartProvider>);

    const card = screen.getByRole("article", { name: product.name });
    expect(within(card).getByRole("button", { name: "Sin stock" })).toBeDisabled();
  });
});
