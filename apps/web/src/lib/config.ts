/**
 * Configuración de cliente. La URL de la API se inyecta vía
 * NEXT_PUBLIC_API_URL (build/runtime). Por defecto el backend local.
 */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * API key opcional para modo single-tenant protegido o multi-tenant.
 * En el self-host abierto por defecto no hace falta.
 */
export const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";
