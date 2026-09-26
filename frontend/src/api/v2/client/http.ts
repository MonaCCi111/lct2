import { ApiError } from '../../client/http';
import { v2ApiConfig } from './config';

/** Read-only transport for the dispatcher API. It deliberately has no send/mutation method. */
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
    const body: unknown = await response.json().catch(() => null);
    const message =
      body && typeof body === 'object' && 'message' in body && typeof body.message === 'string'
        ? body.message
        : `Ошибка API v2 (${response.status})`;
    throw new ApiError(message, response.status, 'HTTP_ERROR');
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError('API v2 вернул некорректный JSON.', response.status, 'INVALID_RESPONSE');
  }
}
