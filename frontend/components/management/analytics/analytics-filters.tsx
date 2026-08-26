"use client";

import { usePathname, useRouter } from "next/navigation";
import type { FormEvent } from "react";

import { buildAnalyticsQuery } from "@/lib/management/analytics-filters";
import type { AnalyticsFilters } from "@/lib/management/analytics-types";

type FilterOption = { id: number; name: string };

export function AnalyticsFilters({
  filters,
  commercial = false,
  categories = [],
  brands = [],
}: {
  filters: AnalyticsFilters;
  commercial?: boolean;
  categories?: FilterOption[];
  brands?: FilterOption[];
}) {
  const pathname = usePathname();
  const router = useRouter();

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    router.replace(`${pathname}?${buildAnalyticsQuery({
      from: String(data.get("from")),
      to: String(data.get("to")),
      compare: data.get("compare") === "on",
      coverageDays: Number(data.get("coverage_days")) as 15 | 30 | 60,
      category: Number(data.get("category")) || null,
      brand: Number(data.get("brand")) || null,
    })}`, { scroll: false });
  }

  return (
    <form className="analytics-filters" onSubmit={apply}>
      <label>Desde<input defaultValue={filters.from} name="from" required type="date" /></label>
      <label>Hasta<input defaultValue={filters.to} name="to" required type="date" /></label>
      {commercial ? (
        <>
          <label>Categoría<select defaultValue={filters.category ?? ""} name="category"><option value="">Todas</option>{categories.map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}</select></label>
          <label>Marca<select defaultValue={filters.brand ?? ""} name="brand"><option value="">Todas</option>{brands.map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}</select></label>
          <label>Cobertura<select defaultValue={filters.coverageDays} name="coverage_days"><option value="15">15 días</option><option value="30">30 días</option><option value="60">60 días</option></select></label>
        </>
      ) : <input name="coverage_days" type="hidden" value={filters.coverageDays} />}
      <label className="analytics-compare"><input defaultChecked={filters.compare} name="compare" type="checkbox" />Comparar período anterior</label>
      <button className="button secondary" type="submit">Actualizar</button>
    </form>
  );
}
