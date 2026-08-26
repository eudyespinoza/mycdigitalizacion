"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { managementRequest } from "@/lib/management/api";


const sections: ReadonlyArray<{ label: string; href: string; permission?: string }> = [
  { label: "Inicio", href: "/gestion" },
  { label: "Métricas web", href: "/gestion/metricas", permission: "analytics.view_web_analytics" },
  { label: "Compras y ventas", href: "/gestion/estadisticas", permission: "analytics.view_commercial_analytics" },
  { label: "Catálogo", href: "/gestion/catalogo" },
  { label: "Inventario", href: "/gestion/inventario" },
  { label: "Pedidos", href: "/gestion/pedidos" },
  { label: "Clientes", href: "/gestion/clientes" },
  { label: "Consultas", href: "/gestion/consultas" },
  { label: "Contenido", href: "/gestion/contenido" },
  { label: "Promociones", href: "/gestion/promociones" },
  { label: "Envíos", href: "/gestion/envios" },
  { label: "Integraciones", href: "/gestion/integraciones" },
  { label: "Usuarios", href: "/gestion/usuarios" },
  { label: "Auditoría", href: "/gestion/auditoria" },
  { label: "Configuración", href: "/gestion/configuracion" },
] as const;


export function ManagementNav({ permissions = [] }: { permissions?: string[] }) {
  const pathname = usePathname() ?? "";
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    let active = true;
    void managementRequest<{ unread: number }>("/support/summary/")
      .then((summary) => { if (active) setUnread(summary.unread); })
      .catch(() => { if (active) setUnread(0); });
    return () => { active = false; };
  }, []);
  const visibleSections = sections.filter((section) => !section.permission || permissions.includes(section.permission));
  const current = visibleSections.find(({ href }) => href === "/gestion" ? pathname === href : pathname.startsWith(href))?.label ?? "Gestión";
  return (
    <div className="management-navigation">
      <button
        aria-controls="management-menu"
        aria-expanded={open}
        className="management-menu-toggle"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <span>{current}</span>
        <span aria-hidden="true">{open ? "Cerrar" : "Menú"}</span>
      </button>
      <nav aria-label="Gestión de la tienda" className="management-nav" data-open={open} id="management-menu">
        {visibleSections.map(({ label, href }) => {
          const active = href === "/gestion" ? pathname === href : pathname.startsWith(href);
          const name = label === "Consultas" ? unread ? `Consultas, ${unread} sin leer` : "Consultas, sin consultas sin leer" : label;
          return <Link aria-current={active ? "page" : undefined} aria-label={name} href={href} key={href} onClick={() => setOpen(false)}>{label}{label === "Consultas" && unread ? <span aria-hidden="true">{unread}</span> : null}</Link>;
        })}
      </nav>
    </div>
  );
}
