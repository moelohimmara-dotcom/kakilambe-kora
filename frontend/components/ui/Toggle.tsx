'use client'

import { useId } from 'react'

interface ToggleProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label?: string
  description?: string
  disabled?: boolean
  size?: 'sm' | 'md'
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled = false,
  size = 'md',
}: ToggleProps) {
  const id = useId()

  const trackSm = 'w-8 h-4'
  const thumbSm = 'w-3 h-3 translate-x-0.5'
  const thumbSmOn = 'translate-x-[18px]'

  const trackMd = 'w-11 h-6'
  const thumbMd = 'w-4 h-4 translate-x-1'
  const thumbMdOn = 'translate-x-6'

  const trackCls = size === 'sm' ? trackSm : trackMd
  const thumbBase = `absolute top-1/2 -translate-y-1/2 rounded-full bg-white shadow transition-transform duration-200 ${size === 'sm' ? thumbSm : thumbMd}`
  const thumbOn   = size === 'sm' ? thumbSmOn : thumbMdOn

  return (
    <div className="flex items-center gap-3">
      <button
        id={id}
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={
          `relative inline-flex shrink-0 rounded-full border-2 border-transparent ` +
          `transition-colors duration-200 cursor-pointer ` +
          `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange focus-visible:ring-offset-2 ` +
          `disabled:opacity-40 disabled:cursor-not-allowed ` +
          `${trackCls} ${checked ? 'bg-orange' : 'bg-gray-light'}`
        }
      >
        <span className={`${thumbBase} ${checked ? thumbOn : ''}`} aria-hidden="true" />
      </button>

      {(label || description) && (
        <label htmlFor={id} className="cursor-pointer select-none">
          {label && (
            <span className="block font-heading text-[13px] font-medium text-anthracite">
              {label}
            </span>
          )}
          {description && (
            <span className="block font-heading text-[12px] text-gray-dk mt-0.5">
              {description}
            </span>
          )}
        </label>
      )}
    </div>
  )
}
