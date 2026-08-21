"use client";

import { FormEvent, useState } from "react";

import { ApiError } from "@/lib/api";
import type { GeneralSettings } from "@/lib/management/types";
import { THEME_PRESETS, type ThemeColors, type ThemePalette } from "@/lib/theme";


export function GeneralSettingsForm({
  initial,
  onSave,
}: {
  initial: GeneralSettings;
  onSave: (settings: GeneralSettings) => Promise<void>;
}) {
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [themePalette, setThemePalette] = useState<ThemePalette>(initial.theme_palette);
  const [themeColors, setThemeColors] = useState<ThemeColors>({
    theme_structure: initial.theme_structure,
    theme_action: initial.theme_action,
    theme_wayfinding: initial.theme_wayfinding,
    theme_background: initial.theme_background,
    theme_text: initial.theme_text,
  });
  const choosePalette = (palette: ThemePalette) => {
    setThemePalette(palette);
    if (palette !== "custom") setThemeColors(THEME_PRESETS[palette].colors);
  };
  const updateThemeColor = (field: keyof ThemeColors, value: string) => {
    setThemeColors((current) => ({ ...current, [field]: value.toUpperCase() }));
  };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setState("saving");
    setErrorMessage("");
    const form = new FormData(event.currentTarget);
    const payload: GeneralSettings = {
      public_name: String(form.get("public_name") ?? ""),
      announcement: String(form.get("announcement") ?? ""),
      contact_email: String(form.get("contact_email") ?? ""),
      pickup_enabled: form.has("pickup_enabled"),
      pickup_label: String(form.get("pickup_label") ?? ""),
      pickup_address: String(form.get("pickup_address") ?? ""),
      pickup_hours: String(form.get("pickup_hours") ?? ""),
      instagram_url: String(form.get("instagram_url") ?? ""),
      facebook_url: String(form.get("facebook_url") ?? ""),
      tiktok_url: String(form.get("tiktok_url") ?? ""),
      youtube_url: String(form.get("youtube_url") ?? ""),
      linkedin_url: String(form.get("linkedin_url") ?? ""),
      whatsapp_enabled: form.has("whatsapp_enabled"),
      whatsapp_number: String(form.get("whatsapp_number") ?? ""),
      whatsapp_message: String(form.get("whatsapp_message") ?? ""),
      theme_palette: themePalette,
      ...themeColors,
    };
    try {
      await onSave(payload);
      setState("saved");
    } catch (error) {
      const fieldMessage = error instanceof ApiError
        ? Object.values(error.fields).flat()[0] ?? error.message
        : "No pudimos guardar los cambios.";
      setErrorMessage(fieldMessage);
      setState("error");
    }
  };
  return (
    <form className="management-form" onSubmit={(event) => void submit(event)}>
      <section className="management-form-section">
        <h2>Datos de la tienda</h2>
        <div className="management-field-grid">
          <label><span>Nombre público</span><input defaultValue={initial.public_name} name="public_name" /></label>
          <label><span>Email de contacto</span><input defaultValue={initial.contact_email} name="contact_email" type="email" /></label>
          <label className="field-wide"><span>Franja informativa</span><input defaultValue={initial.announcement} name="announcement" /></label>
        </div>
      </section>
      <section className="management-form-section">
        <h2>Retiro</h2>
        <label className="management-check"><input defaultChecked={initial.pickup_enabled} name="pickup_enabled" type="checkbox" /><span>Permitir retiro</span></label>
        <div className="management-field-grid">
          <label><span>Nombre de la opción</span><input defaultValue={initial.pickup_label} name="pickup_label" /></label>
          <label><span>Dirección</span><input defaultValue={initial.pickup_address} name="pickup_address" /></label>
          <label className="field-wide"><span>Horarios</span><input defaultValue={initial.pickup_hours} name="pickup_hours" /></label>
        </div>
      </section>
      <section className="management-form-section theme-settings-section">
        <div className="management-section-heading">
          <div>
            <h2>Paleta de colores</h2>
            <p>La selección se aplica a la tienda y a Administración.</p>
          </div>
          <button className="button secondary theme-reset" onClick={() => choosePalette("pulso")} type="button">Restaurar Pulso Comercial</button>
        </div>
        <label className="theme-palette-select">
          <span>Paleta</span>
          <select value={themePalette} onChange={(event) => choosePalette(event.target.value as ThemePalette)}>
            {Object.entries(THEME_PRESETS).map(([value, preset]) => <option key={value} value={value}>{preset.label}</option>)}
            <option value="custom">Personalizada</option>
          </select>
        </label>
        <div className="theme-swatches" aria-label="Vista previa de la paleta">
          {Object.entries(themeColors).map(([name, color]) => <span key={name} style={{ backgroundColor: color }} title={color} />)}
        </div>
        {themePalette === "custom" && <div className="management-field-grid theme-color-grid">
          <label htmlFor="theme-structure"><span>Color de estructura</span><input aria-label="Color de estructura" id="theme-structure" type="color" value={themeColors.theme_structure} onChange={(event) => updateThemeColor("theme_structure", event.target.value)} /><small>{themeColors.theme_structure}</small></label>
          <label htmlFor="theme-action"><span>Color de acción</span><input aria-label="Color de acción" id="theme-action" type="color" value={themeColors.theme_action} onChange={(event) => updateThemeColor("theme_action", event.target.value)} /><small>{themeColors.theme_action}</small></label>
          <label htmlFor="theme-wayfinding"><span>Color de orientación</span><input aria-label="Color de orientación" id="theme-wayfinding" type="color" value={themeColors.theme_wayfinding} onChange={(event) => updateThemeColor("theme_wayfinding", event.target.value)} /><small>{themeColors.theme_wayfinding}</small></label>
          <label htmlFor="theme-background"><span>Color de fondo</span><input aria-label="Color de fondo" id="theme-background" type="color" value={themeColors.theme_background} onChange={(event) => updateThemeColor("theme_background", event.target.value)} /><small>{themeColors.theme_background}</small></label>
          <label htmlFor="theme-text"><span>Color de texto</span><input aria-label="Color de texto" id="theme-text" type="color" value={themeColors.theme_text} onChange={(event) => updateThemeColor("theme_text", event.target.value)} /><small>{themeColors.theme_text}</small></label>
        </div>}
        <p className="theme-contrast-note">Al guardar verificamos automáticamente que textos y acciones mantengan contraste accesible.</p>
      </section>
      <section className="management-form-section">
        <h2>Redes sociales</h2>
        <p className="management-section-intro">Sólo se mostrarán en el pie de la tienda las redes que tengan una dirección configurada.</p>
        <div className="management-field-grid">
          <label><span>Instagram</span><input defaultValue={initial.instagram_url} name="instagram_url" placeholder="https://instagram.com/..." type="url" /></label>
          <label><span>Facebook</span><input defaultValue={initial.facebook_url} name="facebook_url" placeholder="https://facebook.com/..." type="url" /></label>
          <label><span>TikTok</span><input defaultValue={initial.tiktok_url} name="tiktok_url" placeholder="https://tiktok.com/@..." type="url" /></label>
          <label><span>YouTube</span><input defaultValue={initial.youtube_url} name="youtube_url" placeholder="https://youtube.com/@..." type="url" /></label>
          <label><span>LinkedIn</span><input defaultValue={initial.linkedin_url} name="linkedin_url" placeholder="https://linkedin.com/company/..." type="url" /></label>
        </div>
      </section>
      <section className="management-form-section">
        <h2>WhatsApp</h2>
        <label className="management-check"><input defaultChecked={initial.whatsapp_enabled} name="whatsapp_enabled" type="checkbox" /><span>Mostrar botón de WhatsApp</span></label>
        <div className="management-field-grid">
          <label><span>Número de WhatsApp</span><input defaultValue={initial.whatsapp_number} inputMode="tel" name="whatsapp_number" placeholder="+54 9 11 5555-1234" /></label>
          <label className="field-wide"><span>Mensaje inicial</span><textarea defaultValue={initial.whatsapp_message} maxLength={240} name="whatsapp_message" rows={3} /></label>
        </div>
      </section>
      {state === "saved" && <p className="success-message">Cambios guardados.</p>}
      {state === "error" && <p className="inline-error" role="alert">{errorMessage}</p>}
      <button className="button primary" disabled={state === "saving"} type="submit">
        {state === "saving" ? "Guardando…" : "Guardar cambios"}
      </button>
    </form>
  );
}
