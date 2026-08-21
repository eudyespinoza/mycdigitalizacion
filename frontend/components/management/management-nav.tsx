"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";


const sections = [
  ["Inicio", "/gestion"],
  ["Catálogo", "/gestion/catalogo"],
  ["Inventario", "/gestion/inventario"],
  ["Pedidos", "/gestion/pedidos"],
  ["Clientes", "/gestion/clientes"],
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
          return <Link aria-current={active ? "page" : undefined} href={href} key={href} onClick={() => setOpen(false)}>{label}</Link>;
        })}
      </nav>
    </div>
  );
}
