import React from "react";
// @ts-ignore
import "./globals.css";

export const metadata = {
  title: 'VoxBrief AI',
  description: 'Production Ready Identity Verification',
}
// Root layout for the entire application
export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 antialiased">
        {children}
      </body>
    </html>
  )
}