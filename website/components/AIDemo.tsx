'use client'

import { useState, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bot, Send, Sparkles, Zap } from 'lucide-react'
import { springTransition, headingReveal } from '@/lib/motion'

const demoQueries = [
  { query: 'How do I reset my password?', response: 'To reset your password, click on "Forgot Password" on the login page. You\'ll receive an email with a reset link that expires in 1 hour. If you don\'t see it, check your spam folder.', category: 'Support' },
  { query: 'What are your business hours?', response: 'Our support team is available Monday-Friday, 9 AM - 6 PM EST. For urgent issues, we offer 24/7 emergency support for premium customers.', category: 'General' },
  { query: 'I need help with billing', response: 'I can help you with billing questions. Would you like to view your current invoice, update your payment method, or request a refund? Please provide your account email for faster assistance.', category: 'Billing' },
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

export default function AIDemo() {
  const [selectedQuery, setSelectedQuery] = useState(0)
  const [isTyping, setIsTyping] = useState(false)

  const handleQueryClick = (index: number) => {
    setIsTyping(true)
    setTimeout(() => { setSelectedQuery(index); setIsTyping(false) }, 500)
  }

  const currentDemo = demoQueries[selectedQuery]

  return (
    <section id="demo" className="py-32 px-6 relative overflow-hidden">
      <div className="mesh-orb-1 absolute top-1/2 left-0 w-[500px] h-[500px] bg-[radial-gradient(circle,rgba(220,38,38,0.04)_0%,transparent_70%)] blur-[200px] pointer-events-none" />
      <div className="mesh-orb-3 absolute bottom-0 right-0 w-[400px] h-[400px] bg-[radial-gradient(circle,rgba(236,72,153,0.04)_0%,transparent_70%)] blur-[150px] pointer-events-none" />

      <div className="max-w-7xl mx-auto relative">
        <motion.div variants={headingReveal} initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-100px' }} className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-b from-white to-white/40">Your support just got smarter</h2>
          <p className="text-xl text-zinc-500 max-w-2xl mx-auto">AI where it&apos;s most useful — in your support workflow</p>
        </motion.div>

        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <motion.div initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={springTransition}>
            <SpotlightCard className="rounded-2xl p-8 shadow-[0_8px_40px_rgba(0,0,0,0.6)]">
              <div className="relative z-10">
                <div className="flex items-center gap-3 mb-6 pb-4 border-b border-white/[0.04]">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-red-600 to-pink-600 flex items-center justify-center shadow-lg shadow-red-500/15">
                    <Bot className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <div className="font-semibold text-white text-sm">Nexus AI Assistant</div>
                    <div className="text-xs text-zinc-600">Online • GPT-4o-mini</div>
                  </div>
                  <div className="ml-auto flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500 shadow-sm shadow-green-500/50" />
                    <div className="text-xs text-zinc-600">Active</div>
                  </div>
                </div>

                <div className="relative mb-6">
                  <input type="text" value={currentDemo.query} readOnly className="w-full px-4 py-3 bg-white/[0.03] border border-white/[0.05] rounded-xl text-white placeholder-zinc-700 focus:outline-none text-sm" placeholder="Ask anything..." />
                  <Send className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-700" />
                </div>

                <AnimatePresence mode="wait">
                  {isTyping ? (
                    <motion.div key="typing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex gap-2 p-4">
                      <div className="flex gap-1.5">
                        <div className="w-2 h-2 bg-red-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-2 h-2 bg-red-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-2 h-2 bg-red-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </motion.div>
                  ) : (
                    <motion.div key={selectedQuery} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={springTransition} className="bg-gradient-to-br from-red-500/[0.06] to-pink-500/[0.06] rounded-xl p-4 border border-red-500/[0.08]">
                      <div className="flex items-start gap-3">
                        <Sparkles className="w-4 h-4 text-red-400 mt-1 flex-shrink-0" />
                        <div>
                          <p className="text-zinc-400 leading-relaxed text-sm">{currentDemo.response}</p>
                          <div className="mt-3 flex items-center gap-2">
                            <span className="text-xs px-2.5 py-1 bg-white/[0.03] rounded-full text-zinc-600 border border-white/[0.04]">{currentDemo.category}</span>
                            <span className="text-xs text-zinc-700">• Generated in 0.8s</span>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </SpotlightCard>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ ...springTransition, delay: 0.15 }} className="space-y-4">
            {demoQueries.map((demo, index) => (
              <motion.button key={index} onClick={() => handleQueryClick(index)} whileTap={{ scale: 0.98 }} className={`w-full text-left rounded-2xl p-6 border transition-all duration-300 ${selectedQuery === index ? 'border-red-500/20 bg-red-500/[0.04] shadow-[0_0_30px_rgba(220,38,38,0.06)]' : 'border-white/[0.05] bg-white/[0.02] hover:bg-white/[0.03] hover:border-white/[0.08]'}`}>
                <div className="flex items-start gap-4">
                  <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-300 ${selectedQuery === index ? 'bg-gradient-to-br from-red-600 to-pink-600 shadow-lg shadow-red-500/15' : 'bg-white/[0.03]'}`}>
                    <Zap className={`w-5 h-5 ${selectedQuery === index ? 'text-white' : 'text-zinc-600'}`} />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold mb-1 text-white text-sm">{demo.category}</h3>
                    <p className="text-sm text-zinc-600">{demo.query}</p>
                  </div>
                </div>
              </motion.button>
            ))}

            <div className="rounded-2xl p-6 bg-white/[0.02] border border-white/[0.05]">
              <h3 className="font-semibold mb-3 text-white text-sm">Key Features</h3>
              <ul className="space-y-2.5 text-sm text-zinc-600">
                {['Context-aware responses', 'PII sanitization & safety', 'Sub-second response times', 'Automatic ticket creation'].map((item, i) => (
                  <li key={i} className="flex items-center gap-2.5"><div className="w-1.5 h-1.5 rounded-full bg-red-500 shadow-sm shadow-red-500/50" />{item}</li>
                ))}
              </ul>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
