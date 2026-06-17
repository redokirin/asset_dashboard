import axios from 'axios'

const base = import.meta.env.VITE_API_BASE || ''

export async function fetchSummary() {
  const { data } = await axios.get(`${base}/api/summary`)
  return data
}

export async function fetchPortfolio() {
  const { data } = await axios.get(`${base}/api/portfolio`)
  return data
}
