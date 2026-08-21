import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { LoginForm } from "@/components/account/auth-forms";
import { CartProvider } from "@/components/cart/cart-provider";
import { clearCsrfToken } from "@/lib/api";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

const customer = {
  id: 1,
  email: "admin@mycdigitalizacion.local",
  email_verified_at: "2026-08-20T10:00:00Z",
  is_staff: true,
  profile: { first_name: "Admin", last_name: "MYC", phone: "" },
  masked_dni: "",
  masked_cuit: "",
};

describe("stale anonymous carts", () => {
  beforeEach(() => {
    clearCsrfToken();
    sessionStorage.clear();
    push.mockClear();
    refresh.mockClear();
  });

  test("a missing anonymous cart is removed from browser storage", async () => {
    sessionStorage.setItem("myc-cart-token", "stale-cart-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ code: "cart_not_found", detail: "Cart not found" }), {
          status: 404,
        }),
      ),
    );

    render(<CartProvider><span>Tienda</span></CartProvider>);

    await waitFor(() => expect(sessionStorage.getItem("myc-cart-token")).toBeNull());
  });

  test("a successful login discards the merged anonymous cart token", async () => {
    sessionStorage.setItem("myc-cart-token", "anonymous-cart-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).endsWith("/auth/csrf/")) {
          return new Response(JSON.stringify({ csrf_token: "csrf-login" }), { status: 200 });
        }
        return new Response(JSON.stringify(customer), { status: 200 });
      }),
    );
    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "admin@mycdigitalizacion.local" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "Correct-Horse-Battery-Staple-42" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/cuenta"));
    expect(sessionStorage.getItem("myc-cart-token")).toBeNull();
  });
});
