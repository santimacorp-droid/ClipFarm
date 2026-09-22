/**
 * APIutility function
 * unified handlingAPI URLand request
 */

import { apiConfigManager, getApiBaseUrl, buildApiUrl } from './apiConfig'

// dynamic fetchAPIbaseURL
export const getApiBaseUrlAsync = async () => {
  // wait API configuration ready
  await apiConfigManager.waitForReady(5000);
  return getApiBaseUrl();
}

// build completeAPI URL
export const buildApiUrlAsync = async (path: string) => {
  // wait API configuration ready
  await apiConfigManager.waitForReady(5000);
  return buildApiUrl(path);
}

// uniformfetchfunction
export const apiFetch = async (path: string, options?: RequestInit) => {
  const url = await buildApiUrlAsync(path);
  return fetch(url, options);
}

// uniformGETrequest
export const apiGet = async (path: string) => {
  return apiFetch(path, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })
}

// uniformPOSTrequest
export const apiPost = async (path: string, data?: any) => {
  return apiFetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: data ? JSON.stringify(data) : undefined,
  })
}

// uniformPUTrequest
export const apiPut = async (path: string, data?: any) => {
  return apiFetch(path, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: data ? JSON.stringify(data) : undefined,
  })
}

// uniformDELETErequest
export const apiDelete = async (path: string) => {
  return apiFetch(path, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
  })
}
