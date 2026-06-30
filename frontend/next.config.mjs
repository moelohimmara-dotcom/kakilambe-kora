import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

/** @type {import('next').NextConfig} */
const PRIVATE_ROUTES = [
  '/dashboard', '/articles', '/agent', '/chat',
  '/history', '/settings', '/sources', '/system',
]

const nextConfig = {
  webpack(config) {
    config.resolve.alias['@'] = path.resolve(__dirname)
    return config
  },
  async headers() {
    return PRIVATE_ROUTES.map(route => ({
      source: `${route}/:path*`,
      headers: [
        { key: 'Cache-Control', value: 'private, no-store, must-revalidate' },
        { key: 'Surrogate-Control', value: 'no-store' },
      ],
    })).concat([{
      source: '/api/:path*',
      headers: [
        { key: 'Cache-Control', value: 'no-store' },
      ],
    }])
  },
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
