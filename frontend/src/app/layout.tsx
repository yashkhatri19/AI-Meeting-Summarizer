// @ts-ignore
import "./globals.css";

export const metadata = {
  title: 'VoxBrief AI',
  description: 'Production Ready Identity Verification',
}

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