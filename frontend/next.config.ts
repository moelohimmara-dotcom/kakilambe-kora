import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'kakilambe.com' },
      { protocol: 'https', hostname: 'image.pollinations.ai' },
      { protocol: 'https', hostname: '*.fal.run' },
      { protocol: 'https', hostname: '*.fal.ai' },
    ],
  },
}

export default nextConfig
