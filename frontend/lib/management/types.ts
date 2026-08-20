export type ManagementUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  permissions: string[];
};

export type ManagementSession = { user: ManagementUser };

export type ManagementDashboard = {
  metrics: {
    active_products: number;
    low_stock_variants: number;
    orders_requiring_attention: number;
    integration_incidents: number;
  };
};
