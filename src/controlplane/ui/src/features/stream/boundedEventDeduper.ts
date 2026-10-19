// Bộ khử trùng lặp stream_event_id có giới hạn bộ nhớ (CT-API-008, GAP-H-03).
// Thuần logic: không gọi mạng, không chạm DOM. Loại bỏ theo FIFO theo thứ tự chèn
// của Set; id đã thấy lại không được làm mới vị trí.

export const DEFAULT_MAX_SEEN = 5000;

export interface BoundedEventDeduper {
  seenBefore(id: string): boolean;
  clear(): void;
  size(): number;
}

export function createBoundedEventDeduper(maxSeen: number = DEFAULT_MAX_SEEN): BoundedEventDeduper {
  if (!Number.isInteger(maxSeen) || maxSeen < 1) {
    throw new RangeError(`maxSeen phải là số nguyên không nhỏ hơn 1, nhận được ${String(maxSeen)}`);
  }
  const seen = new Set<string>();

  return {
    seenBefore(id: string): boolean {
      if (seen.has(id)) {
        return true;
      }
      seen.add(id);
      if (seen.size > maxSeen) {
        const oldest = seen.keys().next();
        if (!oldest.done) {
          seen.delete(oldest.value);
        }
      }
      return false;
    },
    clear(): void {
      seen.clear();
    },
    size(): number {
      return seen.size;
    },
  };
}
