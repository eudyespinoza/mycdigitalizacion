export type PublicAnalyticsEventType = "page_view" | "product_view";

export type AnalyticsDimensions = {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  referrer?: string;
};

export type AnalyticsClientEvent = {
  event_type: PublicAnalyticsEventType;
  path: string;
  product_id?: number;
  variant_id?: number;
  quantity?: number;
  dimensions?: AnalyticsDimensions;
};

export type AnalyticsEventPayload = AnalyticsClientEvent & {
  event_id: string;
};
