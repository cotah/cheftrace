import { api } from "./client";
import type {
  Category,
  DashboardData,
  Equipment,
  HACCPAnswer,
  HACCPItem,
  HACCPRun,
  HACCPTemplate,
  IngredientUnit,
  Invoice,
  InvoiceConfirmDecision,
  InvoiceUploadResponse,
  InvoiceWithItems,
  Product,
  PurchaseList,
  PurchaseListItem,
  PurchaseListWithItems,
  ReceiveItemInput,
  Recipe,
  RecipeIngredient,
  RecipeProduction,
  RecipeProductionPreviewResponse,
  RecipeWithIngredients,
  StockLot,
  StockMovement,
  Supplier,
  TemperatureLog,
} from "./types";

export const categoriesApi = {
  list: (rid: string, token: string) =>
    api.get<Category[]>(`/restaurants/${rid}/categories`, token),
  create: (rid: string, data: { name: string }, token: string) =>
    api.post<Category>(`/restaurants/${rid}/categories`, data, token),
};

export const suppliersApi = {
  list: (rid: string, token: string) =>
    api.get<Supplier[]>(`/restaurants/${rid}/suppliers`, token),
  create: (rid: string, data: Partial<Supplier>, token: string) =>
    api.post<Supplier>(`/restaurants/${rid}/suppliers`, data, token),
  update: (rid: string, id: string, data: Partial<Supplier>, token: string) =>
    api.put<Supplier>(`/restaurants/${rid}/suppliers/${id}`, data, token),
};

export const productsApi = {
  list: (rid: string, token: string) =>
    api.get<Product[]>(`/restaurants/${rid}/products`, token),
  create: (rid: string, data: Partial<Product>, token: string) =>
    api.post<Product>(`/restaurants/${rid}/products`, data, token),
  update: (rid: string, id: string, data: Partial<Product>, token: string) =>
    api.put<Product>(`/restaurants/${rid}/products/${id}`, data, token),
};

export const stockLotsApi = {
  list: (rid: string, token: string) =>
    api.get<StockLot[]>(`/restaurants/${rid}/stock-lots`, token),
  receive: (rid: string, data: Record<string, unknown>, token: string) =>
    api.post<StockLot>(`/restaurants/${rid}/stock-lots`, data, token),
  updateExpiry: (
    rid: string,
    lotId: string,
    data: { expiry_date: string; reason: string },
    token: string,
  ) => api.put<StockLot>(`/restaurants/${rid}/stock-lots/${lotId}/expiry`, data, token),
  discard: (rid: string, lotId: string, token: string) =>
    api.post<StockLot>(`/restaurants/${rid}/stock-lots/${lotId}/discard`, {}, token),
};

export const stockMovementsApi = {
  list: (rid: string, token: string) =>
    api.get<StockMovement[]>(`/restaurants/${rid}/stock/movements`, token),
};

export const dashboardApi = {
  get: (rid: string, token: string) =>
    api.get<DashboardData>(`/restaurants/${rid}/dashboard`, token),
};

export const equipmentApi = {
  list: (rid: string, token: string) =>
    api.get<Equipment[]>(`/restaurants/${rid}/equipment`, token),
  create: (rid: string, data: Partial<Equipment>, token: string) =>
    api.post<Equipment>(`/restaurants/${rid}/equipment`, data, token),
  update: (rid: string, id: string, data: Partial<Equipment>, token: string) =>
    api.put<Equipment>(`/restaurants/${rid}/equipment/${id}`, data, token),
  logTemperature: (
    rid: string,
    data: {
      equipment_id: string;
      temperature: number;
      notes?: string;
      recorded_at?: string;
    },
    token: string,
  ) => api.post<TemperatureLog>(`/restaurants/${rid}/temperature-logs`, data, token),
  listTemperatureLogs: (rid: string, equipment_id: string, token: string) =>
    api.get<TemperatureLog[]>(
      `/restaurants/${rid}/temperature-logs?equipment_id=${equipment_id}`,
      token,
    ),
};

export const haccpApi = {
  listTemplates: (rid: string, token: string) =>
    api.get<HACCPTemplate[]>(`/restaurants/${rid}/haccp/templates`, token),

  listRuns: (
    rid: string,
    filters: {
      run_date?: string;
      date_from?: string;
      date_to?: string;
      status?: string;
      template_id?: string;
    },
    token: string,
  ) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
      if (v) qs.set(k, v);
    }
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return api.get<HACCPRun[]>(`/restaurants/${rid}/haccp/runs${suffix}`, token);
  },

  startRun: (
    rid: string,
    data: { template_id: string; run_date: string; shift_number?: number },
    token: string,
  ) => api.post<HACCPRun>(`/restaurants/${rid}/haccp/runs`, data, token),

  getRun: (rid: string, runId: string, token: string) =>
    api.get<HACCPRun>(`/restaurants/${rid}/haccp/runs/${runId}`, token),

  listItems: (rid: string, templateId: string, token: string) =>
    api.get<HACCPItem[]>(`/restaurants/${rid}/haccp/templates/${templateId}/items`, token),

  listAnswers: (rid: string, runId: string, token: string) =>
    api.get<HACCPAnswer[]>(`/restaurants/${rid}/haccp/runs/${runId}/answers`, token),

  submitAnswer: (rid: string, runId: string, data: Partial<HACCPAnswer>, token: string) =>
    api.post<HACCPAnswer>(`/restaurants/${rid}/haccp/runs/${runId}/answers`, data, token),

  completeRun: (rid: string, runId: string, token: string) =>
    api.put<HACCPRun>(`/restaurants/${rid}/haccp/runs/${runId}/complete`, {}, token),

  reseedTemplates: (rid: string, token: string) =>
    api.post<{ created: string[]; skipped: string[] }>(
      `/restaurants/${rid}/haccp/seed-templates`,
      {},
      token,
    ),
};

export const purchaseListsApi = {
  list: (rid: string, token: string, status?: string) =>
    api.get<PurchaseList[]>(
      `/restaurants/${rid}/purchase-lists${status ? `?status=${status}` : ""}`,
      token,
    ),
  create: (
    rid: string,
    data: { type: string; notes?: string | null },
    token: string,
  ) => api.post<PurchaseList>(`/restaurants/${rid}/purchase-lists`, data, token),
  get: (rid: string, listId: string, token: string) =>
    api.get<PurchaseListWithItems>(
      `/restaurants/${rid}/purchase-lists/${listId}`,
      token,
    ),
  update: (
    rid: string,
    listId: string,
    data: { type?: string; notes?: string | null },
    token: string,
  ) =>
    api.put<PurchaseList>(
      `/restaurants/${rid}/purchase-lists/${listId}`,
      data,
      token,
    ),
  addItem: (
    rid: string,
    listId: string,
    data: {
      product_id: string;
      supplier_id?: string | null;
      quantity_ordered: number;
      unit: string;
      unit_cost_estimate?: number | null;
      notes?: string | null;
    },
    token: string,
  ) =>
    api.post<PurchaseListItem>(
      `/restaurants/${rid}/purchase-lists/${listId}/items`,
      data,
      token,
    ),
  updateItem: (
    rid: string,
    listId: string,
    itemId: string,
    data: Partial<{
      quantity_ordered: number;
      unit_cost_estimate: number | null;
      supplier_id: string | null;
      notes: string | null;
    }>,
    token: string,
  ) =>
    api.put<PurchaseListItem>(
      `/restaurants/${rid}/purchase-lists/${listId}/items/${itemId}`,
      data,
      token,
    ),
  deleteItem: (rid: string, listId: string, itemId: string, token: string) =>
    api.delete<void>(
      `/restaurants/${rid}/purchase-lists/${listId}/items/${itemId}`,
      token,
    ),
  send: (rid: string, listId: string, token: string) =>
    api.post<PurchaseList>(
      `/restaurants/${rid}/purchase-lists/${listId}/send`,
      {},
      token,
    ),
  receiveItem: (
    rid: string,
    listId: string,
    itemId: string,
    data: ReceiveItemInput,
    token: string,
  ) =>
    api.post<PurchaseListItem>(
      `/restaurants/${rid}/purchase-lists/${listId}/items/${itemId}/receive`,
      data,
      token,
    ),
};

export const invoicesApi = {
  list: (rid: string, status: string | undefined, token: string) => {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return api.get<Invoice[]>(`/restaurants/${rid}/invoices${qs}`, token);
  },
  get: (rid: string, id: string, token: string) =>
    api.get<InvoiceWithItems>(`/restaurants/${rid}/invoices/${id}`, token),
  requestUploadUrl: (
    rid: string,
    data: { filename: string; mime_type: string },
    token: string,
  ) =>
    api.post<InvoiceUploadResponse>(
      `/restaurants/${rid}/invoices/upload-url`,
      data,
      token,
    ),
  process: (rid: string, id: string, token: string) =>
    api.post<InvoiceWithItems>(`/restaurants/${rid}/invoices/${id}/process`, {}, token),
  confirm: (
    rid: string,
    id: string,
    body: { items: InvoiceConfirmDecision[] },
    token: string,
  ) =>
    api.post<InvoiceWithItems>(
      `/restaurants/${rid}/invoices/${id}/confirm`,
      body,
      token,
    ),
  delete: (rid: string, id: string, token: string) =>
    api.delete<void>(`/restaurants/${rid}/invoices/${id}`, token),
};

export const recipesApi = {
  list: (rid: string, token: string, isActive?: boolean) => {
    const qs = isActive !== undefined ? `?is_active=${isActive}` : "";
    return api.get<Recipe[]>(`/restaurants/${rid}/recipes${qs}`, token);
  },
  create: (
    rid: string,
    data: {
      name: string;
      yield_quantity: number;
      yield_unit: string;
      prep_time_minutes?: number | null;
      cook_time_minutes?: number | null;
      instructions?: string | null;
    },
    token: string,
  ) => api.post<Recipe>(`/restaurants/${rid}/recipes`, data, token),
  get: (rid: string, id: string, token: string) =>
    api.get<RecipeWithIngredients>(`/restaurants/${rid}/recipes/${id}`, token),
  update: (
    rid: string,
    id: string,
    data: Partial<{
      name: string;
      yield_quantity: number;
      yield_unit: string;
      prep_time_minutes: number | null;
      cook_time_minutes: number | null;
      instructions: string | null;
      is_active: boolean;
    }>,
    token: string,
  ) => api.put<Recipe>(`/restaurants/${rid}/recipes/${id}`, data, token),
  delete: (rid: string, id: string, token: string) =>
    api.delete<void>(`/restaurants/${rid}/recipes/${id}`, token),
  addIngredient: (
    rid: string,
    recipeId: string,
    data: {
      product_id: string;
      quantity: number;
      unit: IngredientUnit;
      notes?: string | null;
    },
    token: string,
  ) =>
    api.post<RecipeIngredient>(
      `/restaurants/${rid}/recipes/${recipeId}/ingredients`,
      data,
      token,
    ),
  updateIngredient: (
    rid: string,
    recipeId: string,
    ingredientId: string,
    data: Partial<{
      quantity: number;
      unit: IngredientUnit;
      notes: string | null;
    }>,
    token: string,
  ) =>
    api.put<RecipeIngredient>(
      `/restaurants/${rid}/recipes/${recipeId}/ingredients/${ingredientId}`,
      data,
      token,
    ),
  removeIngredient: (
    rid: string,
    recipeId: string,
    ingredientId: string,
    token: string,
  ) =>
    api.delete<void>(
      `/restaurants/${rid}/recipes/${recipeId}/ingredients/${ingredientId}`,
      token,
    ),
  producePreview: (
    rid: string,
    recipeId: string,
    batches: number,
    token: string,
  ) =>
    api.post<RecipeProductionPreviewResponse>(
      `/restaurants/${rid}/recipes/${recipeId}/produce/preview`,
      { batches },
      token,
    ),
  produceConfirm: (
    rid: string,
    recipeId: string,
    data: { batches: number; notes?: string | null },
    token: string,
  ) =>
    api.post<RecipeProduction>(
      `/restaurants/${rid}/recipes/${recipeId}/produce/confirm`,
      data,
      token,
    ),
};
