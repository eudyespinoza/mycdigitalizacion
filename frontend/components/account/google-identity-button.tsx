"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef } from "react";

type CredentialResponse = { credential?: string };
type GoogleIdentityApi = {
  accounts: {
    id: {
      initialize: (options: {
        client_id: string;
        callback: (response: CredentialResponse) => void;
        ux_mode: "popup";
        use_fedcm_for_prompt: boolean;
      }) => void;
      renderButton: (
        container: HTMLElement,
        options: Record<string, string | number>,
      ) => void;
    };
  };
};

function getGoogleIdentityApi() {
  return (window as unknown as { google?: GoogleIdentityApi }).google;
}

export function GoogleIdentityButton({
  clientId,
  mode,
  onCredential,
}: {
  clientId: string;
  mode: "login" | "register";
  onCredential: (credential: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const callbackRef = useRef(onCredential);
  useEffect(() => { callbackRef.current = onCredential; }, [onCredential]);

  const renderButton = useCallback(() => {
    const google = getGoogleIdentityApi();
    const container = containerRef.current;
    if (!google || !container) return;
    container.replaceChildren();
    google.accounts.id.initialize({
      client_id: clientId,
      callback: (response) => {
        if (response.credential) callbackRef.current(response.credential);
      },
      ux_mode: "popup",
      use_fedcm_for_prompt: true,
    });
    google.accounts.id.renderButton(container, {
      type: "standard",
      theme: "outline",
      size: "large",
      shape: "pill",
      text: mode === "login" ? "signin_with" : "signup_with",
      logo_alignment: "left",
      locale: "es-419",
      width: 320,
    });
  }, [clientId, mode]);

  useEffect(() => { renderButton(); }, [renderButton]);

  return (
    <div className="google-auth-control">
      <Script
        id="google-identity-services"
        src="https://accounts.google.com/gsi/client?hl=es-419"
        strategy="afterInteractive"
        onReady={renderButton}
      />
      <div ref={containerRef} className="google-auth-button" />
    </div>
  );
}
