import { HTMLAttributes, ReactNode } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  hover?: boolean
  padding?: 'sm' | 'md' | 'lg'
  as?: 'div' | 'article' | 'section'
}

export function Card({
  children,
  hover = false,
  padding = 'md',
  as: Tag = 'div',
  className = '',
  ...rest
}: CardProps) {
  const paddings = { sm: 'p-4', md: 'p-5', lg: 'p-6' }

  return (
    <Tag
      className={
        `bg-white border border-gray-light rounded-lg shadow-card ` +
        `${hover ? 'hover:shadow-card-hover hover:-translate-y-px transition-all duration-150 cursor-pointer' : ''} ` +
        `${paddings[padding]} ${className}`
      }
      {...rest}
    >
      {children}
    </Tag>
  )
}
