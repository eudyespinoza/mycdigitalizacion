"use client";

import { FormEvent, useState } from "react";


export function BrandingForm({ logoUrl, faviconUrl, onSave }: { logoUrl: string; faviconUrl: string; onSave: (data: FormData) => Promise<void> }) {
  const [state, setState] = useState("idle");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setState("saving");
    try { await onSave(new FormData(event.currentTarget)); setState("saved"); } catch { setState("error"); }
  };
  return <form className="management-form-section branding-form" onSubmit={(event) => void submit(event)}><div><p className="management-kicker">Identidad visual</p><h2>Logo y favicon</h2><p>Reemplazá las imágenes sin tocar código. El tamaño del logo se adapta dentro de la navegación actual.</p></div><div className="branding-preview-grid"><figure><img alt="Logo actual" src={logoUrl} /><figcaption>Logo actual</figcaption></figure><figure><img alt="Favicon actual" src={faviconUrl} /><figcaption>Favicon actual</figcaption></figure></div><div className="management-field-grid"><label><span>Nuevo logo</span><input accept="image/*" name="logo" type="file" /></label><label><span>Nuevo favicon</span><input accept="image/*" name="favicon" type="file" /></label></div><button className="button secondary" disabled={state === "saving"} type="submit">Guardar identidad visual</button>{state === "saved" && <p className="success-message">Identidad visual actualizada.</p>}{state === "error" && <p className="inline-error">No pudimos actualizar las imágenes.</p>}</form>;
}
