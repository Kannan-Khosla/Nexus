'use client'

import { useState, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronLeft, ChevronRight, Bot, Mail, Shield, Zap, Users, Route } from 'lucide-react'
import { springTransition, staggerContainer, staggerItem, headingReveal } from '@/lib/motion'

const extensions = [
  { icon: Bot, title: 'AI-Powered Replies', description: 'GPT-4o-mini generates intelligent, context-aware responses instantly.', gradient: 'from-red-500/20 to-orange-500/20', iconGradient: 'from-red-500 to-orange-500' },
  { icon: Mail, title: 'Email Integration', description: 'Connect SMTP, SendGrid, or AWS SES. Automatic ticket creation from emails.', gradient: 'from-pink-500/20 to-rose-500/20', iconGradient: 'from-pink-500 to-rose-500' },
  { icon: Shield, title: 'Role-Based Access', description: 'JWT authentication with RBAC. Secure access control for teams.', gradient: 'from-amber-500/20 to-yellow-500/20', iconGradient: 'from-amber-500 to-yellow-500' },
  { icon: Zap, title: 'Smart Routing', description: 'Automatically route tickets based on keywords, tags, and priority.', gradient: 'from-rose-500/20 to-red-500/20', iconGradient: 'from-rose-500 to-red-500' },
  { icon: Users, title: 'Team Collaboration', description: 'Assign tickets, track SLAs, and collaborate seamlessly with your team.', gradient: 'from-fuchsia-500/20 to-pink-500/20', iconGradient: 'from-fuchsia-500 to-pink-500' },
  { icon: Route, title: 'Workflow Automation', description: 'Create custom workflows and automate repetitive support tasks.', gradient: 'from-orange-500/20 to-amber-500/20', iconGradient: 'from-orange-500 to-amber-500' },
]

const categories = ['All', 'AI', 'Integration', 'Automation', 'Security']

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

export default function FeatureCarousel() {
  const [selectedCategory, setSelectedCategory] = useState('All')
  const [currentIndex, setCurrentIndex] = useState(0)
  const carouselRef = useRef<HTMLDivElement>(null)
  const filteredExtensions = extensions.filter((ext) => selectedCategory === 'All' || ext.title.includes(selectedCategory))
  const visibleExtensions = filteredExtensions.slice(currentIndex, currentIndex + 4)
  const next = () => { if (currentIndex < filteredExtensions.length - 4) setCurrentIndex(currentIndex + 1) }
  const prev = () => { if (currentIndex > 0) setCurrentIndex(currentIndex - 1) }

  return (
    <section className="py-32 px-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-red-500/[0.01] to-transparent pointer-events-none" />

      <div className="max-w-7xl mx-auto relative">
        <motion.div variants={headingReveal} initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-100px' }} className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-b from-white to-white/40">There&apos;s an extension for that.</h2>
          <p className="text-xl text-zinc-500 max-w-2xl mx-auto mb-10">Use your favorite tools without even opening them.</p>

          <div className="flex flex-wrap justify-center gap-2 mb-12">
            {categories.map((cat) => (
              <button key={cat} onClick={() => { setSelectedCategory(cat); setCurrentIndex(0) }} className={`px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 active:scale-[0.98] ${selectedCategory === cat ? 'bg-white text-black shadow-[0_0_20px_rgba(255,255,255,0.1)]' : 'bg-white/[0.03] text-zinc-500 border border-white/[0.05] hover:bg-white/[0.06] hover:text-white'}`}>{cat}</button>
            ))}
          </div>
        </motion.div>

        <div className="relative" ref={carouselRef}>
          <motion.div variants={staggerContainer} initial="hidden" whileInView="visible" viewport={{ once: true }} className="flex gap-5 overflow-hidden">
            <AnimatePresence mode="wait">
              {visibleExtensions.map((ext) => {
                const Icon = ext.icon
                return (
                  <motion.div key={`${ext.title}-${currentIndex}`} variants={staggerItem} className="flex-shrink-0 w-full md:w-1/2 lg:w-1/4">
                    <SpotlightCard className="rounded-2xl p-8 group h-full">
                      <div className={`absolute inset-0 bg-gradient-to-br ${ext.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur-xl`} />
                      <div className="relative z-10">
                        <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${ext.iconGradient} flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300 shadow-lg`}>
                          <Icon className="w-7 h-7 text-white" />
                        </div>
                        <h3 className="text-xl font-bold mb-3 text-white">{ext.title}</h3>
                        <p className="text-zinc-600 text-sm leading-relaxed">{ext.description}</p>
                      </div>
                    </SpotlightCard>
                  </motion.div>
                )
              })}
            </AnimatePresence>
          </motion.div>

          {filteredExtensions.length > 4 && (
            <>
              <button onClick={prev} disabled={currentIndex === 0} className={`absolute left-0 top-1/2 -translate-y-1/2 -translate-x-4 w-12 h-12 rounded-full bg-white/[0.03] backdrop-blur-md border border-white/[0.06] flex items-center justify-center transition-all active:scale-[0.98] ${currentIndex === 0 ? 'opacity-30 cursor-not-allowed' : 'hover:bg-white/[0.06] hover:border-white/[0.1]'}`}><ChevronLeft className="w-5 h-5 text-white" /></button>
              <button onClick={next} disabled={currentIndex >= filteredExtensions.length - 4} className={`absolute right-0 top-1/2 -translate-y-1/2 translate-x-4 w-12 h-12 rounded-full bg-white/[0.03] backdrop-blur-md border border-white/[0.06] flex items-center justify-center transition-all active:scale-[0.98] ${currentIndex >= filteredExtensions.length - 4 ? 'opacity-30 cursor-not-allowed' : 'hover:bg-white/[0.06] hover:border-white/[0.1]'}`}><ChevronRight className="w-5 h-5 text-white" /></button>
            </>
          )}
        </div>

        <div className="flex justify-center gap-2 mt-8">
          {Array.from({ length: Math.max(1, filteredExtensions.length - 3) }).map((_, index) => (
            <button key={index} onClick={() => setCurrentIndex(index)} className={`h-1.5 rounded-full transition-all duration-300 ${currentIndex === index ? 'bg-white w-8' : 'bg-white/15 w-1.5 hover:bg-white/30'}`} />
          ))}
        </div>

        <div className="text-center mt-8">
          <a href="https://github.com/Kannan-Khosla/Nexus" className="text-zinc-600 hover:text-white transition-colors inline-flex items-center gap-2 text-sm">Plus many more features...<ChevronRight className="w-4 h-4" /></a>
        </div>
      </div>
    </section>
  )
}
