interface PagePlaceholderProps {
  title: string
  subtitle?: string
}

export function PagePlaceholder({ title, subtitle }: PagePlaceholderProps) {
  return (
    <div className="p-6 md:p-8">
      <div className="mb-8">
        <h1 className="font-heading font-bold text-2xl text-anthracite">{title}</h1>
        {subtitle && (
          <p className="font-heading text-[14px] text-gray-dk mt-1">{subtitle}</p>
        )}
      </div>
      <div className="border-2 border-dashed border-gray-light rounded-xl p-12 flex flex-col items-center justify-center text-center gap-3 min-h-[240px]">
        <div className="w-12 h-12 rounded-xl bg-orange/10 flex items-center justify-center">
          <span className="font-heading font-bold text-xl text-orange">/</span>
        </div>
        <p className="font-heading text-[14px] font-semibold text-gray-dk">
          Implémenté au PROMPT 4
        </p>
        <p className="font-heading text-[12px] text-gray-med">
          Phase 3 Shell · Navigation opérationnelle
        </p>
      </div>
    </div>
  )
}
