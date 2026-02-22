import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Combina classes CSS com suporte a condicionais e merge do Tailwind.
 * Utiliza clsx para condicionais e tailwind-merge para resolver conflitos.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
