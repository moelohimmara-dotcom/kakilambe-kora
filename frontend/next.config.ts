import type { NextConfig } from 'next'
import path from 'path'

const nextConfig: NextConfig = {
  // Fix outputFileTracing pour route groups (editorial) sur Vercel
  outputFileTracingRoot: path.join(__dirname),

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
