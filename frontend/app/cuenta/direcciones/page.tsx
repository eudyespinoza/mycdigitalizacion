import { AddressManager } from "@/components/account/address-manager";

export default function AddressesPage() {
  return <>
    <div className="catalog-title address-page-title">
      <h1>Direcciones de entrega</h1>
      <p>Administrá tus domicilios y confirmá el punto exacto cuando haga falta.</p>
    </div>
    <AddressManager />
  </>;
}
