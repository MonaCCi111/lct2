import { apiConfig } from './config';

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export const isNotFound = (error: unknown) => error instanceof ApiError && error.status === 404;

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiConfig.baseUrl}${path}`, {
      signal,
      headers: { Accept: 'application/json' },
    });
  } catch (error: unknown) {
    if (signal?.aborted) throw error;
    throw new ApiError('Не удалось подключиться к API. Проверьте соединение.', 0, 'NETWORK_ERROR');
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const message =
      body && typeof body === 'object' && 'message' in body && typeof body.message === 'string'
        ? body.message
        : `Ошибка API (${response.status})`;
    throw new ApiError(message, response.status, 'HTTP_ERROR');
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError('API вернул некорректный JSON.', response.status, 'INVALID_RESPONSE');
  }
}

/** Write requests share the client so error shape, cancellation and messages stay identical. */
export async function apiSend<T>(
  method: 'POST' | 'PATCH',
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiConfig.baseUrl}${path}`, {
      method,
      signal,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (error: unknown) {
    if (signal?.aborted) throw error;
    throw new ApiError('Не удалось подключиться к API. Проверьте соединение.', 0, 'NETWORK_ERROR');
  }
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const message =
      payload && typeof payload === 'object' && 'message' in payload && typeof payload.message === 'string'
        ? payload.message
        : `Ошибка API (${response.status})`;
    throw new ApiError(message, response.status, 'HTTP_ERROR');
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError('API вернул некорректный JSON.', response.status, 'INVALID_RESPONSE');
  }
}
