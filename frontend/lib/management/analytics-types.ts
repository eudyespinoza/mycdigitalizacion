export type AnalyticsPeriod = {
  from: string;
  to: string;
  timezone: string;
};

export type FunnelStep = {
  count: number;
  rate: string | null;
  has_denominator: boolean;
};

export type WebAnalyticsReport = {
  period: AnalyticsPeriod;
  data_since: string | null;
  coverage: { attribution_percentage: string | null; has_denominator: boolean };
  kpis: {
    sessions: number;
    visitors: number;
    conversion_rate: string | null;
    attributed_revenue: string;
    average_ticket: string | null;
    checkout_abandonment: string | null;
  };
  funnel: Record<"sessions" | "product" | "cart" | "checkout" | "delivery" | "payment" | "paid", FunnelStep>;
  series: Array<{ date: string; sessions: number; carts: number; orders: number }>;
  tables: {
    products: Array<{ product_id: number; name: string; views: number; cart_additions: number; cart_rate: string | null }>;
    channels: Array<{ source: string; medium: string; campaign: string; sessions: number; conversion_rate: string | null; revenue: string }>;
    devices: Array<{ device: string; sessions: number; conversion_rate: string | null; revenue: string }>;
  };
  comparison: Partial<WebAnalyticsReport["kpis"]> | null;
};

export type CommercialAnalyticsReport = {
  period: AnalyticsPeriod;
  data_since: string | null;
  filters: { category: number | null; brand: number | null; coverage_days: number };
  coverage: { attribution_percentage: string | null; cost_percentage: string | null };
  kpis: {
    net_sales: string;
    paid_orders: number;
    net_units: string;
    average_ticket: string | null;
    discounts: string;
    refunds: string;
    gross_product_margin: string;
    inventory_value: string;
    reorder_variants: number;
  };
  series: Array<{ date: string; sales: string; refunds: string; net_sales: string }>;
  tables: {
    skus: Array<{
      sku: string;
      product_id: number | null;
      product: string;
      category: string;
      units: string;
      revenue: string;
      margin: string;
      cost_covered: boolean;
    }>;
    reorder: Array<ReorderRow>;
    no_movement: Array<ReorderRow>;
  };
  comparison: Partial<CommercialAnalyticsReport["kpis"]> | null;
};

export type ReorderRow = {
  variant_id: number;
  sku: string;
  product: string;
  stock: number;
  sold_units: string;
  daily_velocity: string;
  stock_coverage_days: string | null;
  suggested_units: number;
};

export type AnalyticsFilters = {
  from: string;
  to: string;
  compare: boolean;
  coverageDays: 15 | 30 | 60;
  category: number | null;
  brand: number | null;
};
