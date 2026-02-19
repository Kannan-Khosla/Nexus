'use client'

import { motion } from 'framer-motion'
import { Github, ArrowRight } from 'lucide-react'
import { springTransition, headingReveal } from '@/lib/motion'

export default function CTA() {
  return (
    <section id="pricing" className="py-32 px-6 relative overflow-hidden">
      {/* Animated mesh gradient orbs */}
      <div className="mesh-orb-1 absolute top-[-20%] left-[30%] w-[40%] h-[60%] rounded-full bg-[radial-gradient(circle,rgba(220,38,38,0.1)_0%,transparent_70%)] blur-[120px] pointer-events-none" />
      <div className="mesh-orb-2 absolute bottom-[-10%] right-[20%] w-[30%] h-[50%] rounded-full bg-[radial-gradient(circle,rgba(236,72,153,0.08)_0%,transparent_70%)] blur-[100px] pointer-events-none" />

      <div className="max-w-4xl mx-auto text-center relative">
        <motion.div variants={headingReveal} initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-100px' }}>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-b from-white to-white/40">Take the short way</h2>
          <p className="text-xl text-zinc-500 mb-12 max-w-2xl mx-auto">Open-source and production-ready. Start using Nexus today.</p>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 30, scale: 0.97 }} whileInView={{ opacity: 1, y: 0, scale: 1 }} viewport={{ once: true }} transition={{ ...springTransition, delay: 0.15 }} className="flex flex-col sm:flex-row gap-4 justify-center items-center">
          <a href="https://github.com/Kannan-Khosla/Nexus" target="_blank" rel="noopener noreferrer" className="group relative inline-flex items-center gap-2.5 bg-white text-black px-8 py-4 rounded-full text-lg font-semibold hover:bg-zinc-200 transition-all duration-300 active:scale-[0.98] hover:shadow-[0_0_40px_rgba(255,255,255,0.12)]">
            <Github className="w-5 h-5" />
            View on GitHub
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </a>
        </motion.div>
      </div>
    </section>
  )
}
