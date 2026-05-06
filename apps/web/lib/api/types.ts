export interface Restaurant {
  id: string;
  name: string;
  city: string | null;
  country: string;
  timezone: string;
  currency: string;
  expiry_warning_days: number;
  critical_expiry_days: number;
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
