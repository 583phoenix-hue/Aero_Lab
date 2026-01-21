import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import os
import subprocess
import shutil
import uuid
import re

# --- LINUX SERVER CONFIG ---
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":99"

st.set_page_config(page_title="Airfoil CFD Tool", layout="wide", page_icon="✈️")

def parse_dat_file(filepath):
    coords = []
    with open(filepath, 'r') as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line or any(c.isalpha() for c in line): continue
            parts = re.split(r'\s+|,', line)
            parts = [p for p in parts if p]
            if len(parts) >= 2:
                try:
                    coords.append((float(parts[0]), float(parts[1])))
                except ValueError: continue
    
    # --- NEW: GEOMETRY AUTO-FIXER ---
    # XFOIL fails if points aren't sorted from trailing edge -> leading edge -> trailing edge
    if len(coords) > 0 and coords[0][0] < coords[-1][0]:
        coords.reverse() 
    return coords

def run_xfoil_linux(fix_path, reynolds, alpha, work_dir):
    polar_path = os.path.join(work_dir, "polar.txt")
    cp_path = os.path.join(work_dir, "cp.txt")
    
    # --- NEW: AGGRESSIVE COMMAND SEQUENCE ---
    # Added 'MDES' -> 'FILT' to smooth out any "bumps" in your .dat file
    # Increased ITER to 500 for maximum attempt time
    commands = f"""
    LOAD {fix_path}
    MDES
    FILT
    EXEC
    PANE
    OPER
    ITER 500
    VISC {reynolds}
    INIT
    PACC
    {polar_path}
    
    ALFA {alpha}
    CPWR {cp_path}
    
    QUIT
    """
    
    process = subprocess.Popen(
        ["xvfb-run", "-a", "xfoil"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    process.communicate(input=commands)
    
    cp_x, cp_vals = [], []
    if os.path.exists(cp_path):
        with open(cp_path, "r") as f:
            lines = f.readlines()
            for line in lines[3:]:
                p = line.split()
                if len(p) >= 3:
                    cp_x.append(float(p[0]))
                    cp_vals.append(float(p[1]))
    return cp_x, cp_vals

# --- FRONTEND (Identical to your original) ---

st.title("✈️ Professional Airfoil Analysis")
st.markdown("If convergence fails, try clicking **'Run Analysis'** a second time or lower the **Angle of Attack**.")

uploaded_file = st.file_uploader("Upload Airfoil .dat file", type=['dat'])

if uploaded_file:
    job_id = str(uuid.uuid4())
    work_dir = f"temp_{job_id}"
    os.makedirs(work_dir, exist_ok=True)
    
    input_path = os.path.join(work_dir, "airfoil.dat")
    fix_path = os.path.join(work_dir, "fix.dat")
    with open(input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.sidebar.header("Simulation Settings")
    re_val = st.sidebar.number_input("Reynolds Number", value=1000000, min_value=10000)
    aoa = st.sidebar.slider("Angle of Attack (Degrees)", -10.0, 15.0, 5.0)

    if st.button("🚀 Run Analysis"):
        with st.spinner("Smoothing geometry and solving..."):
            raw_coords = parse_dat_file(input_path)
            
            if not raw_coords:
                st.error("Could not read coordinates. Check your .dat file format.")
            else:
                with open(fix_path, "w") as f:
                    f.write("AIRFOIL\n")
                    for x, y in raw_coords:
                        f.write(f"  {x:.6f}  {y:.6f}\n")
                
                cp_x, cp_vals = run_xfoil_linux(fix_path, re_val, aoa, work_dir)
                
                if cp_x:
                    st.success(f"Analysis Complete at α={aoa}°")
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=cp_x, y=cp_vals, mode='lines', line=dict(color='blue')))
                    fig.update_layout(title="Pressure Distribution", xaxis_title="x/c", yaxis_title="-Cp")
                    fig.update_yaxes(autorange="reversed")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("Convergence failed. This usually happens if the Angle of Attack is too high for this specific airfoil shape.")
    
    shutil.rmtree(work_dir, ignore_errors=True)
