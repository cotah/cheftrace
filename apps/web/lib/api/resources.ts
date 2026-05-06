import { api } from "./client";
import type { Category, Product, Supplier, StockLot, StockMovement } from "./types";

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
