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
  // Le backend FastAPI est l'unique source de vérité pour /api/* — en
  // production, Nginx route déjà tout /api/ vers le backend (port 8000)
  // AVANT que Next.js ne voie la requête, rendant cette règle inopérante
  // (donc sans risque de conflit). En dev local (`npm run dev`, pas de
  // Nginx), elle reproduit le même comportement : jusqu'ici, deux copies
  // de la logique de login coexistaient (app/api/auth/login,
  // app/api/admin/login vs backend/api/auth_routes.py) — la copie
  // frontend n'était JAMAIS atteinte en production (Nginx interceptait
  // avant), seulement en dev local, créant un écart de comportement
  // invisible entre les deux environnements. Supprimée au profit de
  // cette redirection vers le backend, seule implémentation réelle.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.BACKEND_URL || 'http://localhost:8000'}/api/:path*`,
      },
    ]
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
