"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { managementRequest } from "@/lib/management/api";
import type { ManagementStaffUser } from "@/lib/management/access-types";
import type { ManagementSupportCase, ManagementSupportCaseList, ManagementSupportFilters, ManagementSupportPriority } from "@/lib/management/support-types";
import type { SupportCaseKind, SupportCaseStatus } from "@/lib/support/types";

const kindLabels: Record<SupportCaseKind, string> = { consultation: "Consulta", problem: "Problema" };
const statusLabels: Record<SupportCaseStatus, string> = {
  new: "Recibida", waiting_staff: "En revisión", waiting_customer: "Esperando cliente", resolved: "Resuelta", closed: "Cerrada",
};
const priorityLabels: Record<ManagementSupportPriority, string> = { low: "Baja", normal: "Normal", high: "Alta", urgent: "Urgente" };

export const managementSupportLabels = { kindLabels, statusLabels, priorityLabels };

function displayDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Fecha no disponible" : new Intl.DateTimeFormat("es-AR", { dateStyle: "short", timeStyle: "short" }).format(date).replace(/[\u00a0\u202f]/g, " ");
}

function queryFor(filters: ManagementSupportFilters) {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value) query.set(key, value); });
  return query.toString();
}

function hrefFor(filters: ManagementSupportFilters) {
  const query = queryFor(filters);
  return `/gestion/consultas${query ? `?${query}` : ""}`;
}

function contactLabel(item: ManagementSupportCase) {
  return item.contact_name || item.customer?.name || item.contact_email || "Sin contacto";
}

function FilterSelect<T extends string>({ label, value, onChange, options }: { label: string; value?: T; onChange: (value: T | "") => void; options: readonly [T, string][] }) {
  return <label>{label}<select aria-label={label} onChange={(event) => onChange(event.target.value as T | "")} value={value ?? ""}><option value="">Todas</option>{options.map(([option, name]) => <option key={option} value={option}>{name}</option>)}</select></label>;
}

export function ManagementSupportInbox({ initialData, initialFilters, assignees = [] }: { initialData: ManagementSupportCaseList; initialFilters: ManagementSupportFilters; assignees?: ManagementStaffUser[] }) {
  const [filters, setFilters] = useState(initialFilters);
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => { if (searchTimer.current) clearTimeout(searchTimer.current); }, []);

  async function load(nextFilters: ManagementSupportFilters) {
    const query = queryFor(nextFilters);
    setLoading(true);
    setError("");
    window.history.replaceState(null, "", hrefFor(nextFilters));
    try {
      const result = await managementRequest<ManagementSupportCaseList>(`/support/cases/${query ? `?${query}` : ""}`);
      setData(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos cargar las consultas. Intentá nuevamente.");
    } finally {
      setLoading(false);
    }
  }

  function changeFilter(name: keyof ManagementSupportFilters, value: string, debounce = false) {
    const next = { ...filters, [name]: value || undefined, page: undefined };
    setFilters(next);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (debounce) searchTimer.current = setTimeout(() => { void load(next); }, 300);
    else void load(next);
  }

  function goToPage(link: string | null) {
    if (!link) return;
    const url = new URL(link, window.location.origin);
    const next = Object.fromEntries(url.searchParams.entries()) as ManagementSupportFilters;
    setFilters(next);
    void load(next);
  }

  return <section className="management-list-section" aria-labelledby="management-support-inbox-title">
    <header className="management-section-heading"><div><h1 id="management-support-inbox-title">Consultas</h1><p>Priorizá respuestas y resolvé problemas sin perder el contexto de cada caso.</p></div></header>
    <div className="management-search" role="search">
      <FilterSelect label="Tipo" onChange={(value) => changeFilter("kind", value)} options={Object.entries(kindLabels) as [SupportCaseKind, string][]} value={filters.kind} />
      <FilterSelect label="Estado" onChange={(value) => changeFilter("status", value)} options={Object.entries(statusLabels) as [SupportCaseStatus, string][]} value={filters.status} />
      <FilterSelect label="Prioridad" onChange={(value) => changeFilter("priority", value)} options={Object.entries(priorityLabels) as [ManagementSupportPriority, string][]} value={filters.priority} />
      <label>Asignación<select aria-label="Asignación" onChange={(event) => changeFilter("assignee", event.target.value)} value={filters.assignee ?? ""}><option value="">Todas</option><option value="unassigned">Sin asignar</option>{assignees.filter((user) => user.is_active).map((user) => <option key={user.id} value={user.id}>{[user.first_name, user.last_name].filter(Boolean).join(" ") || user.email}</option>)}</select></label>
      <label><input aria-label="Sólo pendientes" checked={filters.pending === "1"} onChange={(event) => changeFilter("pending", event.target.checked ? "1" : "")} type="checkbox" /> Pendientes</label>
      <label><input aria-label="Sólo sin leer" checked={filters.unread === "1"} onChange={(event) => changeFilter("unread", event.target.checked ? "1" : "")} type="checkbox" /> Sin leer</label>
      <label><span className="sr-only">Buscar consultas</span><input aria-label="Buscar consultas" defaultValue={filters.search} onChange={(event) => changeFilter("search", event.target.value, true)} placeholder="Buscar número, asunto o contacto" type="search" /></label>
    </div>
    {loading ? <p role="status">Cargando consultas...</p> : null}
    {error ? <p className="inline-error" role="alert">{error} <button className="text-button" onClick={() => void load(filters)} type="button">Reintentar</button></p> : null}
    <div className="management-table-wrap">
      <table aria-label="Consultas y problemas" className="management-table">
        <thead><tr><th>Número</th><th>Consulta</th><th>Tipo</th><th>Estado</th><th>Prioridad</th><th>Asignada a</th><th>Actualizada</th><th>Sin leer</th></tr></thead>
        <tbody>{data.results.map((item) => <tr key={item.public_id}>
          <td><Link aria-label={`Abrir ${item.case_number}: ${item.subject}`} href={`/gestion/consultas/${item.public_id}`}>{item.case_number}</Link></td>
          <td><strong>{item.subject}</strong><small>{contactLabel(item)}</small></td><td>{kindLabels[item.kind]}</td><td>{statusLabels[item.status]}</td><td>{priorityLabels[item.priority]}</td><td>{item.assigned_to?.name || "Sin asignar"}</td><td><time dateTime={item.updated_at}>{displayDate(item.updated_at)}</time></td><td>Ver en detalle</td>
        </tr>)}</tbody>
      </table>
    </div>
    {!loading && !error && !data.results.length ? <p className="management-empty">No hay consultas con estos filtros.</p> : null}
    {data.previous || data.next ? <nav aria-label="Paginación de consultas" className="management-content-actions"><button className="button secondary" disabled={!data.previous || loading} onClick={() => goToPage(data.previous)} type="button">Página anterior</button><button className="button secondary" disabled={!data.next || loading} onClick={() => goToPage(data.next)} type="button">Página siguiente</button></nav> : null}
  </section>;
}
