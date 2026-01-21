import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import subprocess
import shutil
import uuid
import re

# --- FORCED LINUX ENVIRONMENT ---
os.environ["DISPLAY"] = ":99"

st.set_page_config(page_title="Airfoil CFD Tool", layout="wide")

def robust_parse_and_fix(input_path, output_path):
    """
    Cleans the airfoil data to be Linux-XFOIL compatible.
    Ensures TE -> LE -> TE ordering and removes mathematical noise.
    """
    coords = []
    with open(input_path, 'r') as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip()
            # Skip header or empty lines
            if not line or any(c.isalpha() for c in line): continue
            parts = re.split(r'\s+|,', line)
            parts = [p for p in parts if p]
            if len(parts) >= 2:
                try:
                    coords.append((float(parts[0]), float(parts[1])))
                except ValueError: continue

    if len(coords) < 10:
        return False

    # 1. Sort points: XFOIL requires Trailing Edge (1.0) -> Leading Edge (0.0) -> Trailing Edge (1.0)
    # If the file starts at 0.0, it's backwards for Linux XFOIL.
    if coords[0][0] < coords[-1][0]:
        coords.reverse()

    # 2. Save in a strict format Linux XFOIL loves
    with open(output_path, "w") as f:
        f.write("CLEANED_AIRFOIL\n")
        for x, y in coords:
            f.write(f" {x:10.7f} {y:10.7f}\n")
    return True

def run_xfoil_linux_only(airfoil_path, reynolds, alpha, work_dir):
    polar_path = os.path.join(work_dir, "polar.txt")
    cp_path = os.path.join(work_dir, "cp.txt")
    
    # The 'MDES' -> 'FILT' -> 'EXEC' sequence is like 'Photoshop' for airfoils.
    # It smooths out tiny bumps that cause convergence crashes.
    commands = f"""
    LOAD {airfoil_path}
    MDES
    FILT
    EXEC
    PANE
    OPER
    VISC {reynolds}
    ITER 500
    INIT
    PACC
    {polar_path}
    
    ALFA {alpha}
    CPWR {cp_path}
    
    QUIT
    """
    
    try:
        process = subprocess.Popen(
            ["xvfb-run", "-a", "xfoil"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        process.communicate(input=commands, timeout=40)
    except:
        return None, None

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

# --- UI ---
st.title("✈️ Professional Linux CFD Tool")

uploaded_file = st.file_uploader("Upload Airfoil (.dat)", type=['dat'])

if uploaded_file:
    job_id = str(uuid.uuid4())
    work_dir = os.path.join("/tmp", job_id)
    os.makedirs(work_dir, exist_ok=True)
    
    raw_path = os.path.join(work_dir, "raw.dat")
    fix_path = os.path.join(work_dir, "fix.dat")
    
    with open(raw_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Parameters
    re_val = st.sidebar.number_input("Reynolds Number", value=1000000, step=100000)
    aoa = st.sidebar.slider("Angle of Attack", -5.0, 15.0, 0.0)

    if st.button("🚀 Execute Analysis"):
        with st.spinner("Smoothing geometry and solving..."):
            if robust_parse_and_fix(raw_path, fix_path):
                cp_x, cp_y = run_xfoil_linux_only(fix_path, re_val, aoa, work_dir)
                
                if cp_x:
                    st.success("Converged successfully!")
                    fig = go.Figure(data=go.Scatter(x=cp_x, y=cp_y, mode='lines+markers'))
                    fig.update_layout(title=f"Pressure Distribution (α={aoa})", xaxis_title="x/c", yaxis_title="-Cp")
                    fig.update_yaxes(autorange="reversed")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("XFOIL math failed. Try a lower Angle of Attack (e.g., 0 or 2).")
            else:
                st.error("Invalid .dat file format.")

    shutil.rmtree(work_dir, ignore_errors=True)
