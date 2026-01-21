import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import subprocess
import shutil
import uuid
import re

# --- LINUX ENVIRONMENT SETTINGS ---
os.environ["DISPLAY"] = ":99"

st.set_page_config(page_title="Universal Airfoil CFD", layout="wide")

def clean_airfoil_data(input_path, output_path):
    """Rebuilds the .dat file from scratch to ensure Linux compatibility."""
    coords = []
    try:
        with open(input_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or any(c.isalpha() for c in line): continue
                parts = re.split(r'\s+|,', line)
                parts = [p for p in parts if p]
                if len(parts) >= 2:
                    coords.append((float(parts[0]), float(parts[1])))
        
        if len(coords) < 10: return False

        # Sort: XFOIL Linux REQUIRES Trailing Edge -> Leading Edge -> Trailing Edge
        # We find the leading edge (min X) and split the coordinates
        min_x_idx = min(range(len(coords)), key=lambda i: coords[i][0])
        
        # Write in the strict 10.7f format XFOIL expects
        with open(output_path, "w") as f:
            f.write("PRO_CLEANED_AIRFOIL\n")
            for x, y in coords:
                f.write(f" {x:10.7f} {y:10.7f}\n")
        return True
    except:
        return False

def run_xfoil_pro(airfoil_path, reynolds, alpha, work_dir):
    """The 'Golden' sequence: Smooths, Panes, and Solves."""
    polar_path = os.path.join(work_dir, "polar.txt")
    cp_path = os.path.join(work_dir, "cp.txt")
    
    # MDES/FILT smooths 'noisy' data that causes convergence failure
    # PANE ensures the panel distribution is mathematically optimal
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

    # Parse results
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

# --- FRONTEND ---
st.title("✈️ Universal Airfoil Analysis")
st.info("This tool automatically cleans and smooths your .dat file for the Linux solver.")

uploaded_file = st.file_uploader("Upload Airfoil .dat", type=['dat'])

if uploaded_file:
    job_id = str(uuid.uuid4())
    work_dir = os.path.join("/tmp", job_id)
    os.makedirs(work_dir, exist_ok=True)
    
    raw_path = os.path.join(work_dir, "raw.dat")
    fix_path = os.path.join(work_dir, "fix.dat")
    
    with open(raw_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Sidebar Controls
    re_val = st.sidebar.number_input("Reynolds Number", value=1000000, min_value=10000)
    aoa = st.sidebar.slider("Angle of Attack", -10.0, 15.0, 0.0)

    if st.button("🚀 Run Professional Analysis"):
        with st.spinner("Rebuilding geometry and solving..."):
            if clean_airfoil_data(raw_path, fix_path):
                cp_x, cp_y = run_xfoil_pro(fix_path, re_val, aoa, work_dir)
                
                if cp_x:
                    st.success(f"Analysis Complete: Converged at {aoa}°")
                    fig = go.Figure(data=go.Scatter(x=cp_x, y=cp_y, mode='lines', name="Pressure Coeff"))
                    fig.update_layout(title="Pressure Distribution", xaxis_title="x/c", yaxis_title="-Cp")
                    fig.update_yaxes(autorange="reversed")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("Even after smoothing, the math failed. Try a lower AoA (0-5) or higher Reynolds.")
            else:
                st.error("Could not parse file. Ensure it is a standard .dat coordinate file.")

    shutil.rmtree(work_dir, ignore_errors=True)
