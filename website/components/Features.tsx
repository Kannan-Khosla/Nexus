'use client'

import React, { useState, useCallback, useRef } from 'react'
import { motion } from 'framer-motion'
import {
  Bot, Mail, Shield, Zap, Users, FileText, Route, Clock,
  MessageSquare, Settings, BarChart3, Tag,
} from 'lucide-react'
import { staggerContainer, staggerItem, headingReveal } from '@/lib/motion'

const features = [
  { icon: Bot, title: 'AI-Powered Replies', description: 'GPT-4o-mini generates intelligent, context-aware responses with rate limiting and PII sanitization.', category: 'AI', gradient: 'from-red-500/20 to-orange-500/20' },
  { icon: Mail, title: 'Multi-Channel Support', description: 'Email integration (SMTP/SendGrid), IMAP polling, webhooks, and web UI—all in one platform.', category: 'Integration', gradient: 'from-pink-500/20 to-rose-500/20' },
  { icon: Shield, title: 'Role-Based Access', description: 'JWT authentication with RBAC. Customers see their tickets; admins manage everything.', category: 'Security', gradient: 'from-amber-500/20 to-yellow-500/20' },
  { icon: Zap, title: 'Intelligent Routing', description: 'Automatic ticket routing based on rules, keywords, tags, and priority levels.', category: 'Automation', gradient: 'from-rose-500/20 to-red-500/20' },
  { icon: Users, title: 'Team Collaboration', description: 'Assign tickets, track SLAs, manage escalations, and collaborate seamlessly.', category: 'Collaboration', gradient: 'from-fuchsia-500/20 to-pink-500/20' },
  { icon: FileText, title: 'Rich Documentation', description: 'File attachments, ticket threads, tags, categories, and comprehensive admin tools.', category: 'Management', gradient: 'from-orange-500/20 to-amber-500/20' },
  { icon: Route, title: 'Smart Routing Rules', description: 'Create custom routing rules based on keywords, tags, priority, and context.', category: 'Automation', gradient: 'from-red-500/20 to-pink-500/20' },
  { icon: Clock, title: 'SLA Management', description: 'Track response times, resolution times, and SLA violations with priority-based policies.', category: 'Analytics', gradient: 'from-amber-500/20 to-red-500/20' },
  { icon: MessageSquare, title: 'Real-Time Threading', description: 'Full conversation history with AI, customer, and admin messages in one thread.', category: 'Communication', gradient: 'from-pink-500/20 to-fuchsia-500/20' },
  { icon: Settings, title: 'Admin Dashboard', description: 'Comprehensive admin panel with filtering, search, analytics, and team management.', category: 'Management', gradient: 'from-rose-500/20 to-pink-500/20' },
  { icon: BarChart3, title: 'Analytics & Insights', description: 'Track ticket volumes, response times, AI usage, and team performance metrics.', category: 'Analytics', gradient: 'from-orange-500/20 to-rose-500/20' },
  { icon: Tag, title: 'Tags & Categories', description: 'Organize tickets with custom tags and categories for better tracking and reporting.', category: 'Organization', gradient: 'from-red-500/20 to-amber-500/20' },
]

const categories = ['All', 'AI', 'Automation', 'Integration', 'Security', 'Analytics', 'Management']

function SpotlightCard({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    ref.current.style.setProperty('--mouse-x', `${((e.clientX - rect.left) / rect.width) * 100}%`)
    ref.current.style.setProperty('--mouse-y', `${((e.clientY - rect.top) / rect.height) * 100}%`)
  }, [])

  return (
    <div ref={ref} onMouseMove={handleMouseMove} className={`spotlight-card ${className}`}>
      {children}
    </div>
  )
}

export default function Features() {
  const [selectedCategory, setSelectedCategory] = useState('All')

  return (
    <section id="features" className="py-32 px-6 relative">
      {/* Background mesh orb */}
      <div className="mesh-orb-2 absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-[radial-gradient(circle,rgba(220,38,38,0.06)_0%,transparent_70%)] blur-[150px] pointer-events-none" />

      <div className="max-w-7xl mx-auto relative">
        <motion.div
          variants={headingReveal}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-100px' }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
            <span className="bg-clip-text text-transparent bg-gradient-to-b from-white to-white/40">
              Everything you need for
            </span>
            <span className="block mt-2 bg-clip-text text-transparent bg-[linear-gradient(90deg,#ef4444,#ec4899,#a855f7)] animate-gradient-shine bg-[length:200%_auto]">
              modern support
            </span>
          </h2>
          <p className="text-xl text-zinc-500 max-w-2xl mx-auto mb-10">
            Powerful features that work together seamlessly
          </p>

          <div className="flex flex-wrap justify-center gap-2 mb-12">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-all duration-300 active:scale-[0.98] ${selectedCategory === cat
                    ? 'bg-white text-black shadow-[0_0_20px_rgba(255,255,255,0.1)]'
                    : 'bg-white/[0.03] text-zinc-500 border border-white/[0.06] hover:bg-white/[0.06] hover:text-white'
                  }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </motion.div>

        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"
        >
          {features
            .filter((f) => selectedCategory === 'All' || f.category === selectedCategory)
            .map((feature) => {
              const Icon = feature.icon
              return (
                <motion.div key={feature.title} variants={staggerItem}>
                  <SpotlightCard className="rounded-2xl p-7 cursor-pointer group h-full">
                    <div className={`absolute inset-0 bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur-xl`} />
                    <div className="relative z-10">
                      <div className="mb-5 inline-flex p-3 rounded-xl bg-white/[0.05] text-white group-hover:scale-110 group-hover:bg-white/[0.08] transition-all duration-300">
                        <Icon size={22} />
                      </div>
                      <h3 className="text-lg font-semibold mb-2 text-white">{feature.title}</h3>
                      <p className="text-zinc-600 text-sm leading-relaxed">{feature.description}</p>
                      <div className="mt-4">
                        <span className="text-xs px-2.5 py-1 bg-white/[0.03] rounded-full text-zinc-600 border border-white/[0.04]">{feature.category}</span>
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
