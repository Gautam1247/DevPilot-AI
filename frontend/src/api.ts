import type {Health, Result, Session} from './types';
async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch('/api' + path, { ...init, headers: {...init.headers, ...(token ? {Authorization: `Bearer ${token}`} : {})} });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === 'string' ? error.detail : `Service request failed (${response.status}).`);
  }
  return response.json();
}
export const api = {
  health: () => request<Health>('/health'),
  upload: (file: File) => request<Session>('/projects/upload', {method:'POST', headers:{'Content-Type':'application/zip', 'X-Filename':file.name}, body:file}),
  analyze: (id: string, token: string) => request<Result>(`/projects/${id}/analyze`, {method:'POST'}, token),
  results: (id: string, token: string) => request<Result>(`/projects/${id}/results`, {}, token),
  approve: (id: string, token: string, approve: boolean) => request<Result>(`/projects/${id}/approve`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({approve})}, token),
  download: async (id: string, token: string) => {
    const response = await fetch(`/api/projects/${id}/download`, {headers:{Authorization:`Bearer ${token}`}});
    if (!response.ok) { const error = await response.json().catch(() => null); throw new Error(error?.detail || 'Download failed.'); }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a'); link.href=url; link.download='devpilot-patched.zip'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
};
