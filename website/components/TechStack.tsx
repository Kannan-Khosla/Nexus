'use client'

import { useCallback, useRef } from 'react'
import { motion } from 'framer-motion'
import { Code, Database, Zap, Globe } from 'lucide-react'
import { staggerContainer, staggerItem, headingReveal } from '@/lib/motion'

const techStack = [
  { category: 'Backend', icon: Code, items: ['FastAPI', 'Python', 'Pydantic', 'JWT Auth'], description: 'Async, type-safe APIs with automatic OpenAPI docs', gradient: 'from-red-500/20 to-orange-500/20', iconColor: 'text-red-400' },
  { category: 'Frontend', icon: Globe, items: ['React', 'Vite', 'Tailwind CSS', 'React Router'], description: 'Modern, fast, and responsive user interface', gradient: 'from-pink-500/20 to-rose-500/20', iconColor: 'text-pink-400' },
  { category: 'Database', icon: Database, items: ['Supabase', 'PostgreSQL', 'Storage', 'RLS'], description: 'Scalable database with built-in auth and storage', gradient: 'from-amber-500/20 to-yellow-500/20', iconColor: 'text-amber-400' },
  { category: 'AI & Services', icon: Zap, items: ['OpenAI GPT-4o-mini', 'Email (SMTP/SendGrid)', 'IMAP Polling', 'Webhooks'], description: 'Intelligent AI integration with multi-channel support', gradient: 'from-rose-500/20 to-red-500/20', iconColor: 'text-rose-400' },
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

export default function TechStack() {
  return (
    <section id="tech" className="py-32 px-6 relative overflow-hidden">
      <div className="mesh-orb-3 absolute bottom-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-[radial-gradient(circle,rgba(220,38,38,0.05)_0%,transparent_70%)] blur-[200px] pointer-events-none" />

      <div className="max-w-7xl mx-auto relative">
        <motion.div variants={headingReveal} initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-100px' }} className="text-center mb-20">
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
            <span className="bg-clip-text text-transparent bg-gradient-to-b from-white to-white/40">Built with</span>
            <span className="block mt-2 bg-clip-text text-transparent bg-[linear-gradient(90deg,#ef4444,#ec4899,#a855f7)] animate-gradient-shine bg-[length:200%_auto]">modern technology</span>
          </h2>
          <p className="text-xl text-zinc-500 max-w-2xl mx-auto">Production-ready stack designed for scale and reliability</p>
        </motion.div>

        <motion.div variants={staggerContainer} initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-50px' }} className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-5xl mx-auto">
          {techStack.map((stack) => {
            const Icon = stack.icon
            return (
              <motion.div key={stack.category} variants={staggerItem}>
                <SpotlightCard className="rounded-2xl p-8 group h-full">
                  <div className={`absolute inset-0 bg-gradient-to-br ${stack.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur-xl`} />
                  <div className="relative z-10">
                    <div className="flex items-center gap-4 mb-4">
                      <div className="w-12 h-12 rounded-xl bg-white/[0.04] flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                        <Icon className={`w-6 h-6 ${stack.iconColor}`} />
                      </div>
                      <h3 className="text-2xl font-bold text-white">{stack.category}</h3>
                    </div>
                    <p className="text-zinc-600 mb-6 text-sm leading-relaxed">{stack.description}</p>
                    <div className="flex flex-wrap gap-2">
                      {stack.items.map((item) => (
                        <span key={item} className="px-3 py-1.5 bg-white/[0.03] rounded-full text-xs border border-white/[0.04] text-zinc-500 hover:bg-white/[0.06] hover:text-white transition-all duration-200 cursor-default">{item}</span>
                      ))}
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
