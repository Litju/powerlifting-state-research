"use client";

import { useMemo, useState, type ReactNode } from "react";
import styles from "./ui.module.css";

export interface Column<T> {
  key: string;
  header: string;
  numeric?: boolean;
  value: (row: T) => string | number;
  render?: (row: T) => ReactNode;
}

export function DataTable<T>({
  caption,
  columns,
  rows,
  rowKey,
  defaultSort,
}: {
  caption: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  defaultSort?: { key: string; dir: "asc" | "desc" };
}) {
  const [sort, setSort] = useState(defaultSort ?? null);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return rows;
    const factor = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const x = col.value(a);
      const y = col.value(b);
      if (typeof x === "number" && typeof y === "number") return (x - y) * factor;
      return String(x).localeCompare(String(y)) * factor;
    });
  }, [rows, columns, sort]);

  return (
    <div className={styles.tableWrap} tabIndex={0} role="region" aria-label={`${caption} (scrollable table)`}>
      <table className={styles.table}>
        <caption>
          {caption} <span aria-live="polite">{`(${rows.length} ${rows.length === 1 ? "row" : "rows"})`}</span>
        </caption>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={c.numeric ? styles.num : undefined}
                aria-sort={sort?.key === c.key ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
              >
                <button
                  type="button"
                  className={styles.sortBtn}
                  onClick={() => setSort((s) => (s && s.key === c.key ? { key: c.key, dir: s.dir === "asc" ? "desc" : "asc" } : { key: c.key, dir: "asc" }))}
                >
                  {c.header}
                  {sort?.key === c.key ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((c) => (
                <td key={c.key} className={c.numeric ? styles.num : undefined}>
                  {c.render ? c.render(row) : c.value(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Plain, non-interactive table used as the accessible alternative of a chart. */
export function ChartTable({ caption, head, body }: { caption: string; head: string[]; body: (string | number)[][] }) {
  return (
    <details>
      <summary>Data table: {caption}</summary>
      <div className={styles.tableWrap} tabIndex={0} role="region" aria-label={`${caption} (scrollable table)`}>
        <table className={styles.table}>
          <caption>{caption}</caption>
          <thead>
            <tr>
              {head.map((h, i) => (
                <th key={h} scope="col" className={i > 0 ? styles.num : undefined}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((r, i) => (
              <tr key={i}>
                {r.map((cell, j) => (
                  <td key={j} className={j > 0 ? styles.num : undefined}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
