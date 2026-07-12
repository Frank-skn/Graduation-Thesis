/**
 * Cache đơn giản ở tầng module (sống ngoài vòng đời component).
 * Dùng cho các API ít thay đổi trong 1 phiên làm việc (tổng quan dữ liệu,
 * tham số giải thuật/chi phí...) để tránh gọi lại API mỗi khi rời rồi quay
 * lại trang — React Router unmount component nên state trong component bị
 * mất, nhưng cache ở đây thì không.
 *
 * Cache tự mất khi tải lại trang (F5) — đây là hành vi mong muốn, không
 * cần cơ chế hết hạn phức tạp cho một buổi làm việc.
 */
const cache = new Map();

export function getCached(key) {
  return cache.has(key) ? cache.get(key) : undefined;
}

export function setCached(key, value) {
  cache.set(key, value);
}

export function invalidateCache(key) {
  if (key) {
    cache.delete(key);
  } else {
    cache.clear();
  }
}
