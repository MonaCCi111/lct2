import { ApiError } from '../../client/http';
import { v2ApiConfig } from './config';

function toV2HttpError(payload: unknown, status: number) {
  const body = payload && typeof payload === 'object' ? payload : null;
  const message =
    body && 'message' in body && typeof body.message === 'string'
      ? body.message
      : `Ошибка API v2 (${status})`;
  const code = body && 'code' in body && typeof body.code === 'string' ? body.code : 'HTTP_ERROR';
  const details = body && 'details' in body ? body.details : null;
  return new ApiError(message, status, code, details);
}

export async function v2ApiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${v2ApiConfig.baseUrl}${path}`, {
      signal,
      headers: { Accept: 'application/json' },
    });
  } catch (error: unknown) {
    if (signal?.aborted) throw error;
    throw new ApiError('Не удалось подключиться к API v2. Проверьте соединение.', 0, 'NETWORK_ERROR');
  }
  if (!response.ok) {
    throw toV2HttpError(await response.json().catch(() => null), response.status);
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError('API v2 вернул некорректный JSON.', response.status, 'INVALID_RESPONSE');
  }
}

export async function v2ApiSend<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${v2ApiConfig.baseUrl}${path}`, {
      method: 'POST',
      signal,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (error: unknown) {
    if (signal?.aborted) throw error;
    throw new ApiError('Не удалось подключиться к API v2. Проверьте соединение.', 0, 'NETWORK_ERROR');
  }
  if (!response.ok) {
    throw toV2HttpError(await response.json().catch(() => null), response.status);
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError('API v2 вернул некорректный JSON.', response.status, 'INVALID_RESPONSE');
  }
}
