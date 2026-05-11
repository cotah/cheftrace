export interface Restaurant {
  id: string;
  name: string;
  city: string | null;
  country: string;
  timezone: string;
  currency: string;
  expiry_warning_days: number;
  critical_expiry_days: number;
  role?: string | null;
}

export interface Category {
  id: string;
  name: string;
  is_active: boolean;
}

export interface Supplier {
  id: string;
  name: string;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  is_active: boolean;
}

export interface Product {
  id: string;
  name: string;
  sku: string | null;
  unit: string;
  category_id: string | null;
  expiry_required: boolean;
  storage_type: string | null;
  is_active: boolean;
  unit_cost?: number | null;
  minimum_stock_quantity?: number | null;
}

export interface StockLot {
  id: string;
  product_id: string;
  supplier_id: string | null;
  quantity_received: number;
  quantity_remaining: number;
  unit: string;
  unit_cost?: number | null;
  expiry_date: string | null;
  received_date: string;
  status: "active" | "depleted" | "expired" | "discarded";
  notes: string | null;
  created_by_user_id: string;
  created_at: string;
}

export interface StockMovement {
  id: string;
  product_id: string;
  lot_id: string | null;
  kind: string;
  source: string;
  quantity: number;
  unit: string;
  reason: string | null;
  notes: string | null;
  created_by_user_id: string;
  created_at: string;
}

export interface ExpiryAlert {
  lot_id: string;
  product_id: string;
  product_name: string;
  expiry_date: string;
  days_left: number;
  quantity_remaining: number;
  unit: string;
}

export interface LowStockAlert {
  product_id: string;
  product_name: string;
  quantity_remaining: number;
  minimum_stock_quantity: number;
  unit: string;
}

export interface HACCPPendingAlert {
  template_id: string;
  template_name: string;
  frequency: string;
  shift_number: number | null;
}

export interface TemperatureAlert {
  log_id: string;
  equipment_id: string;
  equipment_name: string;
  temperature: number;
  min_temp: number | null;
  max_temp: number | null;
  recorded_at: string;
}

export interface DashboardData {
  expiry_alerts: ExpiryAlert[];
  critical_expiry: ExpiryAlert[];
  low_stock: LowStockAlert[];
  haccp_pending: HACCPPendingAlert[];
  temperature_out_of_range: TemperatureAlert[];
  total_active_lots: number;
  stock_value_eur?: number | null;
  stock_value_partial?: boolean;
  lots_without_cost?: number;
}

export interface Equipment {
  id: string;
  name: string;
  equipment_type: string;
  min_temp: number | null;
  max_temp: number | null;
  location: string | null;
  is_active: boolean;
}

export interface TemperatureLog {
  id: string;
  equipment_id: string;
  temperature: number;
  is_out_of_range: boolean;
  notes: string | null;
  recorded_by_user_id: string;
  recorded_at: string;
  created_at: string;
}

export interface HACCPTemplate {
  id: string;
  name: string;
  frequency: string;
  shifts_per_day: number | null;
  is_equipment_dynamic: boolean;
  is_active: boolean;
  is_seed: boolean;
}

export interface HACCPItem {
  id: string;
  template_id: string;
  order_index: number;
  question: string;
  item_type: string;
  equipment_id: string | null;
  options_json: { options: string[] } | null;
  min_selections: number | null;
  is_required: boolean;
  is_active: boolean;
}

export interface EquipmentSnapshot {
  id: string;
  name: string;
  equipment_type: string;
  min_temp: number | null;
  max_temp: number | null;
}

export interface HACCPRun {
  id: string;
  template_id: string;
  status: string;
  run_date: string;
  shift_number: number | null;
  equipment_snapshot_json: EquipmentSnapshot[] | null;
  completed_by_user_id: string | null;
  completed_at: string | null;
  notes: string | null;
  created_by_user_id: string;
}

export interface HACCPAnswer {
  id: string;
  run_id: string;
  item_template_id: string | null;
  equipment_id: string | null;
  answer_bool: boolean | null;
  answer_numeric: number | null;
  answer_text: string | null;
  answer_options: string[] | null;
  is_out_of_range: boolean;
  skip_reason: string | null;
  skip_reason_text: string | null;
  answered_by_user_id: string;
}

export type PurchaseListType = "food" | "beverage" | "non_food" | "mixed";
export type PurchaseListStatus =
  | "draft"
  | "sent"
  | "partially_received"
  | "received";
export type PurchaseListItemStatus =
  | "pending"
  | "received"
  | "partial"
  | "not_received";

export interface PurchaseList {
  id: string;
  type: string;
  status: string;
  notes: string | null;
  created_by_user_id: string;
  sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PurchaseListItem {
  id: string;
  purchase_list_id: string;
  product_id: string;
  supplier_id: string | null;
  quantity_ordered: number;
  quantity_received: number | null;
  unit: string;
  unit_cost_estimate: number | null;
  status: string;
  notes: string | null;
}

export interface PurchaseListWithItems extends PurchaseList {
  items: PurchaseListItem[];
}

export interface ReceiveItemInput {
  quantity_received: number;
  expiry_date?: string | null;
  unit_cost?: number | null;
  notes?: string | null;
}
