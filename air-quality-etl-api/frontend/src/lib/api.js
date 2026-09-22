export async function requestJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `请求失败：${response.status}`);
  }
  return response.json();
}

export function toApiDate(value) {
  return `${value}T00:00:00`;
}

export function buildDashboardQuery(startDate, endDate, county = "", extra = {}) {
  const params = new URLSearchParams({
    start: toApiDate(startDate),
    end: toApiDate(endDate),
    ...extra,
  });
  if (county) params.set("county", county);
  return params.toString();
}
