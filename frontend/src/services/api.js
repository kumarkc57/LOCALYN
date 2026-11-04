const API_BASE_URL = 'http://localhost:8000';

/**
 * Fetch all reports from the backend without invalid query parameters.
 */
export async function getReports(category = null, search = null) {
  const url = new URL(`${API_BASE_URL}/reports`);
  if (category && category !== 'ALL') {
    url.searchParams.set('category', category);
  }
  if (search && search.trim()) {
    url.searchParams.set('search', search.trim());
  }

  const res = await fetch(url.toString());
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: Failed to load reports`);
  }
  return await res.json();
}

/**
 * Fetch single report by ID along with its full CHEF confidence breakdown factors.
 */
export async function getReportById(reportId) {
  if (!reportId) throw new Error('Report ID is required');
  const res = await fetch(`${API_BASE_URL}/reports/${encodeURIComponent(reportId)}`);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: Failed to load report '${reportId}'`);
  }
  return await res.json();
}

export { API_BASE_URL };
