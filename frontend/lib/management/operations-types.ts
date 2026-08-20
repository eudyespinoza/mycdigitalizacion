export type ManagementOrder = {
  public_id: string;
  customer: { id: number; name: string; email: string; phone: string };
  identity_status: string;
  payment_status: string;
  fulfillment_status: string;
  fulfillment_method: string;
  total: string;
  created_at: string;
};

export type ManagementOrderDetail = ManagementOrder & {
  customer_snapshot: Record<string, unknown>;
  address_snapshot: Record<string, unknown>;
  fiscal_snapshot: Record<string, unknown>;
  subtotal: string;
  discount: string;
  shipping_amount: string;
  items: Array<{
    product_name: string;
    variant_name: string;
    sku: string;
    quantity: number;
    unit_price: string;
    discount: string;
    total: string;
  }>;
  audit_events: Array<{
    kind: string;
    data: Record<string, unknown>;
    actor: string;
    created_at: string;
  }>;
  payments: Array<{
    provider: string;
    status: string;
    provider_status: string;
    payment_id: string | null;
    amount: string;
    currency: string;
    created_at: string;
  }>;
  shipment: null | {
    provider: string;
    tracking_number: string;
    status: string;
    label_url: string;
    updated_at: string;
  };
};

export type ManagementCustomer = {
  id: number;
  name: string;
  email: string;
  phone: string;
  masked_dni: string;
  email_verified: boolean;
  order_count: number;
  total_spent: string;
};

export type ManagementCustomerDetail = ManagementCustomer & {
  addresses: Array<{
    id: number;
    label: string;
    raw_address: string;
    normalized_address: string;
    street: string;
    number: string;
    postal_code: string;
    locality: string;
    province: string;
    floor: string;
    apartment: string;
    reference: string;
    needs_review: boolean;
  }>;
  billing_profiles: Array<{
    id: number;
    label: string;
    legal_name: string;
    tax_condition: string;
    masked_cuit: string;
    is_default: boolean;
  }>;
  orders: ManagementOrder[];
};

export type ShippingBox = {
  id: number;
  code: string;
  inner_length_cm: string;
  inner_width_cm: string;
  inner_height_cm: string;
  tare_weight_grams: number;
  max_weight_grams: number;
  enabled: boolean;
};
