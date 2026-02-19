'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { springTransition, headingReveal, staggerContainer, staggerItem } from '@/lib/motion'

const keyboardFeatures = [
  { key: 'F', label: 'Fast', description: 'AI replies in milliseconds' },
  { key: 'S', label: 'Smart', description: 'Context-aware responses' },
  { key: 'R', label: 'Reliable', description: '99.9% uptime guarantee' },
  { key: 'E', label: 'Efficient', description: 'Automated workflows' },
]

const keyboardLayout = [
  ['esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12'],
  ['`', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=', 'del'],
  ['tab', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '[', ']', '\\'],
  ['caps', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ';', "'", 'enter'],
  ['shift', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '.', '/', 'shift'],
  ['ctrl', 'opt', 'cmd', 'space', 'cmd', 'opt', 'ctrl'],
]

const specialWidths: Record<string, string> = { tab: 'min-w-[70px]', caps: 'min-w-[90px]', shift: 'min-w-[90px]', enter: 'min-w-[100px]', space: 'min-w-[200px]', del: 'min-w-[80px]', esc: 'min-w-[60px]' }

export default function InteractiveKeyboard() {
  const [hoveredKey, setHoveredKey] = useState<string | null>(null)
  const [activeFeature, setActiveFeature] = useState<typeof keyboardFeatures[0] | null>(null)

  const handleKeyHover = (key: string) => {
    setHoveredKey(key)
    setActiveFeature(keyboardFeatures.find(f => f.key.toLowerCase() === key.toLowerCase()) || null)
  }

  return (
    <section className="py-32 px-6 relative overflow-hidden">
      <div className="mesh-orb-3 absolute bottom-0 left-1/2 -translate-x-1/2 w-[500px] h-[300px] bg-[radial-gradient(circle,rgba(220,38,38,0.04)_0%,transparent_70%)] blur-[150px] pointer-events-none" />

      <div className="max-w-7xl mx-auto relative">
        <motion.div variants={headingReveal} initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-100px' }} className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-b from-white to-white/40">It&apos;s not about saving time.</h2>
          <p className="text-xl text-zinc-500 max-w-2xl mx-auto mb-12">It&apos;s about feeling like you&apos;re never wasting it.</p>
        </motion.div>

        <div className="flex flex-col lg:flex-row items-center justify-center gap-16">
          <motion.div initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={springTransition} className="relative w-full lg:w-auto">
            <div className="bg-white/[0.02] rounded-2xl p-4 md:p-8 border border-white/[0.05] shadow-[0_8px_40px_rgba(0,0,0,0.5)] overflow-x-auto">
              <div className="inline-block min-w-[600px]">
                {keyboardLayout.map((row, rowIndex) => (
                  <div key={rowIndex} className="flex gap-1 mb-1 justify-center">
                    {row.map((key, keyIndex) => {
                      const isFeature = keyboardFeatures.some(f => f.key.toLowerCase() === key.toLowerCase())
                      const isHovered = hoveredKey === key
                      return (
                        <motion.button key={`${rowIndex}-${keyIndex}`} onMouseEnter={() => handleKeyHover(key)} onMouseLeave={() => { setHoveredKey(null); setActiveFeature(null) }}
                          className={`${specialWidths[key.toLowerCase()] || 'min-w-[44px]'} h-11 bg-white/[0.03] border rounded-lg text-white text-xs font-semibold flex items-center justify-center transition-all duration-200 cursor-pointer ${isFeature ? 'bg-gradient-to-br from-red-600/15 to-pink-600/15 border-red-500/20' : 'border-white/[0.05]'} ${isHovered ? 'bg-gradient-to-br from-red-600/30 to-pink-600/30 border-red-500/40 shadow-lg shadow-red-500/15 scale-110 z-10' : 'hover:bg-white/[0.06] hover:border-white/[0.1]'}`}
                          whileTap={{ scale: 0.95 }}
                        >{key.toUpperCase()}</motion.button>
                      )
                    })}
                  </div>
                ))}
              </div>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ ...springTransition, delay: 0.15 }} className="flex-1 max-w-md w-full">
            <AnimatePresence mode="wait">
              {activeFeature ? (
                <motion.div key={activeFeature.key} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={springTransition} className="rounded-2xl p-8 bg-white/[0.02] border border-white/[0.05]">
                  <div className="text-6xl font-bold mb-4 bg-clip-text text-transparent bg-[linear-gradient(90deg,#ef4444,#ec4899,#a855f7)]">{activeFeature.label}</div>
                  <p className="text-xl text-zinc-500">{activeFeature.description}</p>
                </motion.div>
              ) : (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="rounded-2xl p-8 bg-white/[0.02] border border-white/[0.05]">
                  <p className="text-zinc-600 text-center">Hover over highlighted keys to discover features</p>
                </motion.div>
              )}
            </AnimatePresence>

            <motion.div variants={staggerContainer} initial="hidden" whileInView="visible" viewport={{ once: true }} className="mt-8 space-y-4">
              {keyboardFeatures.map((feature) => (
                <motion.div key={feature.key} variants={staggerItem} className="flex items-center gap-4 group cursor-pointer">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-red-600/15 to-pink-600/15 border border-red-500/15 flex items-center justify-center text-white font-bold group-hover:scale-110 group-hover:border-red-500/30 transition-all duration-300">{feature.key}</div>
                  <div><div className="font-semibold text-white">{feature.label}</div><div className="text-sm text-zinc-600">{feature.description}</div></div>
                </motion.div>
              ))}
            </motion.div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
