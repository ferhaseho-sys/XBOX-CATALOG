/**
 * Modo administrador.
 *
 * El token se guarda a mano en el navegador, una sola vez:
 *   localStorage.setItem('atlas_admin_token', '<token>')
 *
 * OJO: esto solo decide qué se DIBUJA. No es seguridad — cualquiera puede
 * escribir una clave en su propio localStorage. Lo que realmente protege la
 * ingesta es el header X-Admin-Token que valida la API (401/503).
 * Acá simplemente evitamos mostrarle al público un panel que no puede usar.
 */
const ADMIN_TOKEN_KEY = 'atlas_admin_token';

export function adminToken(): string {
  try {
    return localStorage.getItem(ADMIN_TOKEN_KEY) || '';
  } catch {
    return ''; // localStorage puede tirar en modo privado o con cookies bloqueadas
  }
}

export function isAdmin(): boolean {
  return adminToken().length > 0;
}
