export function toDateStr(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

// 回傳 6*7 格子陣列（前後補位用 null），每格 { date: Date, dateStr: string } 或 null
export function buildMonthGrid(year, month) {
  const firstDay = new Date(year, month, 1)
  const startOffset = firstDay.getDay() // 0=週日
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  const cells = []
  for (let i = 0; i < startOffset; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) {
    const date = new Date(year, month, d)
    cells.push({ date, dateStr: toDateStr(date) })
  }
  while (cells.length % 7 !== 0) cells.push(null)
  while (cells.length < 42) cells.push(null)

  const weeks = []
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))
  return weeks
}
