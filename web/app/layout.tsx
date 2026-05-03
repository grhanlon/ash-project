import type { Metadata } from "next";
import "./globals.css";
import { penMeta, penVariablesToCssRoot, readPenDoc } from "@/lib/pen-theme";

export const metadata: Metadata = {
  title: "Contagion Read-Through",
  description: "Earnings read-through workbench",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const doc = readPenDoc();
  const penCss = penVariablesToCssRoot(doc);
  const meta = penMeta();

  return (
    <html lang="en">
      <head>
        <style id="pen-variables" dangerouslySetInnerHTML={{ __html: penCss }} />
      </head>
      <body>
        {children}
        {process.env.NODE_ENV === "development" ? (
          <p className="penFootnote" style={{ padding: "0 24px 12px" }}>
            Pencil: {meta.loaded ? `done.pen v${meta.version ?? "?"} (${meta.path})` : `missing ${meta.path}`}
          </p>
        ) : null}
      </body>
    </html>
  );
}
