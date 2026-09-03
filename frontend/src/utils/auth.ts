export interface JwtPayload {
  exp?: number
  iat?: number
  user_id?: string
  username?: string
}

function decodeBase64Url(value: string): string {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = normalized.padEnd(normalized.length + ((4 - normalized.length % 4) % 4), '=')
  return atob(padded)
}

export function parseJwt(token: string | null | undefined): JwtPayload | null {
  if (!token) {
    return null
  }

  try {
    const [, payload] = token.split('.')
    if (!payload) {
      return null
    }
    return JSON.parse(decodeBase64Url(payload)) as JwtPayload
  } catch {
    return null
  }
}

export function getTokenExpiryMs(token: string | null | undefined): number | null {
  const payload = parseJwt(token)
  if (!payload?.exp) {
    return null
  }
  return payload.exp * 1000
}

export function isTokenExpired(token: string | null | undefined, nowMs: number = Date.now()): boolean {
  const expiryMs = getTokenExpiryMs(token)
  if (!expiryMs) {
    return true
  }
  return expiryMs <= nowMs
}
