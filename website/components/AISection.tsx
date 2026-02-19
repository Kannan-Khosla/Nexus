'use client'

import { useCallback, useRef } from 'react'
import { motion } from 'framer-motion'
import { Bot, Sparkles, Zap } from 'lucide-react'
import { staggerContainer, staggerItem, headingReveal } from '@/lib/motion'

const aiFeatures = [
  { icon: Bot, title: 'Context-Aware Replies', description: 'GPT-4o-mini analyzes full conversation history to generate intelligent, relevant responses that feel human.', gradient: 'from-red-500/20 to-orange-500/20', iconColor: 'text-red-400', glowColor: 'bg-red-500/10' },
  { icon: Sparkles, title: 'Smart Guardrails', description: 'Automatic PII sanitization, rate limiting, and safety checks ensure every AI response is secure and appropriate.', gradient: 'from-pink-500/20 to-rose-500/20', iconColor: 'text-pink-400', glowColor: 'bg-pink-500/10' },
  { icon: Zap, title: 'Instant Responses', description: 'AI replies in seconds with exponential backoff retry logic for maximum reliability and uptime.', gradient: 'from-amber-500/20 to-orange-500/20', iconColor: 'text-amber-400', glowColor: 'bg-amber-500/10' },
]

function SpotlightCard({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    ref.current.style.setProperty('--mouse-x', `${((e.clientX - rect.left) / rect.width) * 100}%`)
    ref.current.style.setProperty('--mouse-y', `${((e.clientY - rect.top) / rect.height) * 100}%`)
  }, [])
  return <div ref={ref} onMouseMove={handleMouseMove} className={`spotlight-card ${className}`}>{children}</div>
}

export default function AISection() {
  return (
    <section id="ai" className="py-32 px-6 relative overflow-hidden">
      {/* Ambient mesh orbs */}
      <div className="mesh-orb-1 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[600px] bg-[radial-gradient(circle,rgba(236,72,153,0.06)_0%,transparent_70%)] blur-[200px] pointer-events-none" />
      <div className="mesh-orb-3 absolute top-0 right-0 w-[400px] h-[400px] bg-[radial-gradient(circle,rgba(220,38,38,0.05)_0%,transparent_70%)] blur-[150px] pointer-events-none" />

      <div className="max-w-7xl mx-auto relative">
        <motion.div variants={headingReveal} initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-100px' }} className="text-center mb-20">
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
            <span className="bg-clip-text text-transparent bg-gradient-to-b from-white to-white/40">AI where it&apos;s</span>
            <span className="block mt-2 bg-clip-text text-transparent bg-[linear-gradient(90deg,#ef4444,#ec4899,#a855f7)] animate-gradient-shine bg-[length:200%_auto]">most useful</span>
          </h2>
          <p className="text-xl text-zinc-500 max-w-2xl mx-auto">Intelligent automation that understands context and delivers exceptional support</p>
        </motion.div>

        <motion.div variants={staggerContainer} initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-50px' }} className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {aiFeatures.map((feature) => {
            const Icon = feature.icon
            return (
              <motion.div key={feature.title} variants={staggerItem}>
                <SpotlightCard className="rounded-2xl p-8 group h-full">
                  <div className={`absolute inset-0 bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur-xl`} />
                  <div className="relative z-10">
                    <div className={`w-14 h-14 rounded-2xl ${feature.glowColor} flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300`}>
                      <Icon className={`w-7 h-7 ${feature.iconColor}`} />
                    </div>
                    <h3 className="text-2xl font-bold mb-3 text-white">{feature.title}</h3>
                    <p className="text-zinc-500 leading-relaxed">{feature.description}</p>
                  </div>
                </SpotlightCard>
              </motion.div>
            )
          })}
        </motion.div>
      </div>
    </section>
  )
}
