"use client";

import { WarningCircle } from "@phosphor-icons/react";
import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

type ConfirmationDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  busyLabel: string;
  busy?: boolean;
  error?: string;
  onCancel: () => void;
  onConfirm: () => void | Promise<void>;
};

export function ConfirmationDialog({
  open,
  title,
  description,
  confirmLabel,
  busyLabel,
  busy = false,
  error,
  onCancel,
  onConfirm,
}: ConfirmationDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const layerRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const cancelHandler = useRef(onCancel);
  const busyState = useRef(busy);
  cancelHandler.current = onCancel;
  busyState.current = busy;

  useEffect(() => {
    if (!open) return;
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    const siblings = [...document.body.children]
      .filter((element) => element !== layerRef.current)
      .map((element) => ({
        element,
        inert: element.hasAttribute("inert"),
        ariaHidden: element.getAttribute("aria-hidden"),
      }));

    document.body.style.overflow = "hidden";
    siblings.forEach(({ element }) => {
      element.setAttribute("inert", "");
      element.setAttribute("aria-hidden", "true");
    });
    const focusFrame = requestAnimationFrame(() => cancelRef.current?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busyState.current) {
        event.preventDefault();
        cancelHandler.current();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const controls = [...dialogRef.current.querySelectorAll<HTMLElement>("button:not(:disabled), [href], input:not(:disabled)")];
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);

    return () => {
      cancelAnimationFrame(focusFrame);
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      siblings.forEach(({ element, inert, ariaHidden }) => {
        if (!inert) element.removeAttribute("inert");
        if (ariaHidden === null) element.removeAttribute("aria-hidden");
        else element.setAttribute("aria-hidden", ariaHidden);
      });
      requestAnimationFrame(() => returnFocus?.focus());
    };
  }, [open]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      className="confirmation-layer"
      ref={layerRef}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onCancel();
      }}
    >
      <div
        aria-busy={busy}
        aria-describedby={descriptionId}
        aria-labelledby={titleId}
        aria-modal="true"
        className="confirmation-dialog"
        ref={dialogRef}
        role="dialog"
      >
        <span className="confirmation-symbol" aria-hidden="true"><WarningCircle size={26} weight="bold" /></span>
        <h2 id={titleId}>{title}</h2>
        <p id={descriptionId}>{description}</p>
        {error && <p className="inline-error" role="alert">{error}</p>}
        <div className="confirmation-actions">
          <button className="button secondary" disabled={busy} ref={cancelRef} type="button" onClick={onCancel}>Cancelar</button>
          <button className="button destructive" disabled={busy} type="button" onClick={() => void onConfirm()}>{busy ? busyLabel : confirmLabel}</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
