import Link from "next/link";

import { ManagementShell } from "@/components/management/management-shell";
import {
  ManagementServerError,
  managementServerGet,
} from "@/lib/management/server-api";
import type { ManagementSession } from "@/lib/management/types";


export const dynamic = "force-dynamic";


export default async function ManagementLayout({ children }: { children: React.ReactNode }) {
  try {
    const session = await managementServerGet<ManagementSession>("/session/");
    return <ManagementShell session={session}>{children}</ManagementShell>;
  } catch (cause) {
    const forbidden = cause instanceof ManagementServerError && cause.status === 403;
    return (
      <main className="management-access-state">
        <p className="management-kicker">Panel de gestión</p>
        <h1>{forbidden ? "Esta cuenta no tiene acceso" : "Ingresá para administrar la tienda"}</h1>
        <p>
          {forbidden
            ? "Necesitás un usuario interno habilitado por el propietario."
            : "Usá tu cuenta del equipo para continuar."}
        </p>
        <Link className="button primary" href="/cuenta/ingresar?next=/gestion">Ingresar</Link>
      </main>
    );
  }
}
