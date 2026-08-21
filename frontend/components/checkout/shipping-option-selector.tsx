import { formatMoney } from "@/lib/format";
import type { ShippingQuote } from "@/lib/types";


const serviceCopy: Record<string, string> = {
  CP: "Entrega a domicilio",
  andreani_domicilio: "Entrega a domicilio",
  multi_parcel: "Entrega en varios bultos",
  a_convenir: "Coordinación personalizada",
};


export function ShippingOptionSelector({
  options,
  selectedId,
  onSelect,
}: {
  options: ShippingQuote[];
  selectedId: string;
  onSelect: (publicId: string) => void;
}) {
  return (
    <fieldset className="shipping-options">
      <legend>Elegí una opción de envío</legend>
      {options.map((option) => (
        <label className="shipping-option" key={option.public_id}>
          <input
            checked={selectedId === option.public_id}
            name="shipping-option"
            onChange={() => onSelect(option.public_id)}
            type="radio"
            value={option.public_id}
          />
          <span>
            <strong>{option.provider_label}</strong>
            <small>{serviceCopy[option.service] ?? option.service}</small>
            {option.amount_pending && (
              <small>Te avisaremos el costo antes de pagar.</small>
            )}
          </span>
          <strong className="shipping-option-price">
            {option.amount_pending ? "A confirmar" : formatMoney(option.total_amount)}
          </strong>
        </label>
      ))}
    </fieldset>
  );
}
