"use client";

import { FormEvent, useState } from "react";

import type { ManagementVariant } from "@/lib/management/catalog-types";


export function InventoryTable({
  variants,
  onAdjust,
}: {
  variants: ManagementVariant[];
  onAdjust: (id: number, newOnHand: number, reason: string) => Promise<ManagementVariant>;
}) {
  const [rows, setRows] = useState(variants);
  const [selected, setSelected] = useState<ManagementVariant | null>(null);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected) return;
    const form = new FormData(event.currentTarget);
    const adjusted = await onAdjust(
      selected.id,
      Number(form.get("new_on_hand")),
      String(form.get("reason")),
    );
    setRows((current) => current.map((row) => row.id === adjusted.id ? adjusted : row));
    setSelected(null);
  };
  return (
    <>
      <div className="management-table-wrap">
        <table className="management-table">
          <thead><tr><th>SKU</th><th>Variante</th><th>Físico</th><th>Reservado</th><th>Disponible</th><th><span className="sr-only">Acción</span></th></tr></thead>
          <tbody>
            {rows.map((variant) => (
              <tr key={variant.id}>
                <td><strong>{variant.sku}</strong></td>
                <td>{variant.name || "Predeterminada"}</td>
                <td>{variant.on_hand}</td>
                <td>{Math.max(variant.on_hand - variant.available_stock, 0)}</td>
                <td>{variant.available_stock}</td>
                <td><button className="text-button" onClick={() => setSelected(variant)} type="button" aria-label={`Ajustar stock de ${variant.sku}`}>Ajustar</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selected && (
        <div className="management-dialog-layer" role="presentation">
          <form aria-label={`Ajustar stock de ${selected.sku}`} className="management-dialog" onSubmit={(event) => void submit(event)}>
            <div><p className="management-kicker">Inventario</p><h2>{selected.sku}</h2></div>
            <label><span>Stock físico resultante</span><input defaultValue={selected.on_hand} min="0" name="new_on_hand" required type="number" /></label>
            <label><span>Motivo</span><textarea name="reason" required rows={3} /></label>
            <div className="management-form-actions"><button className="button primary" type="submit">Confirmar ajuste</button><button className="button secondary" onClick={() => setSelected(null)} type="button">Cancelar</button></div>
          </form>
        </div>
      )}
    </>
  );
}
