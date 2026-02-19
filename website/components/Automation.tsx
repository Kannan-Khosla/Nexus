'use client'

import { useCallback, useRef } from 'react'
import { motion } from 'framer-motion'
import { Route, Mail, Clock, Tag } from 'lucide-react'
import { staggerContainer, staggerItem, headingReveal } from '@/lib/motion'

const automations = [
  { icon: Route, title: 'Smart Routing', description: 'Automatically route tickets based on keywords, tags, priority, and context.', example: 'Tickets with "billing" → Finance team', gradient: 'from-red-500/20 to-orange-500/20', iconColor: 'text-red-400' },
  { icon: Mail, title: 'Email Automation', description: 'IMAP polling and webhooks automatically create tickets from emails. Send replies via SMTP or SendGrid.', example: 'Inbound email → New ticket → AI reply', gradient: 'from-pink-500/20 to-rose-500/20', iconColor: 'text-pink-400' },
  { icon: Clock, title: 'SLA Tracking', description: 'Automatic SLA violation detection based on priority. Track response and resolution times.', example: 'Urgent ticket → 1hr response SLA → Alert', gradient: 'from-amber-500/20 to-orange-500/20', iconColor: 'text-amber-400' },
  { icon: Tag, title: 'Auto-Tagging', description: 'Automatically tag tickets based on content, routing rules, and patterns.', example: 'Keyword "refund" → Auto-tag "billing"', gradient: 'from-rose-500/20 to-red-500/20', iconColor: 'text-rose-400' },
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

export default function Automation() {
  return (
    <section id="automation" className="py-32 px-6 relative overflow-hidden">
      <div className="mesh-orb-2 absolute top-0 right-0 w-[500px] h-[400px] bg-[radial-gradient(circle,rgba(236,72,153,0.05)_0%,transparent_70%)] blur-[200px] pointer-events-none" />

      <div className="max-w-7xl mx-auto relative">
        <motion.div variants={headingReveal} initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-100px' }} className="text-center mb-20">
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-b from-white to-white/40">
            Don&apos;t repeat yourself
          </h2>
          <p className="text-xl text-zinc-500 max-w-2xl mx-auto">Automate the things you do all the time</p>
        </motion.div>

        <motion.div variants={staggerContainer} initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-50px' }} className="grid md:grid-cols-2 gap-6 max-w-5xl mx-auto">
          {automations.map((auto) => {
            const Icon = auto.icon
            return (
              <motion.div key={auto.title} variants={staggerItem}>
                <SpotlightCard className="rounded-2xl p-8 group h-full">
                  <div className={`absolute inset-0 bg-gradient-to-br ${auto.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur-xl`} />
                  <div className="relative z-10 flex items-start gap-4">
                    <div className="w-12 h-12 rounded-xl bg-white/[0.04] flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform duration-300">
                      <Icon className={`w-6 h-6 ${auto.iconColor}`} />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-xl font-bold mb-2 text-white">{auto.title}</h3>
                      <p className="text-zinc-600 text-sm mb-4 leading-relaxed">{auto.description}</p>
                      <div className="px-3 py-2 bg-white/[0.02] rounded-lg text-xs text-zinc-500 font-mono border border-white/[0.04]">{auto.example}</div>
                    </div>
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
