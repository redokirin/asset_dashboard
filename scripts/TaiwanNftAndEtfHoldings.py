import json
import matplotlib.pyplot as plt
import numpy as np

json_str = """
{
    "total_value_twd": 1789737.25,
    "assets_count": 10,
    "exposures": [
        {"symbol": "2330.TW", "name": "Taiwan Semiconductor Manufacturing Co Ltd", "weight": 0.105761, "sources": ["0052.TW", "00985A.TW", "00981A.TW", "2330.TW", "0P00006AKV.TW", "0P00009PAQ.TW"]},
        {"symbol": "NVDA", "name": "NVIDIA Corp", "weight": 0.027614, "sources": ["1655.T"]},
        {"symbol": "AAPL", "name": "Apple Inc", "weight": 0.024658, "sources": ["1655.T"]},
        {"symbol": "MSFT", "name": "Microsoft Corp", "weight": 0.017994, "sources": ["1655.T"]},
        {"symbol": "AMZN", "name": "Amazon.com Inc", "weight": 0.014229, "sources": ["1655.T"]},
        {"symbol": "GOOGL", "name": "Alphabet Inc Class A", "weight": 0.011918, "sources": ["1655.T"]},
        {"symbol": "AVGO", "name": "Broadcom Inc", "weight": 0.011401, "sources": ["1655.T"]},
        {"symbol": "2383.TW", "name": "Elite Material Co Ltd", "weight": 0.010014, "sources": ["0052.TW", "00981A.TW", "0P00006AKV.TW", "0P00009PAQ.TW"]},
        {"symbol": "GOOG", "name": "Alphabet Inc Class C", "weight": 0.009475, "sources": ["1655.T"]},
        {"symbol": "3017.TW", "name": "Asia Vital Components Co Ltd", "weight": 0.009209, "sources": ["0052.TW", "00981A.TW", "00988A.TW", "0P00006AKV.TW", "0P00009PAQ.TW"]},
        {"symbol": "8306.T", "name": "Mitsubishi UFJ Financial Group Inc", "weight": 0.008717, "sources": ["1306.T"]},
        {"symbol": "3653.TW", "name": "Jentech Precision Industrial Co Ltd", "weight": 0.008314, "sources": ["00981A.TW", "0P00006AKV.TW", "0P00009PAQ.TW"]},
        {"symbol": "MU", "name": "Micron Technology Inc", "weight": 0.008103, "sources": ["1655.T", "00988A.TW"]},
        {"symbol": "7203.T", "name": "Toyota Motor Corp", "weight": 0.007565, "sources": ["1306.T"]},
        {"symbol": "META", "name": "Meta Platforms Inc Class A", "weight": 0.007446, "sources": ["1655.T"]},
        {"symbol": "9984.T", "name": "SoftBank Group Corp", "weight": 0.006737, "sources": ["1306.T"]},
        {"symbol": "3037.TW", "name": "Unimicron Technology Corp", "weight": 0.006733, "sources": ["0052.TW", "0P00006AKV.TW", "0P00009PAQ.TW"]},
        {"symbol": "TSLA", "name": "Tesla Inc", "weight": 0.006597, "sources": ["1655.T"]},
        {"symbol": "3665.TW", "name": "Bizlink Holding Inc", "weight": 0.006466, "sources": ["00981A.TW", "0P00006AKV.TW", "0P00009PAQ.TW"]},
        {"symbol": "6223.TWO", "name": "MPI Corp", "weight": 0.006436, "sources": ["00981A.TW", "0P00006AKV.TW"]},
        {"symbol": "6515.TW", "name": "WinWay Technology Co Ltd Ordinary Shares", "weight": 0.006253, "sources": ["00988A.TW", "0P00006AKV.TW"]},
        {"symbol": "6501.T", "name": "Hitachi Ltd", "weight": 0.006148, "sources": ["1306.T"]},
        {"symbol": "8316.T", "name": "Sumitomo Mitsui Financial Group Inc", "weight": 0.005844, "sources": ["1306.T"]},
        {"symbol": "6758.T", "name": "Sony Group Corp", "weight": 0.005558, "sources": ["1306.T"]},
        {"symbol": "8035.T", "name": "Tokyo Electron Ltd", "weight": 0.00515, "sources": ["1306.T"]},
        {"symbol": "2308.TW", "name": "Delta Electronics Inc", "weight": 0.004951, "sources": ["00985A.TW", "00981A.TW", "0P00009PAQ.TW"]},
        {"symbol": "2395.TW", "name": "Advantech Co Ltd", "weight": 0.004833, "sources": ["00985A.TW"]},
        {"symbol": "8411.T", "name": "Mizuho Financial Group Inc", "weight": 0.004612, "sources": ["1306.T"]},
        {"symbol": "8058.T", "name": "Mitsubishi Corp", "weight": 0.004603, "sources": ["1306.T"]},
        {"symbol": "6981.T", "name": "Murata Manufacturing Co Ltd", "weight": 0.004297, "sources": ["1306.T"]},
        {"symbol": "LITE", "name": "Lumentum Holdings Inc", "weight": 0.0042, "sources": ["00988A.TW"]},
        {"symbol": "2317.TW", "name": "Hon Hai Precision Industry Co Ltd", "weight": 0.004013, "sources": ["0052.TW"]},
        {"symbol": "6442.TW", "name": "Ezconn Corp", "weight": 0.003965, "sources": ["0P00006AKV.TW"]},
        {"symbol": "2454.TW", "name": "MediaTek Inc", "weight": 0.003844, "sources": ["0052.TW"]},
        {"symbol": "2412.TW", "name": "Chunghwa Telecom Co Ltd", "weight": 0.003828, "sources": ["00985A.TW"]},
        {"symbol": "3189.TW", "name": "Kinsus Interconnect Technology Corp", "weight": 0.003472, "sources": ["0P00006AKV.TW"]},
        {"symbol": "1216.TW", "name": "Uni-President Enterprises Corp", "weight": 0.003037, "sources": ["00985A.TW"]},
        {"symbol": "3293.TWO", "name": "International Games System Co Ltd", "weight": 0.003024, "sources": ["00985A.TW"]},
        {"symbol": "4904.TW", "name": "Far EasTone Telecommunications Co Ltd", "weight": 0.002386, "sources": ["00985A.TW"]},
        {"symbol": "SNDK", "name": "SanDisk Corp Ordinary Shares", "weight": 0.002278, "sources": ["00988A.TW"]},
        {"symbol": "2345.TW", "name": "Accton Technology Corp", "weight": 0.002234, "sources": ["00981A.TW", "0P00009PAQ.TW"]},
        {"symbol": "GLW", "name": "Corning Inc", "weight": 0.001961, "sources": ["00988A.TW"]},
        {"symbol": "3711.TW", "name": "ASE Technology Holding Co Ltd", "weight": 0.001891, "sources": ["0052.TW"]},
        {"symbol": "2881.TW", "name": "Fubon Financial Holdings Co Ltd", "weight": 0.001874, "sources": ["00985A.TW"]},
        {"symbol": "2368.TW", "name": "Gold Circuit Electronics Ltd", "weight": 0.00183, "sources": ["00981A.TW"]},
        {"symbol": "CIEN", "name": "Ciena Corp", "weight": 0.001763, "sources": ["00988A.TW"]},
        {"symbol": "6787.T", "name": "Meiko Electronics Co Ltd", "weight": 0.001752, "sources": ["00988A.TW"]},
        {"symbol": "GEV", "name": "GE Vernova Inc", "weight": 0.001711, "sources": ["00988A.TW"]},
        {"symbol": "4749.TWO", "name": "Advanced Echem Materials Co Ltd", "weight": 0.001679, "sources": ["00985A.TW"]},
        {"symbol": "2360.TW", "name": "Chroma Ate Inc", "weight": 0.001557, "sources": ["00985A.TW"]},
        {"symbol": "5801.T", "name": "Furukawa Electric Co Ltd", "weight": 0.001551, "sources": ["00988A.TW"]},
        {"symbol": "2382.TW", "name": "Quanta Computer Inc", "weight": 0.00129, "sources": ["0052.TW"]},
        {"symbol": "5274.TWO", "name": "Aspeed Technology Inc", "weight": 0.001191, "sources": ["00981A.TW"]},
        {"symbol": "2303.TW", "name": "United Microelectronics Corp", "weight": 0.001156, "sources": ["0052.TW"]},
        {"symbol": "2327.TW", "name": "Yageo Corp", "weight": 0.000663, "sources": ["0052.TW"]},
        {"symbol": "8996.TW", "name": "Kaori Heat Treatment Co Ltd", "weight": 0.000407, "sources": ["0P00009PAQ.TW"]},
        {"symbol": "3081.TWO", "name": "LandMark Optoelectronics Corp", "weight": 0.000296, "sources": ["0P00009PAQ.TW"]}
    ],
    "buckets": [
        {"label": "美股其他持股", "weight": 0.213095},
        {"label": "日股其他持股", "weight": 0.199758},
        {"label": "台股其他持股", "weight": 0.115624},
        {"label": "全球其他持股", "weight": 0.045035}
    ],
    "identified_pct": 0.426488,
    "unidentified_pct": 0.573512
}
"""
data = json.loads(json_str)

exposures = data['exposures']
buckets = data['buckets']

# Sort exposures by weight descending
exposures = sorted(exposures, key=lambda x: x['weight'], reverse=True)

labels = []
weights = []

# Take top 10 individual stocks for clarity
top_n = 10
for exp in exposures[:top_n]:
    name = exp['name'].split()[0]  # Take first word or two for brevity if too long
    # Hardcode some cleaner names for better display
    clean_name = exp['symbol']
    if exp['symbol'] == '2330.TW': clean_name = '台積電'
    elif exp['symbol'] == '2383.TW': clean_name = '台光電'
    elif exp['symbol'] == '3017.TW': clean_name = '奇鋐'
    
    labels.append(f"{clean_name} ({exp['weight']*100:.1f}%)")
    weights.append(exp['weight'])

# Sum remaining individual stocks
rem_weight = sum(exp['weight'] for exp in exposures[top_n:])
if rem_weight > 0:
    labels.append(f"其他已識別個股 ({rem_weight*100:.1f}%)")
    weights.append(rem_weight)

# Add buckets
for b in buckets:
    labels.append(f"{b['label']} ({b['weight']*100:.1f}%)")
    weights.append(b['weight'])

# Plotting
plt.rcParams['font.sans-serif'] = ['Heiti TC', 'Arial Unicode MS', 'SimHei', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False
plt.figure(figsize=(11, 9))

# Create a good color map
colors = plt.cm.tab20(np.linspace(0, 1, len(labels)))

plt.pie(weights, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors, textprops={'fontsize': 11})
plt.title('整體投資組合部位分佈 (依最新 JSON 解析)', fontsize=15, weight='bold')
plt.tight_layout()
plt.savefig('json_portfolio_pie_chart.png', dpi=300)
plt.close()