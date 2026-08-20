import Link from "next/link";


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
  return (
    <nav aria-label="Gestión de la tienda" className="management-nav">
      {sections.map(([label, href]) => (
        <Link href={href} key={href}>{label}</Link>
      ))}
    </nav>
  );
}
