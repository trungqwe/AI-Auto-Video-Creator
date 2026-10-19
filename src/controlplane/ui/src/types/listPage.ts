export interface ListPage<T> {
  items: T[];
  next_cursor: string | null;
}
