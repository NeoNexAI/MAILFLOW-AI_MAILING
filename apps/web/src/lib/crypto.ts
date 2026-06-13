/**
 * Cifrado simétrico (AES-256-GCM) para guardar la API key de la organización
 * en el `metadata` de la org de Better Auth. La clave en claro nunca se persiste.
 *
 * Formato del token: base64( iv(12) || authTag(16) || ciphertext ). La clave se
 * deriva con SHA-256 de WEB_SECRET_KEY (acepta cualquier longitud → 32 bytes).
 *
 * Solo se usa en el servidor (route handlers / hooks de Better Auth).
 */
import {
  createCipheriv,
  createDecipheriv,
  createHash,
  randomBytes,
} from "node:crypto";

const IV_BYTES = 12;
const TAG_BYTES = 16;

function key(): Buffer {
  const raw = process.env.WEB_SECRET_KEY;
  if (!raw) {
    throw new Error("WEB_SECRET_KEY no configurado");
  }
  return createHash("sha256").update(raw).digest();
}

export function encryptSecret(plaintext: string): string {
  const iv = randomBytes(IV_BYTES);
  const cipher = createCipheriv("aes-256-gcm", key(), iv);
  const ciphertext = Buffer.concat([
    cipher.update(plaintext, "utf8"),
    cipher.final(),
  ]);
  const tag = cipher.getAuthTag();
  return Buffer.concat([iv, tag, ciphertext]).toString("base64");
}

export function decryptSecret(token: string): string {
  const buf = Buffer.from(token, "base64");
  const iv = buf.subarray(0, IV_BYTES);
  const tag = buf.subarray(IV_BYTES, IV_BYTES + TAG_BYTES);
  const ciphertext = buf.subarray(IV_BYTES + TAG_BYTES);
  const decipher = createDecipheriv("aes-256-gcm", key(), iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([
    decipher.update(ciphertext),
    decipher.final(),
  ]).toString("utf8");
}
