'use client'

import { motion } from 'framer-motion'
import { Quote } from 'lucide-react'
import { staggerContainer, staggerItem, headingReveal } from '@/lib/motion'

const testimonials = [
  { quote: "Nexus transformed how we handle customer support. The AI integration reduced our response time by 80%, and the admin tools make managing tickets effortless.", author: "Support Team", role: "Production Deployment", avatar: "ST", gradient: 'from-red-500 to-orange-500' },
  { quote: "The intelligent routing and SLA management features are game-changers. We can now handle 10x more tickets with the same team size.", author: "Engineering Lead", role: "SaaS Company", avatar: "EL", gradient: 'from-pink-500 to-rose-500' },
  { quote: "The multi-channel support means we never miss a customer inquiry. The AI replies are surprisingly good and save us hours daily.", author: "Customer Success", role: "E-commerce Platform", avatar: "CS", gradient: 'from-rose-500 to-red-500' },
]

export default function Testimonials() {
  return (
    <section className="py-32 px-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-pink-500/[0.01] to-transparent pointer-events-none" />

      <div className="max-w-7xl mx-auto relative">
        <motion.div variants={headingReveal} initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-100px' }} className="text-center mb-20">
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
            <span className="bg-clip-text text-transparent bg-gradient-to-b from-white to-white/40">Built for teams</span>
            <span className="block mt-2 bg-clip-text text-transparent bg-[linear-gradient(90deg,#ef4444,#ec4899,#a855f7)] animate-gradient-shine bg-[length:200%_auto]">who care about quality</span>
          </h2>
          <p className="text-xl text-zinc-500 max-w-2xl mx-auto">Used by teams who value speed, reliability, and exceptional customer experience</p>
        </motion.div>

        <motion.div variants={staggerContainer} initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-50px' }} className="grid md:grid-cols-3 gap-6 max-w-6xl mx-auto">
          {testimonials.map((testimonial, index) => (
            <motion.div key={index} variants={staggerItem} className="group relative p-8 rounded-2xl bg-white/[0.02] border border-white/[0.05] hover:border-white/[0.08] transition-all duration-500">
              <Quote className="w-8 h-8 text-white/[0.04] mb-4" />
              <p className="text-zinc-500 mb-8 leading-relaxed text-sm">&ldquo;{testimonial.quote}&rdquo;</p>
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${testimonial.gradient} flex items-center justify-center text-white font-semibold text-xs shadow-lg`}>{testimonial.avatar}</div>
                <div>
                  <div className="font-semibold text-white text-sm">{testimonial.author}</div>
                  <div className="text-xs text-zinc-700">{testimonial.role}</div>
                </div>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}
