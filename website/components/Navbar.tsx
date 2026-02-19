'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Github, Menu, X } from 'lucide-react'
import { springTransition } from '@/lib/motion'

const navLinks = [
  { name: 'Features', href: '#features' },
  { name: 'AI', href: '#ai' },
  { name: 'Demo', href: '#demo' },
  { name: 'Automation', href: '#automation' },
  { name: 'Tech Stack', href: '#tech' },
  { name: 'Pricing', href: '#pricing' },
]

export default function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false)

  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex justify-center pt-6 px-4">
      <motion.nav
        initial={{ y: -50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={springTransition}
        className="flex items-center gap-6 px-3 py-2 bg-white/[0.04] backdrop-blur-xl rounded-full border border-white/[0.06] shadow-[0_8px_32px_rgba(0,0,0,0.6)]"
      >
        {/* Logo */}
        <a href="/" className="flex items-center gap-2.5 px-2">
          <div className="relative w-7 h-7">
            <div className="absolute inset-0 rounded-lg bg-gradient-to-br from-red-500 to-pink-600 blur-sm opacity-50" />
            <div className="relative w-7 h-7 rounded-lg bg-gradient-to-br from-red-500 to-pink-600 flex items-center justify-center">
              <span className="text-white font-bold text-xs">N</span>
            </div>
          </div>
          <span className="font-semibold text-sm hidden sm:block text-white">Nexus</span>
        </a>

        {/* Desktop Nav Links */}
        <div className="hidden lg:flex items-center gap-1">
          {navLinks.map((link) => (
            <a
              key={link.name}
              href={link.href}
              className="text-[13px] font-medium text-zinc-500 hover:text-white transition-colors duration-200 px-3 py-1.5 rounded-full hover:bg-white/[0.04]"
            >
              {link.name}
            </a>
          ))}
        </div>

        {/* Right Side */}
        <div className="flex items-center gap-3 pl-2">
          <a
            href="https://github.com/Kannan-Khosla/Nexus"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 bg-white text-black px-4 py-1.5 rounded-full text-sm font-medium hover:bg-zinc-200 transition-all duration-200 active:scale-[0.98] hover:shadow-[0_0_20px_rgba(255,255,255,0.12)]"
          >
            <Github className="w-4 h-4" />
            <span className="hidden sm:inline">GitHub</span>
          </a>
          <button
            className="lg:hidden text-white p-1"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            {isMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </motion.nav>

      {/* Mobile Menu */}
      <AnimatePresence>
        {isMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            transition={{ ...springTransition, stiffness: 400 }}
            className="absolute top-20 left-4 right-4 bg-black/90 backdrop-blur-xl rounded-2xl border border-white/[0.06] p-6 lg:hidden shadow-2xl"
          >
            <div className="space-y-1">
              {navLinks.map((link, i) => (
                <motion.a
                  key={link.name}
                  href={link.href}
                  onClick={() => setIsMenuOpen(false)}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05, ...springTransition }}
                  className="block text-sm text-zinc-500 hover:text-white transition-colors px-4 py-3 rounded-xl hover:bg-white/[0.04]"
                >
                  {link.name}
                </motion.a>
              ))}
              <div className="pt-4 border-t border-white/[0.06] mt-4">
                <a
                  href="https://github.com/Kannan-Khosla/Nexus"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block px-4 py-3 bg-white text-black rounded-xl text-sm font-medium text-center hover:bg-zinc-200 transition-colors active:scale-[0.98]"
                >
                  View on GitHub
                </a>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  )
}
