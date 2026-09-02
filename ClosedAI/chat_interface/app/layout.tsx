import type React from "react"
import type { Metadata } from "next"
import { Space_Grotesk, Nunito, Outfit } from "next/font/google"
import "./globals.css"

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-heading",
  display: "swap",
  weight: ["400", "500", "600", "700"],
})

const nunito = Nunito({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
})

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-brand",
  display: "swap",
  weight: ["500", "600", "700"],
})

export const metadata: Metadata = {
  title: "Vera HR",
  description: "Vera HR — your People Ops agent.",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon-16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon.png", sizes: "48x48", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="bg-background">
      <body
        className={`${nunito.variable} ${spaceGrotesk.variable} ${outfit.variable} font-sans antialiased`}
      >
        {children}
      </body>
    </html>
  )
}
