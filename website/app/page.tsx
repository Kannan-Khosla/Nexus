'use client'

import Hero from '@/components/Hero'
import InteractiveKeyboard from '@/components/InteractiveKeyboard'
import FeatureCarousel from '@/components/FeatureCarousel'
import AIDemo from '@/components/AIDemo'
import Features from '@/components/Features'
import AISection from '@/components/AISection'
import Automation from '@/components/Automation'
import TechStack from '@/components/TechStack'
import Testimonials from '@/components/Testimonials'
import CTA from '@/components/CTA'
import Navbar from '@/components/Navbar'
import Footer from '@/components/Footer'

export default function Home() {
  return (
    <main className="min-h-screen bg-black text-white overflow-x-hidden selection:bg-red-500/20">
      <Navbar />
      <Hero />

      {/* Section divider */}
      <div className="section-glow-line mx-auto max-w-5xl" />

      <InteractiveKeyboard />
      <FeatureCarousel />

      <div className="section-glow-line mx-auto max-w-5xl" />

      <AIDemo />
      <Features />

      <div className="section-glow-line mx-auto max-w-5xl" />

      <AISection />
      <Automation />
      <TechStack />

      <div className="section-glow-line mx-auto max-w-5xl" />

      <Testimonials />
      <CTA />
      <Footer />
    </main>
  )
}
