import type { IntegrationProvider } from "@/lib/management/types";


export type IntegrationField = {
  key: string;
  label: string;
  type?: "text" | "url" | "email" | "number" | "boolean" | "password" | "select";
  hint?: string;
  options?: Array<{ value: string; label: string }>;
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
    description: "Cotizaciones, alta de envíos y seguimiento con API MiCorreo.",
    public: [
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
  andreani: {
    description: "Cotización, órdenes, etiquetas y seguimiento con Andreani.",
    public: [
      { key: "customer_id", label: "Código de cliente" },
      { key: "contract", label: "Número de contrato" },
      { key: "origin_postal_code", label: "Código postal de origen" },
      { key: "origin_street", label: "Calle de origen" },
      { key: "origin_number", label: "Altura de origen" },
      { key: "origin_city", label: "Localidad de origen" },
      { key: "origin_province", label: "Provincia de origen" },
      { key: "sender_name", label: "Nombre o razón social del remitente" },
      { key: "sender_email", label: "Email del remitente", type: "email" },
      { key: "sender_phone", label: "Teléfono del remitente" },
      { key: "sender_document_type", label: "Tipo de documento del remitente" },
      { key: "sender_document_number", label: "DNI o CUIT del remitente" },
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
  google_identity: {
    description: "Registro e ingreso con el botón oficial de Google.",
    public: [
      {
        key: "client_id",
        label: "Client ID web de Google",
        hint: "Crealo como aplicación web y agregá el dominio de la tienda a los orígenes autorizados.",
      },
    ],
    secrets: [],
  },
  geolocation: {
    description: "OpenStreetMap funciona por defecto; Google Maps es una alternativa opcional.",
    public: [
      {
        key: "provider",
        label: "Proveedor del mapa",
        type: "select",
        options: [
          { value: "openstreetmap", label: "OpenStreetMap (recomendado)" },
          { value: "google_maps", label: "Google Maps" },
        ],
      },
      {
        key: "google_maps_map_id",
        label: "ID de mapa de Google (opcional)",
        hint: "Si lo dejás vacío se usa el mapa estándar de Google.",
      },
    ],
    secrets: [
      {
        key: "google_maps_browser_key",
        label: "Clave de navegador de Google Maps",
        type: "password",
        hint: "Usá una clave exclusiva para Maps JavaScript API y restringila por dominio.",
      },
    ],
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
