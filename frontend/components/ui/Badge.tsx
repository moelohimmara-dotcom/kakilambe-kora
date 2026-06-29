import { ReactNode } from 'react'

export type BadgeVariant = 'orange' | 'sage' | 'blue' | 'gray' | 'danger' | 'warning'

const variants: Record<BadgeVariant, string> = {
  orange:  'bg-orange/10 text-orange',
  sage:    'bg-sage/10 text-sage',
  blue:    'bg-blue/12 text-blue-txt',
  gray:    'bg-gray-pale text-gray-dk',
  danger:  'bg-danger/10 text-danger',
  warning: 'bg-warning/10 text-warning',
}

interface BadgeProps {
  variant?: BadgeVariant
  dot?: boolean
  pulse?: boolean
  children: ReactNode
  className?: string
}

export function Badge({
  variant = 'gray',
  dot = false,
  pulse = false,
  children,
  className = '',
}: BadgeProps) {
  return (
    <span
      className={
        `inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full ` +
        `font-heading text-[11px] font-semibold ${variants[variant]} ${className}`
      }
    >
      {dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full bg-current ${pulse ? 'animate-[kora-pulse_2s_ease-in-out_infinite]' : ''}`}
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  )
}
