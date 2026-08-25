import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { LoginForm, RegisterForm } from "@/components/account/auth-forms";
import { IntegrationEditor } from "@/components/management/integration-editor";
import { clearCsrfToken } from "@/lib/api";
import type { IntegrationConfiguration } from "@/lib/management/types";
import type { AuthConfiguration } from "@/lib/types";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

const authConfiguration: AuthConfiguration = {
  email_verification_required: false,
  google_enabled: true,
  google_client_id: "web-client.apps.googleusercontent.com",
};

const customer = {
  id: 9,
  email: "google@example.test",
  email_verified_at: "2026-08-21T12:00:00Z",
  is_staff: false,
  profile: { first_name: "Ana", last_name: "Pérez", phone: "+54 11 5555 1234" },
  masked_dni: "",
  masked_cuit: "",
};

describe("acceso y registro con Google", () => {
  beforeEach(() => {
    clearCsrfToken();
    push.mockClear();
    refresh.mockClear();
    vi.unstubAllGlobals();
  });

  test("muestra el botón oficial de Google sólo cuando la integración está configurada", async () => {
    const renderButton = vi.fn((container: HTMLElement) => {
      const button = document.createElement("button");
      button.textContent = "Acceder con Google";
      container.append(button);
    });
    Object.defineProperty(window, "google", {
      configurable: true,
      value: { accounts: { id: { initialize: vi.fn(), renderButton } } },
    });

    const { rerender } = render(
      <LoginForm authConfiguration={{ ...authConfiguration, google_enabled: false }} />,
    );
    expect(screen.queryByText("Acceder con Google")).not.toBeInTheDocument();

    rerender(<LoginForm authConfiguration={authConfiguration} />);
    await waitFor(() => expect(renderButton).toHaveBeenCalled());
    expect(screen.getByText("Acceder con Google")).toBeVisible();
  });

  test("sin correo transaccional el registro local salta la pantalla de código", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/auth/csrf/")) {
        return new Response(JSON.stringify({ csrf_token: "csrf-register" }), { status: 200 });
      }
      return new Response(JSON.stringify(customer), { status: 201 });
    }));
    render(<RegisterForm authConfiguration={{ ...authConfiguration, google_enabled: false }} />);

    fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: "Ana" } });
    fireEvent.change(screen.getByLabelText("Apellido"), { target: { value: "Pérez" } });
    fireEvent.change(screen.getByLabelText("Teléfono"), { target: { value: "+54 11 5555 1234" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ana@example.test" } });
    fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "StrongPassword!2026" } });
    fireEvent.click(screen.getByLabelText(/Acepto la política/));
    fireEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/cuenta/ingresar?registered=1"));
  });

  test("envía la credencial oficial de Google y conserva el carrito anónimo", async () => {
    let googleCallback: ((response: { credential?: string }) => void) | undefined;
    Object.defineProperty(window, "google", {
      configurable: true,
      value: {
        accounts: {
          id: {
            initialize: vi.fn((options: { callback: typeof googleCallback }) => { googleCallback = options.callback; }),
            renderButton: vi.fn(),
          },
        },
      },
    });
    sessionStorage.setItem("myc-cart-token", "signed-cart");
    const requests: Array<{ url: string; body: Record<string, unknown> }> = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith("/auth/csrf/")) {
        return new Response(JSON.stringify({ csrf_token: "csrf-google" }), { status: 200 });
      }
      requests.push({ url: String(input), body: JSON.parse(String(init?.body)) });
      return new Response(JSON.stringify(customer), { status: 200 });
    }));

    render(<LoginForm authConfiguration={authConfiguration} />);
    await waitFor(() => expect(googleCallback).toBeTypeOf("function"));
    await act(async () => { googleCallback?.({ credential: "verified-google-token" }); });

    await waitFor(() => expect(push).toHaveBeenCalledWith("/cuenta"));
    expect(requests).toEqual([{
      url: "/api/v1/auth/google/",
      body: { credential: "verified-google-token", mode: "login", cart_token: "signed-cart" },
    }]);
    expect(sessionStorage.getItem("myc-cart-token")).toBeNull();
  });

  test("completa el alta desde el ingreso cuando la cuenta de Google todavía no existe", async () => {
    let googleCallback: ((response: { credential?: string }) => void) | undefined;
    Object.defineProperty(window, "google", {
      configurable: true,
      value: {
        accounts: {
          id: {
            initialize: vi.fn((options: { callback: typeof googleCallback }) => { googleCallback = options.callback; }),
            renderButton: vi.fn(),
          },
        },
      },
    });
    sessionStorage.setItem("myc-cart-token", "new-customer-cart");
    const requests: Array<Record<string, unknown>> = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith("/auth/csrf/")) {
        return new Response(JSON.stringify({ csrf_token: "csrf-google-register" }), { status: 200 });
      }
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
      requests.push(body);
      if (body.mode === "login") {
        return new Response(JSON.stringify({
          code: "google_registration_required",
          detail: "Completá el registro para crear tu cuenta con Google.",
        }), { status: 409 });
      }
      return new Response(JSON.stringify(customer), { status: 201 });
    }));

    render(<LoginForm authConfiguration={authConfiguration} />);
    await waitFor(() => expect(googleCallback).toBeTypeOf("function"));
    await act(async () => { googleCallback?.({ credential: "new-google-token" }); });

    expect(await screen.findByRole("heading", { name: "Completá tu registro con Google" })).toBeVisible();
    fireEvent.change(screen.getByLabelText("Teléfono"), { target: { value: "+54 11 4444 3333" } });
    fireEvent.click(screen.getByLabelText(/Acepto la política/));
    fireEvent.click(screen.getByRole("button", { name: "Crear cuenta con Google" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/cuenta"));
    expect(requests).toEqual([
      {
        credential: "new-google-token",
        mode: "login",
        cart_token: "new-customer-cart",
      },
      {
        credential: "new-google-token",
        mode: "register",
        phone: "+54 11 4444 3333",
        consent_version: "privacy-v1",
        cart_token: "new-customer-cart",
      },
    ]);
    expect(sessionStorage.getItem("myc-cart-token")).toBeNull();
  });

  test("Administración permite habilitar Google con su Client ID web", () => {
    const integration: IntegrationConfiguration = {
      provider: "google_identity",
      label: "Acceso con Google",
      enabled: false,
      environment: "production",
      status: "incomplete",
      public_config: {},
      secret_fields: {},
      version: 0,
      updated_at: null,
      updated_by: "",
      last_test_status: "",
      last_tested_at: null,
      last_test_message: "",
    };

    render(<IntegrationEditor integration={integration} onSave={vi.fn()} />);

    expect(screen.getByLabelText("Client ID web de Google")).toBeVisible();
    expect(screen.getByText(/orígenes autorizados/i)).toBeVisible();
  });
});
