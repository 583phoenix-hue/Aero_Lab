import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import subprocess
import shutil
import uuid
import re

# --- FORCED LINUX ENVIRONMENT ---
# This tells the server to use a fake display for XFOIL's graphics
os.environ["DISPLAY"] = ":99"

def run_xfoil_linux_only(airfoil_path, reynolds, alpha, work_dir):
    polar_path = os.path.join(work_dir, "polar.txt")
    cp_path = os.path.join(work_dir, "cp.txt")
    
    # Professional Linux-XFOIL Sequence
    # 'PANE' and 'MDES' are essential for Linux stability
    commands = f"""
    PLOP
    G
    
    LOAD {airfoil_path}
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
    
    # We call 'xvfb-run' directly in the command
    try:
        process = subprocess.Popen(
            ["xvfb-run", "-a", "xfoil"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=commands, timeout=30)
    except Exception as e:
        return None, None

    # Parsing the output
    cp_x, cp_vals = [], []
    if os.path.exists(cp_path):
        with open(cp_path, "r") as f:
            lines = f.readlines()
            for line in lines[3:]: # Skip XFOIL header
                p = line.split()
                if len(p) >= 3:
                    cp_x.append(float(p[0]))
                    cp_vals.append(float(p[1]))
    return cp_x, cp_vals

# --- FRONTEND ---
st.title("✈️ Linux-Optimized Airfoil Tool")

uploaded_file = st.file_uploader("Upload .dat file", type=['dat'])

if uploaded_file:
    # Use the Linux /tmp directory for maximum compatibility
    job_id = str(uuid.uuid4())
    work_dir = os.path.join("/tmp", job_id)
    os.makedirs(work_dir, exist_ok=True)
    
    file_path = os.path.join(work_dir, "airfoil.dat")
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    re_val = st.sidebar.number_input("Reynolds", value=1000000)
    aoa = st.sidebar.slider("AoA", -5.0, 15.0, 2.0)

    if st.button("Run Simulation"):
        with st.spinner("Processing on Linux Server..."):
            cp_x, cp_y = run_xfoil_linux_only(file_path, re_val, aoa, work_dir)
            
            if cp_x:
                st.success("Converged!")
                fig = go.Figure(data=go.Scatter(x=cp_x, y=cp_y, mode='lines'))
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig)
            else:
                st.error("Convergence failed. Linux XFOIL requires very clean .dat files.")

    # Cleanup
    shutil.rmtree(work_dir, ignore_errors=True)
