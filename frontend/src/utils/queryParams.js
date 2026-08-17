const DEFAULT_PAGE = 1;
const DEFAULT_PAGE_SIZE = 20;
const MIN_PAGE_SIZE = 1;
const MAX_PAGE_SIZE = 500;

export function buildQueryString({ page = DEFAULT_PAGE, page_size = DEFAULT_PAGE_SIZE, ...filters } = {}) {
  const clampedPage = Math.max(1, page);
  const clampedPageSize = Math.min(MAX_PAGE_SIZE, Math.max(MIN_PAGE_SIZE, page_size));

  const params = new URLSearchParams({
    page: String(clampedPage),
    page_size: String(clampedPageSize),
  });

  // Any other truthy/defined filter (item_id, include_depleted, stock_lot_id, and
  // whatever a later domain's list endpoint needs) rides along unchanged — omit
  // null/undefined/empty-string so an unset filter never becomes a literal
  // "?item_id=undefined" in the URL.
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value));
    }
  });

  return `?${params.toString()}`;
}
