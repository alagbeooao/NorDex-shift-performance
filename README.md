# NorDex shift performance

- `nordex.sql` (SQL Server): shift, downtime, defect and maintenance queries; OEE with CTEs that deduplicate before aggregating; a consolidated view `v1_ShiftPerformance` joining seven tables.
- `shift_performance_analysis.ipynb`: KPIs by shift, correlations, and linear vs gradient boosting models predicting shift efficiency.
- `app.py`: Streamlit dashboard with shift summary, operator and machine analytics, a single-shift predictor and a scenario explorer.

Findings: night shifts averaged an efficiency score of 61 against 91 for mornings, a 4.5% defect rate against 2.2%, and 68 minutes of downtime against 29. Gradient boosting predicted efficiency with R² 0.95 and MAE 2.4.

The notebook expects `ShiftPerformance.csv`, an export of the view. The data isn't included.
