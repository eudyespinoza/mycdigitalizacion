"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { managementRequest } from "@/lib/management/api";


const sections = [
  ["Inicio", "/gestion"],
  ["Catálogo", "/gestion/catalogo"],
  ["Inventario", "/gestion/inventario"],
  ["Pedidos", "/gestion/pedidos"],
  ["Clientes", "/gestion/clientes"],
  ["Consultas", "/gestion/consultas"],
  ["Contenido", "/gestion/contenido"],
  ["Promociones", "/gestion/promociones"],
  ["Envíos", "/gestion/envios"],
  ["Integraciones", "/gestion/integraciones"],
  ["Usuarios", "/gestion/usuarios"],
  ["Auditoría", "/gestion/auditoria"],
  ["Configuración", "/gestion/configuracion"],
] as const;


export function ManagementNav() {
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
  const current = sections.find(([, href]) => href === "/gestion" ? pathname === href : pathname.startsWith(href))?.[0] ?? "Gestión";
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
        {sections.map(([label, href]) => {
          const active = href === "/gestion" ? pathname === href : pathname.startsWith(href);
          const name = label === "Consultas" ? unread ? `Consultas, ${unread} sin leer` : "Consultas, sin consultas sin leer" : label;
          return <Link aria-current={active ? "page" : undefined} aria-label={name} href={href} key={href} onClick={() => setOpen(false)}>{label}{label === "Consultas" && unread ? <span aria-hidden="true">{unread}</span> : null}</Link>;
        })}
      </nav>
    </div>
  );
}
