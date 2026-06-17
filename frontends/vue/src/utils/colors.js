export const COLOR_PROFIT = 'text-red-400'
export const COLOR_LOSS   = 'text-green-400'

export function plColor(n) {
  if (n == null) return ''
  return n >= 0 ? COLOR_PROFIT : COLOR_LOSS
}
