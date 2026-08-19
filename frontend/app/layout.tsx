import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "mycdigitalizacion",
  description: "Catálogo y compra online para Argentina.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es-AR">
      <body>{children}</body>
    </html>
  );
}
