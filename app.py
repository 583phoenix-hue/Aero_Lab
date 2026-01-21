import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import os
import subprocess
import time
import shutil
import uuid

# --- LINUX GRAPHICS FIX ---
# XFOIL expects a screen; this "fake" screen allows it to run on a server
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":99"

st.set_page_config(page_title="Airfoil CFD Tool", layout="wide", page_icon="✈️")

# --- CORE LOGIC (Moved from main.py) ---

def run_xfoil_linux(fix_path, reynolds, alpha, work_dir):
    """Executes the Linux version of XFOIL via subprocess."""
    polar_path = os.path.join(work_dir, "polar.txt")
    cp_path = os.path.join(work_dir, "cp.txt")
    
    # XFOIL commands for Linux (no .exe suffix)
    commands = f"""
    LOAD {fix_path}
    OPER
    VISC {reynolds}
    PACC
    {polar_path}
    
    ITER 100
    ALFA {alpha}
    CPWR {cp_path}
    
    QUIT
    """
    
    # Run XFOIL using xvfb-run to provide the virtual display
    process = subprocess.Popen(
        ["xvfb-run", "-a", "xfoil"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = process.communicate(input=commands)
    
    # --- PARSING RESULTS ---
    cp_x, cp_values = [], []
    if os.path.exists(cp_path):
        with open(cp_path, "r") as f:
            lines = f.readlines()
            for line in lines[3:]: # Skip headers
                parts = line.split()
                if len(parts) >= 3:
                    cp_x.append(float(parts[0]))
                    cp_values.append(float(parts[1]))
    
    return cp_x, cp_values

# --- STREAMLIT FRONTEND ---

st.title("✈️ Professional Airfoil Analysis")
uploaded_file = st.file_uploader("Upload Airfoil .dat file", type=['dat'])

if uploaded_file:
    # Setup temporary workspace
    job_id = str(uuid.uuid4())
    work_dir = f"temp_{job_id}"
    os.makedirs(work_dir, exist_ok=True)
    
    # Save uploaded file
    input_path = os.path.join(work_dir, "airfoil.dat")
    with open(input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Sidebar parameters
    st.sidebar.header("Simulation Settings")
    re = st.sidebar.number_input("Reynolds Number", value=1000000)
    aoa = st.sidebar.slider("Angle of Attack", -10.0, 20.0, 5.0)

    if st.button("🚀 Run Analysis"):
        with st.spinner("XFOIL is calculating..."):
            cp_x, cp_vals = run_xfoil_linux(input_path, re, aoa, work_dir)
            
            if cp_x:
                st.success("Analysis Complete!")
                # Plotting
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=cp_x, y=cp_vals, name="Pressure Coefficient"))
                fig.update_layout(title="Cp Distribution", xaxis_title="x/c", yaxis_title="-Cp")
                fig.update_yaxes(autorange="reversed") # Standard Aero convention
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("XFOIL failed to converge. Try different parameters.")
    
    # Cleanup
    shutil.rmtree(work_dir, ignore_errors=True)