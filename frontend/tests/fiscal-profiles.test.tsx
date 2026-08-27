import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { FiscalProfiles } from "@/components/account/fiscal-profiles";

afterEach(() => vi.unstubAllGlobals());

function completeForm(identifier = "12.345.678") {
  fireEvent.change(screen.getByLabelText("Etiqueta"), { target: { value: "Compras" } });
  fireEvent.change(screen.getByLabelText("Razón social o nombre"), {
    target: { value: "Cliente Prueba" },
  });
  fireEvent.change(screen.getByLabelText("CUIT o DNI"), {
    target: { value: identifier },
  });
}

test("valida CUIT o DNI automáticamente y muestra el CUIT guardado", async () => {
  let saved = false;
  let resolvePost: ((response: Response) => void) | undefined;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), "http://localhost").pathname;
    if (path === "/api/v1/auth/csrf/") {
      return new Response(JSON.stringify({ csrf_token: "token" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (path === "/api/v1/billing-profiles/" && init?.method === "POST") {
      return await new Promise<Response>((resolve) => {
        resolvePost = (response) => {
          saved = true;
          resolve(response);
        };
      });
    }
    if (path === "/api/v1/billing-profiles/") {
      return new Response(JSON.stringify(saved ? [{
        id: 1,
        label: "Compras",
        legal_name: "Cliente Prueba",
        tax_condition: "consumidor_final",
        is_default: false,
        masked_cuit: "••-••••••••-6",
      }] : []), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(null, { status: 404 });
  }));

  render(<FiscalProfiles />);
  completeForm();
  fireEvent.click(screen.getByRole("button", { name: "Guardar perfil" }));

  expect(await screen.findByRole("button", { name: "Validando con ARCA…" })).toBeDisabled();
  await waitFor(() => expect(resolvePost).toBeTypeOf("function"));
  resolvePost?.(new Response(JSON.stringify({ id: 1 }), {
    status: 201,
    headers: { "Content-Type": "application/json" },
  }));

  expect(await screen.findByText("Perfil fiscal guardado.")).toBeVisible();
  expect(await screen.findByText("••-••••••••-6")).toBeVisible();
});

test("muestra el mensaje de validación fiscal devuelto por el backend", async () => {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), "http://localhost").pathname;
    if (path === "/api/v1/auth/csrf/") {
      return new Response(JSON.stringify({ csrf_token: "token" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (path === "/api/v1/billing-profiles/" && init?.method === "POST") {
      return new Response(JSON.stringify({
        cuit: ["La validación ARCA no está configurada. Ingresá el CUIT completo de 11 dígitos."],
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(JSON.stringify([]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }));

  render(<FiscalProfiles />);
  completeForm();
  fireEvent.click(screen.getByRole("button", { name: "Guardar perfil" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "La validación ARCA no está configurada. Ingresá el CUIT completo de 11 dígitos.",
  );
});
