import type { IntegrationProvider } from "@/lib/management/types";


export type IntegrationField = {
  key: string;
  label: string;
  type?: "text" | "url" | "email" | "number" | "boolean" | "password";
  hint?: string;
};


export const integrationFields: Record<
  IntegrationProvider,
  { description: string; public: IntegrationField[]; secrets: IntegrationField[] }
> = {
  mercadopago: {
    description: "Cobros con Checkout Pro, conciliación, cancelaciones y reintegros.",
    public: [
      { key: "collector_id", label: "Collector ID" },
      { key: "live_mode", label: "Usar modo producción", type: "boolean" },
    ],
    secrets: [
      { key: "access_token", label: "Access token", type: "password" },
      { key: "webhook_secret", label: "Secreto del webhook", type: "password" },
    ],
  },
  correo_argentino: {
    description: "Cotizaciones, alta de envíos y seguimiento con MiCorreo.",
    public: [
      { key: "base_url", label: "URL de la API", type: "url" },
      { key: "customer_id", label: "ID de cliente" },
      { key: "origin_postal_code", label: "Código postal de origen" },
      { key: "surcharge_type", label: "Tipo de recargo" },
      { key: "surcharge_value", label: "Valor del recargo", type: "number" },
      { key: "free_shipping_threshold", label: "Envío gratis desde", type: "number" },
    ],
    secrets: [
      { key: "username", label: "Usuario", type: "password" },
      { key: "password", label: "Contraseña", type: "password" },
    ],
  },
  sid_renaper: {
    description: "Validación de identidad del titular mediante SID RENAPER.",
    public: [{ key: "base_url", label: "URL de SID", type: "url" }],
    secrets: [{ key: "access_token", label: "Access token", type: "password" }],
  },
  smtp: {
    description: "Mensajes de verificación, pedidos, pagos y seguimiento.",
    public: [
      { key: "host", label: "Servidor SMTP" },
      { key: "port", label: "Puerto", type: "number" },
      { key: "use_tls", label: "Usar conexión segura TLS", type: "boolean" },
      { key: "from_email", label: "Email remitente", type: "email" },
    ],
    secrets: [
      { key: "username", label: "Usuario", type: "password" },
      { key: "password", label: "Contraseña", type: "password" },
    ],
  },
  geolocation: {
    description: "Mapa, teselas y normalización de direcciones.",
    public: [
      { key: "provider", label: "Proveedor" },
      { key: "tile_url", label: "URL de teselas", type: "url" },
      { key: "attribution", label: "Atribución visible" },
    ],
    secrets: [],
  },
  backups: {
    description: "Copias externas cifradas y política de retención.",
    public: [
      { key: "repository", label: "Repositorio" },
      { key: "region", label: "Región" },
      { key: "retention_days", label: "Retención en días", type: "number" },
    ],
    secrets: [
      { key: "access_key", label: "Clave de acceso", type: "password" },
      { key: "secret_key", label: "Clave secreta", type: "password" },
      { key: "repository_password", label: "Contraseña del repositorio", type: "password" },
    ],
  },
};
