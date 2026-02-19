/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'misc-assets.raycast.com',
        pathname: '/wallpapers/**',
      },
    ],
  },
}

module.exports = nextConfig
