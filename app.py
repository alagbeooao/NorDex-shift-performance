import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
import random

# ---------------------------------------------------------------------
# Streamlit Page Settings
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="NorDex Shift Performance & Optimization Dashboard",
    layout="wide"
)

# ---------------------------------------------------------------------
# Helper for Consistent Figure Sizing
# ---------------------------------------------------------------------
def make_fig():
    return plt.subplots(figsize=(6, 3))  # universal sizing for dashboard readability

# ---------------------------------------------------------------------
# 1. DATA LOADING
# ---------------------------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("ShiftPerformance.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df

@st.cache_data
def compute_oee_from_view(df):
    PLANNED_H = 7.5
    THEO_RATE = 100.0

    prod = (
        df[['production_id','shift_id','shift_name','date',
            'units_produced','defect_count','shift_efficiency_score']]
        .drop_duplicates(subset=['production_id'])
        .copy()
    )

    mach = (
        df[['machine_id','shift_id','date','downtime_minutes']]
        .drop_duplicates()
        .copy()
    )

    mach["avail_machine"] = 1 - (mach["downtime_minutes"] / (PLANNED_H*60))
    mach["avail_machine"] = mach["avail_machine"].clip(0,1)

    avail_agg = (
        mach.groupby(["date","shift_id"])["avail_machine"]
            .mean()
            .reset_index()
            .rename(columns={"avail_machine":"availability"})
    )

    merged = prod.merge(avail_agg, on=["date","shift_id"], how="left")
    merged["availability"] = merged["availability"].fillna(1)

    merged["performance"] = (merged["units_produced"] / (THEO_RATE * PLANNED_H)).clip(0,1)
    merged["quality"] = 1 - merged["defect_count"] / merged["units_produced"]
    merged["quality"] = merged["quality"].fillna(1).clip(0,1)

    merged["OEE"] = merged["availability"] * merged["performance"] * merged["quality"]
    merged["month"] = merged["date"].dt.month

    return merged, mach


# ---------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------
df = load_data()
oee_df, mach_df = compute_oee_from_view(df)

st.title("🏭 NorDex Manufacturing – Shift Performance & Optimization Dashboard")

# ---------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "Shift Performance Summary",
    "Operator & Machine Analytics",
    "Predictive Insights & Optimization"
])

# ---------------------------------------------------------------------
# TAB 1: SHIFT PERFORMANCE SUMMARY
# ---------------------------------------------------------------------
with tab1:
    st.header("📊 Shift Performance Summary")

    prod_view = oee_df.copy()

    # KPIs
    kpi1 = prod_view['units_produced'].mean()
    kpi2 = prod_view['defect_count'].mean()
    kpi3 = mach_df['downtime_minutes'].mean()
    kpi4 = prod_view['OEE'].mean() * 100
    kpi5 = prod_view['shift_efficiency_score'].mean()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Units per Record", f"{kpi1:.1f}")
    col2.metric("Defects per Record", f"{kpi2:.2f}")
    col3.metric("Downtime (min)", f"{kpi3:.1f}")
    col4.metric("OEE (%)", f"{kpi4:.1f}")
    col5.metric("Shift Efficiency Score", f"{kpi5:.1f}")

    st.markdown("---")

    # Shift comparison
    st.subheader("Shift Output & Efficiency Comparison")

    shift_summary = (
        prod_view.groupby("shift_name")
                 .agg(
                     avg_units=('units_produced', 'mean'),
                     avg_eff=('shift_efficiency_score', 'mean')
                 )
                 .reset_index()
    )

    colA, colB = st.columns(2)

    with colA:
        fig, ax = make_fig()
        sns.barplot(data=shift_summary, x='shift_name', y='avg_units', ax=ax)
        ax.set_title("Average Units Produced per Shift")
        st.pyplot(fig)

    with colB:
        fig, ax = make_fig()
        sns.barplot(data=shift_summary, x='shift_name', y='avg_eff', ax=ax)
        ax.set_title("Average Shift Efficiency Score")
        st.pyplot(fig)

    st.markdown("---")

    # Monthly OEE
    st.subheader("📈 Monthly OEE Trend")

    monthly_oee = (
        prod_view.groupby("month")["OEE"]
                 .mean()
                 .mul(100)
                 .reset_index()
    )

    fig, ax = make_fig()
    sns.lineplot(data=monthly_oee, x='month', y='OEE', marker="o", ax=ax)
    ax.set_ylim(60, 80)
    st.pyplot(fig)

    # Monthly Efficiency
    st.subheader("📈 Monthly Shift Efficiency Score")

    monthly_eff = (
        prod_view.groupby("month")["shift_efficiency_score"]
                 .mean()
                 .reset_index()
    )

    fig, ax = make_fig()
    sns.lineplot(data=monthly_eff, x='month', y='shift_efficiency_score', marker="o", ax=ax)
    st.pyplot(fig)

# ---------------------------------------------------------------------
# TAB 2: OPERATOR & MACHINE ANALYTICS
# ---------------------------------------------------------------------
with tab2:
    st.header("👷 Operator & Machine Analytics")

    op_view = df[['operator_id','operator_name','experience_level','skill_category']].drop_duplicates()

    st.subheader("Operator Skill Mix")
    skill_counts = op_view['skill_category'].value_counts().reset_index()
    skill_counts.columns = ['skill_category', 'count']

    fig, ax = make_fig()
    sns.barplot(data=skill_counts, x='skill_category', y='count', ax=ax)
    st.pyplot(fig)

    st.subheader("Experience vs Defects")
    prod_op = df[['production_id','experience_level','defect_count']].drop_duplicates(subset=['production_id'])

    fig, ax = make_fig()
    sns.boxplot(data=prod_op, x='experience_level', y='defect_count', ax=ax)
    st.pyplot(fig)

    st.subheader("Top Machines by Downtime")
    downtime_per_machine = (
        mach_df.groupby("machine_id")["downtime_minutes"]
               .sum()
               .sort_values(ascending=False)
               .head(20)
    )
    st.bar_chart(downtime_per_machine)

    st.subheader("Maintenance Events per Machine")
    maint_counts = (
        df[['machine_id','maintenance_id']]
        .drop_duplicates()
        .assign(maint_flag=lambda x: np.where(x['maintenance_id'].notna(), 1, 0))
        .groupby("machine_id")['maint_flag']
        .sum()
        .sort_values(ascending=False)
        .head(20)
    )
    st.bar_chart(maint_counts)

# ---------------------------------------------------------------------
# TAB 3: PREDICTIVE INSIGHTS & OPTIMIZATION
# ---------------------------------------------------------------------
with tab3:
    st.header("🤖 Predictive Insights & Shift Optimization")

    st.subheader("Load Trained Model")

    try:
        model = joblib.load("best_model.pkl")  # MUST be a fitted Pipeline
        st.success("Model loaded successfully.")
    except:
        st.error("Model not found. Ensure best_model.pkl exists.")
        model = None

    # ---------------- Single Prediction ----------------
    st.subheader("Simulate a Shift Configuration")

    shift_choice = st.selectbox("Shift", ["Morning", "Evening", "Night"])

    colL, colR = st.columns(2)
    with colL:
        exp_level = st.slider("Experience Level", 1, 15, 6)
        runtime = st.number_input("Runtime Hours", 0.0, 7.5, 6.0)
        downtime = st.number_input("Downtime Minutes", 0.0, 180.0, 30.0)
        maint_flag = st.selectbox("Maintenance Flag", [0, 1])
        skill_cat = st.selectbox('Operator Skill Category', ['Expert', 'Senior', 'Intermediate', 'Junior'])

    with colR:
        units = st.number_input("Units Produced", 0, 2000, 800)
        defects = st.number_input("Defect Count", 0, 200, 20)
        temp = st.number_input("Temperature (°C)", 15.0, 35.0, 22.0)
        humidity = st.number_input("Humidity (%)", 20.0, 80.0, 50.0)

    cycle_time = runtime * 60 / units if units > 0 else 0

    if model:
        input_df = pd.DataFrame([{
            "experience_level": exp_level,
            "runtime_hours": runtime,
            "downtime_minutes": downtime,
            "maintenance_flag": maint_flag,
            "units_produced": units,
            "defect_count": defects,
            "cycle_time_avg": cycle_time,
            "temperature": temp,
            "humidity": humidity,
            "shift_name": shift_choice,
            'skill_category': skill_cat
        }])

        if st.button("Predict Efficiency Score"):
            pred = model.predict(input_df)[0]
            st.metric("Predicted Shift Efficiency Score", f"{pred:.2f}")

    st.markdown("---")

    # ---------------- Optimization ----------------
    st.subheader("Optimization Explorer")

    if model:
        exp_min, exp_max = st.slider("Experience Range", 1, 15, (5, 10))
        dt_min, dt_max = st.slider("Downtime Range", 0, 120, (10, 60))
        def_min, def_max = st.slider("Defect Range", 0, 100, (5, 30))

        if st.button("Run Optimization Search"):
            exp_vals = np.linspace(exp_min, exp_max, 3, dtype=int)
            dt_vals = np.linspace(dt_min, dt_max, 3, dtype=int)
            def_vals = np.linspace(def_min, def_max, 3, dtype=int)

            # Define possible shift and skill categories
            shift_choices = ["Morning", "Evening", "Night"]
            skill_choices = ["Expert", "Senior", "Intermediate", "Junior"]

            # Randomize shift_name, skill_category, and units_produced in each scenario
            scenarios = []
            for e in exp_vals:
                for dtime in dt_vals:
                    for d in def_vals:
                        shift_random = random.choice(shift_choices)  # Randomly select shift
                        skill_random = random.choice(skill_choices)  # Randomly select skill category
                        units_random = random.randint(750, 900)  # Random units produced between 750 and 900

                        scenarios.append({
                            "experience_level": e,
                            "runtime_hours": 6.0,  # You can adjust this as needed
                            "downtime_minutes": dtime,
                            "maintenance_flag": 0,  # Assuming no maintenance for now
                            "units_produced": units_random,
                            "defect_count": d,
                            "cycle_time_avg": 6.0 * 60 / units_random,  # Cycle time calculation
                            "temperature": 22.0,  # You can adjust or randomize this too
                            "humidity": 50.0,  # You can adjust or randomize this too
                            "shift_name": shift_random,
                            'skill_category': skill_random
                        })

            # Convert to DataFrame
            scenario_df = pd.DataFrame(scenarios)

            # Predict efficiency scores for all the scenarios
            scenario_df["pred_efficiency"] = model.predict(scenario_df)

            # Show top 10 optimized configurations based on predicted efficiency
            top10 = scenario_df.sort_values("pred_efficiency", ascending=False).head(10)
            st.write("### Top 10 Recommended Configurations")
            st.dataframe(top10)

    else:
        st.info("Load a trained model to enable optimization.")
