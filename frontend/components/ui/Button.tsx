import { forwardRef, ButtonHTMLAttributes, AnchorHTMLAttributes, ReactNode } from 'react'
import Link from 'next/link'

type Variant = 'primary' | 'ghost' | 'danger' | 'outline'
type Size    = 'sm' | 'md' | 'lg'

const base =
  'inline-flex items-center justify-center gap-2 rounded-md font-heading font-semibold ' +
  'transition-all duration-150 border border-transparent cursor-pointer ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange focus-visible:ring-offset-2 ' +
  'disabled:opacity-40 disabled:pointer-events-none select-none'

const variants: Record<Variant, string> = {
  primary:
    'bg-orange text-white border-orange hover:bg-orange-dk hover:border-orange-dk ' +
    'hover:-translate-y-px hover:shadow-[0_4px_12px_rgba(217,119,87,.3)]',
  ghost:
    'bg-transparent text-gray-dk border-gray-light hover:bg-gray-pale hover:-translate-y-px',
  danger:
    'bg-transparent text-danger border-danger/30 hover:bg-danger/10',
  outline:
    'bg-white text-anthracite border-gray-light hover:border-orange hover:text-orange hover:-translate-y-px',
}

// min-h : cible tactile mobile (≥44-48px, WCAG/Material) — le padding et le
// texte restent compacts visuellement, seule la zone cliquable s'agrandit
// verticalement (Button est déjà inline-flex items-center, contenu centré).
const sizes: Record<Size, string> = {
  sm:  'px-3.5 py-[7px] text-[12px] rounded-sm min-h-[44px]',
  md:  'px-5 py-[9px] text-[13px] min-h-[44px]',
  lg:  'px-7 py-3 text-[15px] font-bold min-h-[48px]',
}

interface BaseProps {
  variant?: Variant
  size?: Size
  children: ReactNode
  loading?: boolean
  icon?: ReactNode
}

type ButtonProps = BaseProps & ButtonHTMLAttributes<HTMLButtonElement> & { href?: undefined }
type LinkProps   = BaseProps & AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }

type Props = ButtonProps | LinkProps

export const Button = forwardRef<HTMLButtonElement | HTMLAnchorElement, Props>(
  (
    { variant = 'primary', size = 'md', children, loading, icon, className = '', ...rest },
    ref
  ) => {
    const cls = `${base} ${variants[variant]} ${sizes[size]} ${className}`

    const content = (
      <>
        {loading ? <Spinner size={size} /> : icon}
        {children}
      </>
    )

    if ('href' in rest && rest.href) {
      const { href, ...anchorRest } = rest as LinkProps
      return (
        <Link href={href} className={cls} ref={ref as React.Ref<HTMLAnchorElement>} {...anchorRest}>
          {content}
        </Link>
      )
    }

    return (
      <button
        className={cls}
        ref={ref as React.Ref<HTMLButtonElement>}
        disabled={loading || (rest as ButtonProps).disabled}
        {...(rest as ButtonHTMLAttributes<HTMLButtonElement>)}
      >
        {content}
      </button>
    )
  }
)

Button.displayName = 'Button'

function Spinner({ size }: { size: Size }) {
  const s = size === 'sm' ? 'w-3 h-3' : size === 'lg' ? 'w-5 h-5' : 'w-4 h-4'
  return (
    <span
      className={`${s} rounded-full border-2 border-current border-t-transparent animate-spin`}
      aria-hidden="true"
    />
  )
}
