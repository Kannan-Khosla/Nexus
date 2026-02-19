'use client'

import { motion } from 'framer-motion'
import { ArrowRight, Github, Sparkles } from 'lucide-react'
import Image from 'next/image'
import { springTransition } from '@/lib/motion'

export default function Hero() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center pt-32 px-4 overflow-hidden">
      {/* ===== Mesh Gradient Breathing Orbs — The "Living" Background ===== */}
      <div className="absolute inset-0 pointer-events-none">
        {/* Orb 1: Deep crimson — top-left, largest */}
        <div className="mesh-orb-1 absolute top-[-25%] left-[-15%] w-[70%] h-[70%] rounded-full bg-[radial-gradient(circle,rgba(220,38,38,0.25)_0%,transparent_70%)] blur-[100px]" />
        {/* Orb 2: Magenta — bottom-right */}
        <div className="mesh-orb-2 absolute bottom-[-20%] right-[-10%] w-[60%] h-[60%] rounded-full bg-[radial-gradient(circle,rgba(236,72,153,0.2)_0%,transparent_70%)] blur-[120px]" />
        {/* Orb 3: Warm charcoal/amber — center */}
        <div className="mesh-orb-3 absolute top-[10%] right-[20%] w-[50%] h-[50%] rounded-full bg-[radial-gradient(circle,rgba(245,158,11,0.12)_0%,transparent_60%)] blur-[100px]" />
      </div>

      {/* ===== Raycast Wallpaper Layers ===== */}
      <div className="absolute inset-0 w-full h-full pointer-events-none">
        {/* Layer 1: Main wallpaper with breathing + color shift */}
        <div className="hero-bg-breathe absolute inset-[-15%] w-[130%] h-[130%]">
          <Image
            src="https://misc-assets.raycast.com/wallpapers/red_distortion_1_preview.png"
            alt=""
            fill
            priority
            className="object-cover mix-blend-screen"
            quality={100}
          />
        </div>

        {/* Layer 2: Duplicate with offset drift for parallax depth */}
        <div className="hero-bg-drift absolute inset-[-10%] w-[120%] h-[120%] opacity-40">
          <Image
            src="https://misc-assets.raycast.com/wallpapers/red_distortion_1_preview.png"
            alt=""
            fill
            className="object-cover mix-blend-screen blur-sm"
            quality={50}
          />
        </div>

        {/* Layer 3: Moving light sweep */}
        <div className="hero-light-sweep absolute inset-0 w-[60%] h-full bg-gradient-to-r from-transparent via-white/[0.04] to-transparent" />

        {/* Layer 4: Pulsing crimson glow (top-center) */}
        <div className="hero-glow-pulse absolute top-[-20%] left-[20%] w-[60%] h-[60%] rounded-full bg-red-500/20 blur-[120px]" />

        {/* Layer 5: Pulsing magenta glow (bottom-right, delayed) */}
        <div className="hero-glow-pulse-delay absolute bottom-[-10%] right-[10%] w-[40%] h-[50%] rounded-full bg-pink-500/15 blur-[100px]" />

        {/* Floating particles */}
        <div className="animate-particle absolute top-[15%] left-[10%] w-2 h-2 rounded-full bg-red-400/30" />
        <div className="animate-particle absolute top-[25%] right-[15%] w-1.5 h-1.5 rounded-full bg-pink-400/25" style={{ animationDelay: '1s' }} />
        <div className="animate-particle absolute top-[60%] left-[25%] w-1 h-1 rounded-full bg-orange-400/40" style={{ animationDelay: '2.5s' }} />
        <div className="animate-particle absolute top-[45%] right-[30%] w-2.5 h-2.5 rounded-full bg-red-400/15" style={{ animationDelay: '0.5s' }} />
        <div className="animate-particle absolute top-[70%] left-[60%] w-1.5 h-1.5 rounded-full bg-pink-300/20" style={{ animationDelay: '3s' }} />

        {/* Edge fade overlays */}
        <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-black/70" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,black_75%)]" />
      </div>

      {/* ===== Content ===== */}
      <div className="z-10 text-center max-w-5xl mx-auto relative">
        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ ...springTransition, delay: 0 }}
          className="inline-flex items-center gap-2 px-4 py-1.5 mb-8 rounded-full bg-white/[0.04] border border-white/[0.06] backdrop-blur-sm"
        >
          <Sparkles className="w-3.5 h-3.5 text-red-400" />
          <span className="text-xs font-medium text-zinc-500">Open-source • Production-ready • Built with FastAPI & React</span>
        </motion.div>

        {/* === Gradient Shine Headline === */}
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...springTransition, delay: 0.1 }}
          className="text-6xl md:text-8xl lg:text-[6.5rem] font-bold tracking-tight mb-8 leading-[1.05]"
        >
          <span className="bg-clip-text text-transparent bg-gradient-to-b from-white via-white to-white/40">
            Your shortcut to
          </span>
          <br />
          <span className="bg-clip-text text-transparent bg-[linear-gradient(90deg,#ef4444,#f97316,#ec4899,#a855f7,#ef4444)] animate-gradient-shine bg-[length:200%_auto]">
            everything
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...springTransition, delay: 0.2 }}
          className="text-xl md:text-2xl text-zinc-500 max-w-3xl mx-auto mb-10 font-light leading-relaxed"
        >
          A collection of powerful AI-powered support tools all within an extendable platform. Fast, smart and reliable.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ ...springTransition, delay: 0.3 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <a
            href="https://github.com/Kannan-Khosla/Nexus"
            target="_blank"
            rel="noopener noreferrer"
            className="group relative inline-flex items-center gap-2.5 bg-white text-black px-8 py-4 rounded-full font-semibold text-lg hover:bg-zinc-200 transition-all duration-300 active:scale-[0.98] hover:shadow-[0_0_40px_rgba(255,255,255,0.12)]"
          >
            <Github className="w-5 h-5" />
            View on GitHub
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </a>
          <a
            href="https://github.com/Kannan-Khosla/Nexus#readme"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-zinc-500 hover:text-white px-6 py-4 rounded-full font-medium text-lg transition-all hover:bg-white/[0.04] border border-transparent hover:border-white/[0.08] active:scale-[0.98]"
          >
            Read the Docs
            <ArrowRight className="w-4 h-4" />
          </a>
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.5, duration: 1 }}
        className="absolute bottom-8 z-10"
      >
        <div className="w-6 h-10 rounded-full border-2 border-white/15 flex justify-center pt-2">
          <motion.div
            animate={{ y: [0, 12, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
            className="w-1.5 h-1.5 rounded-full bg-white/40"
          />
        </div>
      </motion.div>
    </section>
  )
}
