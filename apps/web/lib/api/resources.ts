import { api } from "./client";
import type {
  Category,
  DashboardData,
  Equipment,
  HACCPAnswer,
  HACCPItem,
  HACCPRun,
  HACCPTemplate,
  Product,
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

  listRuns: (rid: string, date: string, token: string) =>
    api.get<HACCPRun[]>(`/restaurants/${rid}/haccp/runs?run_date=${date}`, token),

  startRun: (
    rid: string,
    data: { template_id: string; run_date: string; shift_number?: number },
    token: string,
  ) => api.post<HACCPRun>(`/restaurants/${rid}/haccp/runs`, data, token),

  getRun: (rid: string, _runId: string, token: string) =>
    api.get<HACCPRun>(`/restaurants/${rid}/haccp/runs?run_date=`, token),

  listItems: (rid: string, templateId: string, token: string) =>
    api.get<HACCPItem[]>(`/restaurants/${rid}/haccp/templates/${templateId}/items`, token),

  listAnswers: (rid: string, runId: string, token: string) =>
    api.get<HACCPAnswer[]>(`/restaurants/${rid}/haccp/runs/${runId}/answers`, token),

  submitAnswer: (rid: string, runId: string, data: Partial<HACCPAnswer>, token: string) =>
    api.post<HACCPAnswer>(`/restaurants/${rid}/haccp/runs/${runId}/answers`, data, token),

  completeRun: (rid: string, runId: string, token: string) =>
    api.put<HACCPRun>(`/restaurants/${rid}/haccp/runs/${runId}/complete`, {}, token),
};
