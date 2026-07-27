import { useMemo, useState } from "react";

export type SortDirection = "asc" | "desc";

export interface SortColumn<T> {
  key: string;
  accessor: (item: T) => string | number | null | undefined;
}

/**
 * Client-side sort-on-click for a data table. Columns are described by an
 * accessor (not just a field name) so a column can sort on a derived display
 * value (e.g. a computed "item" label) rather than only a raw property.
 */
export function useSortableTable<T>(data: T[] | null | undefined, columns: SortColumn<T>[]) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [direction, setDirection] = useState<SortDirection>("asc");

  const sorted = useMemo(() => {
    if (!data) return data;
    const column = columns.find((c) => c.key === sortKey);
    if (!column) return data;
    const copy = [...data];
    copy.sort((a, b) => {
      const av = column.accessor(a);
      const bv = column.accessor(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "number" && typeof bv === "number") return av - bv;
      return String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: "base" });
    });
    if (direction === "desc") copy.reverse();
    return copy;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, sortKey, direction]);

  function toggleSort(key: string) {
    if (sortKey === key) {
      setDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setDirection("asc");
    }
  }

  function indicator(key: string): string {
    if (sortKey !== key) return "";
    return direction === "asc" ? " ▲" : " ▼";
  }

  return { sorted, sortKey, direction, toggleSort, indicator };
}
