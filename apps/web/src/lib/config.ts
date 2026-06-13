/**
 * Configuración de cliente.
 *
 * El navegador siempre habla con el proxy BFF del propio Next (mismo origen);
 * el proxy reenvía al FastAPI por la red interna añadiendo la API key en el
 * servidor. Por eso la API key nunca está en el bundle del navegador.
 */
export const API_BASE = "/api/mf";
