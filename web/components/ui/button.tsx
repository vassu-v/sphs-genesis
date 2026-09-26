import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center gap-2 text-sm font-semibold rounded-sm transition-colors disabled:opacity-50 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        primary: 'bg-accent text-bg px-[18px] py-[9px] hover:bg-[#e8ff70]',
        outline: 'border border-line text-ink px-[18px] py-[9px] hover:border-accent hover:text-accent',
        ghost: 'border border-line text-ink-dim px-[14px] py-2 hover:text-ink hover:border-ink-dim',
      },
    },
    defaultVariants: { variant: 'primary' },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, ...props }, ref) => (
    <button className={cn(buttonVariants({ variant }), className)} ref={ref} {...props} />
  )
);
Button.displayName = 'Button';

export { Button, buttonVariants };
