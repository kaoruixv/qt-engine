import yfinance as yf
import statsmodels.api as sm
import matplotlib.pyplot as plt

print("Downloading market data...")
# 1. Fetch Data (auto_adjust=True puts the adjusted close data directly into 'Close')
data = yf.download(['META', 'NFLX'], start='2024-01-01', end='2026-07-10')['Close']

print("Calculating OLS Regression and Z-Score...")
# 2. Run OLS Regression to find the spread
model = sm.OLS(data['META'], sm.add_constant(data['NFLX'])).fit()
spread = data['META'] - model.predict(sm.add_constant(data['NFLX']))

# 3. Calculate Z-Score: Z = (X - μ) / σ
z_score = (spread - spread.mean()) / spread.std()

print("Generating analytical chart...")
# 4. Plotting the architecture
fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(z_score.index, z_score, label='META/NFLX Z-Score', color='royalblue', linewidth=1.5)
ax.axhline(3, color='crimson', linestyle='--', label='Stop-Loss (+3σ)')
ax.axhline(-3, color='crimson', linestyle='--', label='Stop-Loss (-3σ)')
ax.axhline(0, color='black', label='Mean Reversion Line (0)', linewidth=1)

ax.set_title('Statistical Arbitrage: Z-Score Deviation & Risk Thresholds', fontsize=14, fontweight='bold')
ax.set_ylabel('Standard Deviations (σ)', fontsize=12)
ax.legend(loc='upper right')
plt.grid(True, alpha=0.3)

# 5. Save the image
plt.savefig('z_score_chart.png', dpi=300, bbox_inches='tight')
print("SUCCESS: Chart saved to your folder as 'z_score_chart.png'.")
