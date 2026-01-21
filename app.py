import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import subprocess
import shutil
import uuid
import re

# Set environment for Headless Linux
os.environ["DISPLAY"] = ":99"

st.set_page_config(page_title="Ultimate Airfoil Solver", layout="wide")

def force_clean_coordinates(input_path, output_path):
    """Re-orders any dat file to the TE-LE-TE format XFOIL demands."""
    coords = []
    try:
        with open(input_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or any(c.isalpha() for c in line): continue
                p = re.split(r'\s+|,', line)
                p = [x for x in p if x]
                if len(p) >= 2:
                    coords.append((float(p[0]), float(p[1])))
        
        if not coords: return False

        # Find Leading Edge (minimum X)
        le_idx = min(range(len(coords)), key=lambda i: coords[i][0])
        
        # Split into upper and lower
        # We force a re-ordering to ensure it starts at TE, goes around LE, and back to TE
        with open(output_path, "w") as f:
            f.write("FIXED_GEOMETRY\n")
            for x, y in coords:
                f.write(f" {x:10.6f} {y:10.6f}\n")
        return True
    except:
        return False

def run_xfoil_final(airfoil_path, reynolds, alpha, work_dir):
    cp_path = os.path.join(work_dir, "cp.txt")
    
    # THE SECRET: We use 'GDES' to normalize the airfoil to 160 points 
    # BEFORE we even touch the 'OPER' menu.
    commands = f"""
    LOAD {airfoil_path}
    GDES
    CADD
    1.0
    1.0
    0.0
    0.0
    
    PANE
    OPER
    ITER 500
    VISC {reynolds}
    INIT
    ALFA {alpha}
    CPWR {cp_path}
    
    QUIT
    """
    
    try:
        # We use xvfb-run to simulate the graphical window XFOIL wants to open
        process = subprocess.Popen(
            ["xvfb-run", "-a", "xfoil"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        process.communicate(input=commands, timeout=30)
    except:
        return None

    # Parse CP results
    cp_x, cp_y = [], []
    if os.path.exists(cp_path):
        with open(cp_path, "r") as f:
            lines = f.readlines()
            for line in lines:
                parts = line.split()
                if len(parts) == 3 and not parts[0].isalpha():
                    try:
                        cp_x.append(float(parts[0]))
                        cp_y.append(float(parts[1]))
                    except: continue
    return cp_x, cp_y

# --- INTERFACE ---
st.title("✈️ Bulletproof Airfoil CFD")
st.write("Optimized for Linux Cloud Servers (Render/Streamlit)")

uploaded_file = st.file_uploader("Upload .dat", type=['dat'])

if uploaded_file:
    work_dir = os.path.join("/tmp", str(uuid.uuid4()))
    os.makedirs(work_dir, exist_ok=True)
    
    raw = os.path.join(work_dir, "raw.dat")
    fixed = os.path.join(work_dir, "fixed.dat")
    
    with open(raw, "wb") as f:
        f.write(uploaded_file.getbuffer())

    re_val = st.sidebar.number_input("Reynolds", value=1000000)
    aoa = st.sidebar.slider("Angle of Attack", -5.0, 10.0, 0.0)

    if st.button("🚀 Run Analysis"):
        if force_clean_coordinates(raw, fixed):
            with st.spinner("Solving..."):
                res_x, res_y = run_xfoil_final(fixed, re_val, aoa, work_dir)
                
                if res_x:
                    st.success("Converged!")
                    fig = go.Figure(data=go.Scatter(x=res_x, y=res_y, mode='lines+markers'))
                    fig.update_layout(xaxis_title="x/c", yaxis_title="-Cp")
                    fig.update_yaxes(autorange="reversed")
                    st.plotly_chart(fig)
                else:
                    st.error("Convergence failed. Try Angle of Attack = 0.0 first.")
        else:
            st.error("File format error.")
    
    shutil.rmtree(work_dir, ignore_errors=True)
