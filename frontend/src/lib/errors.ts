import axios from 'axios';

interface ValidationDetail { msg?: string; }
interface ApiErrorBody { detail?: string | ValidationDetail[]; message?: string; }

export function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    const detail = error.response?.data?.detail;
    if (Array.isArray(detail)) {
      const messages = detail.map((item) => item.msg).filter(Boolean);
      if (messages.length > 0) return messages.join(', ');
    }
    if (typeof detail === 'string') return detail;
    if (error.response?.data?.message) return error.response.data.message;
    if (error.message && error.message !== 'Network Error') return error.message;
    if (error.message === 'Network Error') return 'The service is unreachable. Check your connection and try again.';
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}
