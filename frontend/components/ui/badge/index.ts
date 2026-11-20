import { cva, type VariantProps } from 'class-variance-authority'

export { default as Badge } from './Badge.vue'

export const badgeVariants = cva(
  'inline-flex flex-none items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-[16px] whitespace-nowrap',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground',
        secondary: 'border-transparent bg-secondary text-secondary-foreground',
        outline: 'border-border bg-transparent text-muted-foreground',
        brand: 'border-transparent bg-brand text-brand-foreground',
        live: 'border-brand/20 bg-brand-soft text-brand',
        positive: 'border-transparent bg-positive-soft text-positive',
        warning: 'border-transparent bg-warning-soft text-warning',
        negative: 'border-transparent bg-negative-soft text-negative',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

export type BadgeVariants = VariantProps<typeof badgeVariants>
