interface SpinnerProps {
  size?: 'xs' | 'sm' | 'md' | 'lg'
  className?: string
  label?: string
}

const sizes = {
  xs: 'w-3 h-3 border-[1.5px]',
  sm: 'w-4 h-4 border-2',
  md: 'w-6 h-6 border-2',
  lg: 'w-8 h-8 border-[3px]',
}

export function Spinner({ size = 'md', className = '', label = 'Chargement…' }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label={label}
      className={`inline-block rounded-full border-orange border-t-transparent animate-spin ${sizes[size]} ${className}`}
    />
  )
}
