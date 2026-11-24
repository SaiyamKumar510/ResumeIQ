// Reusable API service for the ResumeIQ Flask backend.
// Base URL comes from VITE_API_URL; when empty, relative /api URLs are used
// (proxied by Vite in development).

const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '');

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'unknown_error', details = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request(path, { method = 'GET', body, json } = {}) {
  const options = { method, headers: {} };
  if (json !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(json);
  } else if (body !== undefined) {
    options.body = body; // FormData: the browser sets the multipart boundary
  }

  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, options);
  } catch {
    throw new ApiError('Cannot reach the ResumeIQ server. Check that the backend is running.', {
      code: 'network_error',
    });
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    /* non-JSON body */
  }

  if (!response.ok) {
    // Backend error shape: { error: { code, message, details? } }
    const err = data && data.error;
    throw new ApiError(
      (err && err.message) || `The server responded with an error (HTTP ${response.status}).`,
      { status: response.status, code: (err && err.code) || 'http_error', details: (err && err.details) || null },
    );
  }
  return data;
}

export const api = {
  /** Resolves with the health body, or a synthetic status when the server is down/degraded. */
  async healthStatus() {
    try {
      return await request('/api/health');
    } catch (e) {
      if (e.code === 'network_error') return { status: 'offline' };
      return { status: 'degraded', message: e.message };
    }
  },

  analyzeText: ({ resumeText, jobDescription }) =>
    request('/api/analyze', {
      method: 'POST',
      json: { resume_text: resumeText, job_description: jobDescription },
    }),

  analyzePdf: ({ file, jobDescription }) => {
    const form = new FormData();
    form.append('resume_file', file);
    form.append('job_description', jobDescription);
    return request('/api/analyze', { method: 'POST', body: form });
  },

  listAnalyses: ({ limit = 20, offset = 0 } = {}) => request(`/api/analyses?limit=${limit}&offset=${offset}`),

  /** Loads every saved analysis summary (the API pages at 100 per request). */
  async listAllAnalyses() {
    const pageSize = 100;
    let offset = 0;
    let total = 0;
    const all = [];
    do {
      const page = await request(`/api/analyses?limit=${pageSize}&offset=${offset}`);
      total = page.total;
      all.push(...page.analyses);
      offset += pageSize;
      if (page.analyses.length === 0) break;
    } while (offset < total);
    return { total, analyses: all };
  },

  getAnalysis: (id) => request(`/api/analyses/${id}`),
  deleteAnalysis: (id) => request(`/api/analyses/${id}`, { method: 'DELETE' }),
};
