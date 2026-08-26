import Link from "next/link";
import type { ReactNode } from "react";

import { ManagementNav } from "@/components/management/management-nav";
import type { ManagementSession } from "@/lib/management/types";


export function ManagementShell({
  session,
  children,
}: {
  session: ManagementSession;
  children: ReactNode;
}) {
  const name = [session.user.first_name, session.user.last_name].filter(Boolean).join(" ");
  return (
    <div className="management-app">
      <aside className="management-sidebar">
        <Link className="management-brand" href="/gestion" aria-label="Inicio de Administración">
          Administración
        </Link>
        <ManagementNav permissions={session.user.permissions} />
        <div className="management-user">
          <strong>{name || "Equipo myc"}</strong>
          <span>{session.user.email}</span>
          <Link href="/">Ver tienda</Link>
        </div>
      </aside>
      <main className="management-main" id="contenido-gestion">{children}</main>
    </div>
  );
}
