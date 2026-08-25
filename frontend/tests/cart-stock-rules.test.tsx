import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { CartDrawer } from "@/components/cart/cart-drawer";
import { CartPage } from "@/components/cart/cart-page";
import { ProductPurchase } from "@/components/product/product-purchase";

const cartState = vi.hoisted(() => ({ current: null as unknown }));

vi.mock("@/components/cart/cart-provider", () => ({
  useCart: () => cartState.current,
}));

describe("reglas públicas de stock y cantidad", () => {
  test("el carrito muestra producto y variante sin exponer el SKU", () => {
    cartState.current = {
      open: true,
      loading: false,
      error: "",
      setOpen: vi.fn(),
      restoreFocus: vi.fn(),
      setQuantity: vi.fn(),
      remove: vi.fn(),
      cart: {
        cart_token: "cart-token",
        coupon: null,
        subtotal: "9750.00",
        discount: "0.00",
        total: "9750.00",
        lines: [{
          id: 1,
          variant_id: 5,
          sku: "MYC-LIB-TAP-80",
          product_name: "Libreta tapa dura",
          variant_name: "80 Hojas",
          quantity: 1,
          unit_price: "9750.00",
          line_subtotal: "9750.00",
          line_discount: "0.00",
          line_total: "9750.00",
          availability: "available",
          available_stock: 25,
          stock_is_infinite: false,
          purchase_limit: 25,
          notices: [],
        }],
      },
    };

    render(<CartDrawer />);

    expect(screen.getByText("Libreta tapa dura")).toBeVisible();
    expect(screen.getByText("80 Hojas")).toBeVisible();
    expect(document.body).not.toHaveTextContent("MYC-LIB-TAP-80");
  });

  test("una variante infinita usa sólo el máximo opcional de la compra", () => {
    render(
      <ProductPurchase
        productName="Libreta tapa dura"
        variants={[{
          id: 6,
          sku: "MYC-LIB-TAP-60",
          name: "60 Hojas",
          price: "7650.00",
          available_stock: 0,
          is_available: true,
          stock_is_infinite: true,
          purchase_limit: 12,
          attributes: [],
          pricing: { list_price: "7650.00", effective_price: "7650.00", discount_amount: "0.00", discount_percentage: "0.00", on_offer: false },
          packaged_weight_grams: 126,
          length_cm: "22.00",
          width_cm: "18.00",
          height_cm: "4.00",
          volume_cm3: "1584.000000",
        }]}
        onAdd={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Agregar al carrito" })).toBeEnabled();
    expect(screen.getByLabelText("Cantidad")).toHaveAttribute("max", "12");
    expect(screen.getByRole("option", { name: "60 Hojas" })).toBeEnabled();
  });

  test.each([
    ["el carrito lateral", <CartDrawer />],
    ["la página del carrito", <CartPage />],
  ])("confirma el vaciado en %s con un diálogo propio", async (_surface, component) => {
    const clear = vi.fn().mockResolvedValue(undefined);
    const nativeConfirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    cartState.current = {
      open: true,
      loading: false,
      error: "",
      setOpen: vi.fn(),
      restoreFocus: vi.fn(),
      setQuantity: vi.fn(),
      remove: vi.fn(),
      clear,
      applyCoupon: vi.fn(),
      refresh: vi.fn(),
      cart: {
        cart_token: "cart-token",
        coupon: "COMPRA10",
        subtotal: "9750.00",
        discount: "975.00",
        total: "8775.00",
        lines: [{
          id: 1,
          variant_id: 5,
          sku: "MYC-LIB-TAP-80",
          product_name: "Libreta tapa dura",
          variant_name: "80 Hojas",
          quantity: 1,
          unit_price: "9750.00",
          line_subtotal: "9750.00",
          line_discount: "975.00",
          line_total: "8775.00",
          availability: "available",
          available_stock: 25,
          stock_is_infinite: false,
          purchase_limit: 25,
          notices: [],
        }],
      },
    };

    render(component);
    fireEvent.click(screen.getByRole("button", { name: "Vaciar carrito" }));

    const dialog = screen.getByRole("dialog", { name: "¿Vaciar todo el carrito?" });
    expect(dialog).toBeVisible();
    expect(within(dialog).getByText(/Se quitarán todos los productos y el cupón aplicado/)).toBeVisible();
    expect(nativeConfirm).not.toHaveBeenCalled();
    expect(clear).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole("button", { name: "Cancelar" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "¿Vaciar todo el carrito?" })).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Vaciar carrito" }));
    fireEvent.click(within(screen.getByRole("dialog", { name: "¿Vaciar todo el carrito?" })).getByRole("button", { name: "Vaciar carrito" }));
    await waitFor(() => expect(clear).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "¿Vaciar todo el carrito?" })).not.toBeInTheDocument());
    nativeConfirm.mockRestore();
  });

  test.each([
    ["el carrito lateral", <CartDrawer />],
    ["la página del carrito", <CartPage />],
  ])("continúa el pedido existente con el envío ya configurado en %s", (_surface, component) => {
    cartState.current = {
      open: true,
      loading: false,
      error: "",
      setOpen: vi.fn(),
      restoreFocus: vi.fn(),
      setQuantity: vi.fn(),
      remove: vi.fn(),
      clear: vi.fn(),
      applyCoupon: vi.fn(),
      refresh: vi.fn(),
      cart: {
        cart_token: "cart-token",
        coupon: null,
        subtotal: "2499.00",
        discount: "0.00",
        total: "2499.00",
        active_checkout: {
          order_id: "10c0a7e6-d036-5318-b277-5ada30453bde",
          identity_status: "verified",
          payment_status: "pending",
          shipping_cost_status: "ready",
          shipping_amount: "24565.00",
          total: "27064.00",
          can_resume: true,
        },
        lines: [{
          id: 1,
          variant_id: 5,
          sku: "VOLIGOMA",
          product_name: "Adhesivo Voligoma",
          variant_name: "Voligoma adhesivo",
          quantity: 1,
          unit_price: "2499.00",
          line_subtotal: "2499.00",
          line_discount: "0.00",
          line_total: "2499.00",
          availability: "available",
          available_stock: 25,
          stock_is_infinite: false,
          purchase_limit: 25,
          notices: [],
        }],
      },
    };

    render(component);

    expect(screen.getByText("Compra en curso")).toBeVisible();
    expect(screen.getByText(/Envío.*24\.565,00/)).toBeVisible();
    expect(screen.getByText(/Total.*27\.064,00/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Continuar pedido" })).toHaveAttribute(
      "href",
      "/pedidos/10c0a7e6-d036-5318-b277-5ada30453bde",
    );
  });
});
