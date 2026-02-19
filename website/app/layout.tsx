import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Nexus - AI-Powered Support Platform',
  description: 'Transform customer support with AI-powered ticketing, intelligent routing, and seamless multi-channel communication.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} antialiased bg-black text-white min-h-screen`}>
        {children}
      </body>
    </html>
  )
}
