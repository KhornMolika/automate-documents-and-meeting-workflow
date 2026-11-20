import { cva, type VariantProps } from 'class-variance-authority'

export { default as Button } from './Button.vue'

export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        brand: 'bg-brand text-brand-foreground hover:bg-brand-deep',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        outline: 'border border-input bg-card hover:bg-secondary text-foreground',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/75',
        ghost: 'hover:bg-secondary text-foreground',
        link: 'text-brand underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4 py-2 max-sm:h-10',
        sm: 'h-8 rounded-md px-3 text-[13px] max-sm:h-9',
        xs: 'h-7 rounded px-2 text-xs',
        lg: 'h-10 rounded-md px-5',
        icon: 'h-8 w-8 max-sm:h-10 max-sm:w-10',
        'icon-sm': 'h-7 w-7',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export type ButtonVariants = VariantProps<typeof buttonVariants>
