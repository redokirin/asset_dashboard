import axios from 'axios'

const base = import.meta.env.VITE_API_BASE || ''

export async function fetchPortfolio() {
  const { data } = await axios.get(`${base}/api/portfolio`)
  return data
}

export async function fetchAdvanced() {
  const { data } = await axios.get(`${base}/api/analysis/advanced`)
  return data
}

export async function fetchRisk() {
  const { data } = await axios.get(`${base}/api/analysis/risk`)
  return data
}

export async function fetchDailySummary() {
  const { data } = await axios.get(`${base}/api/summary/daily`)
  return data
}

export async function fetchHistorical(ticker, period = '2y') {
  const { data } = await axios.get(`${base}/api/ticker/${encodeURIComponent(ticker)}/historical`, {
    params: { period },
  })
  return data
}

export async function fetchFundamental(ticker) {
  const { data } = await axios.get(`${base}/api/ticker/${encodeURIComponent(ticker)}/fundamental`)
  return data
}

export async function fetchExportAi() {
  const { data } = await axios.get(`${base}/api/export/ai`)
  return data
}

export async function fetchExportAiTicker(ticker) {
  const { data } = await axios.get(`${base}/api/export/ai/${encodeURIComponent(ticker)}`)
  return data
}

export async function fetchManualAnalysis(tickers) {
  const { data } = await axios.post(`${base}/api/analysis/manual`, { tickers })
  return data
}

export async function fetchHoldings(ticker) {
  const { data } = await axios.get(`${base}/api/holdings/${encodeURIComponent(ticker)}`)
  return data
}

export async function fetchXray() {
  const { data } = await axios.get(`${base}/api/xray`)
  return data
}

export async function fetchTransactions() {
  const { data } = await axios.get(`${base}/api/transactions`)
  return data
}

export async function fetchPortfolioHistory(days = 90) {
  const { data } = await axios.get(`${base}/api/portfolio/history`, { params: { days } })
  return data
}
