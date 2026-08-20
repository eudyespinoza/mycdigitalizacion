import type { Metadata } from "next";
import { Nunito_Sans, Rubik } from "next/font/google";
import { CartProvider } from "@/components/cart/cart-provider";
import "./styles.css";

const rubik = Rubik({ subsets: ["latin"], variable: "--font-display", display: "swap" });
const nunito = Nunito_Sans({ subsets: ["latin"], variable: "--font-body", display: "swap" });

export const metadata: Metadata = {
  title: "mycdigitalizacion",
  description: "Catálogo y compra online para Argentina.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es-AR" className={`${rubik.variable} ${nunito.variable}`} data-scroll-behavior="smooth">
      <body>
        <div
          hidden
          data-direction-contract="db399cd4"
          data-thesis="A broad catalog can feel immediate and trustworthy when search, categories and real products behave like one energetic retail pulse; refuse the centered generic hero and equal-card wall."
          data-world="White and cold-white surfaces, deep navy structure, cyan wayfinding, magenta conversion, rounded logo geometry, crisp product cutouts and soft tinted shadows."
          data-story="Understand breadth, find a category or search, trust delivery/payment signals, inspect a product and advance without uncertainty."
          data-first-viewport="Slim trust rail, practical search-led header, left-aligned oversized promise, right-side product still life, magenta catalog action, compact trust facts and category rail entering the fold."
          data-form="Pulso Comercial, grounded direction 3, seed db399cd4."
          data-finish="unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance"
        />
        <CartProvider>{children}</CartProvider>
      </body>
    </html>
  );
}
