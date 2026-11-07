export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail))
        message = body.detail
          .map((item: { msg: string }) => item.msg)
          .join("; ");
    } catch {
      /* Non-JSON errors still show their HTTP status. */
    }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}
export function post<T>(path: string, body: unknown = {}): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}
export function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Could not complete the request. Please retry.";
}
