import { Github, Twitter } from 'lucide-react'

const footerLinks = {
    Product: ['Features', 'AI Engine', 'Automation', 'Routing', 'Dashboard', 'Pricing'],
    Developers: ['API Docs', 'GitHub', 'Webhooks', 'SDK', 'Plugins'],
    Resources: ['Documentation', 'Blog', 'Changelog', 'FAQ', 'Templates'],
    Company: ['About', 'Careers', 'Press', 'Contact'],
}

export default function Footer() {
    return (
        <footer className="border-t border-white/[0.04] bg-black py-16 px-6">
            <div className="max-w-7xl mx-auto grid grid-cols-2 md:grid-cols-5 gap-10">
                <div className="col-span-2 md:col-span-1">
                    <div className="flex items-center gap-2.5 mb-6">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500 to-pink-600 flex items-center justify-center">
                            <span className="text-white font-bold text-sm">N</span>
                        </div>
                        <span className="font-semibold text-white">Nexus</span>
                    </div>
                    <p className="text-zinc-600 text-sm mb-6 leading-relaxed">AI-powered support platform. Everything you need, in one place.</p>
                    <div className="flex gap-4">
                        <a href="https://github.com/Kannan-Khosla/Nexus" target="_blank" rel="noopener noreferrer" className="text-zinc-600 hover:text-white transition-colors duration-200"><Github size={20} /></a>
                        <a href="#" className="text-zinc-600 hover:text-white transition-colors duration-200"><Twitter size={20} /></a>
                    </div>
                </div>
                {Object.entries(footerLinks).map(([category, links]) => (
                    <div key={category}>
                        <h3 className="font-medium text-zinc-400 mb-4 text-sm">{category}</h3>
                        <ul className="space-y-3">
                            {links.map((link) => (
                                <li key={link}><a href="#" className="text-zinc-700 hover:text-white transition-colors duration-200 text-sm">{link}</a></li>
                            ))}
                        </ul>
                    </div>
                ))}
            </div>
            <div className="max-w-7xl mx-auto mt-16 pt-8 border-t border-white/[0.03] flex flex-col md:flex-row justify-between items-center text-zinc-700 text-sm gap-4">
                <p>&copy; {new Date().getFullYear()} Nexus. All rights reserved.</p>
                <div className="flex gap-6">
                    <a href="#" className="hover:text-zinc-400 transition-colors">Privacy</a>
                    <a href="#" className="hover:text-zinc-400 transition-colors">Terms</a>
                    <a href="#" className="hover:text-zinc-400 transition-colors">Security</a>
                </div>
            </div>
        </footer>
    )
}
