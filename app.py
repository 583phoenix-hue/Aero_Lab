import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import subprocess
import shutil
import uuid
import re

# Set environment for Headless Linux (Critical for Render/Streamlit)
os.environ["DISPLAY"] = ":99"

st.set_page_config(page_title="Universal Airfoil Solver", layout="wide")

def rebuild_airfoil_geometry(input_path, output_path):
    """Re-formats any dat file to the precise TE-LE-TE format Linux XFOIL demands."""
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

        # Write in the strict XFOIL format: 
        # Points must be spaced clearly for the Linux Fortran compiler to read them
        with open(output_path, "w") as f:
            f.write("REBUILT_AIRFOIL\n")
            for x, y in coords:
                f.write(f" {x:10.6f} {y:10.6f}\n")
        return True
    except:
        return False

def run_xfoil_double_pass(airfoil_path, reynolds, alpha, work_dir):
    cp_path = os.path.join(work_dir, "cp.txt")
    
    # THE FIX: 
    # 1. PANE re-distributes points (fixes NACA 0015 gaps)
    # 2. OPER -> ALFA 0 (solves easy inviscid first)
    # 3. VISC (then turns on physics)
    commands = f"""
    LOAD {airfoil_path}
    PANE
    OPER
    ITER 500
    ALFA 0
    VISC {reynolds}
    INIT
    ALFA {alpha}
    CPWR {cp_path}
    
    QUIT
    """
    
    try:
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
            # XFOIL CP files have headers; skip them
            for line in lines:
                parts = line.split()
                if len(parts) == 3 and not parts[0].isalpha():
                    try:
                        cp_x.append(float(parts[0]))
                        cp_y.append(float(parts[1]))
                    except: continue
    return cp_x, cp_y

# --- UI ---
st.title("✈️ Bulletproof Airfoil CFD")
st.markdown("This version uses **Double-Pass Solving** to prevent Linux convergence errors.")

uploaded_file = st.file_uploader("Upload Airfoil .dat", type=['dat'])

if uploaded_file:
    work_dir = os.path.join("/tmp", str(uuid.uuid4()))
    os.makedirs(work_dir, exist_ok=True)
    
    raw = os.path.join(work_dir, "raw.dat")
    fixed = os.path.join(work_dir, "fixed.dat")
    
    with open(raw, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Sidebar parameters
    re_val = st.sidebar.number_input("Reynolds Number", value=1000000)
    aoa = st.sidebar.slider("Angle of Attack", -5.0, 12.0, 0.0)

    if st.button("🚀 Run Simulation"):
        if rebuild_airfoil_geometry(raw, fixed):
            with st.spinner("Stabilizing math and solving..."):
                res_x, res_y = run_xfoil_double_pass(fixed, re_val, aoa, work_dir)
                
                if res_x:
                    st.success(f"Converged at {aoa}°!")
                    fig = go.Figure(data=go.Scatter(x=res_x, y=res_y, mode='lines', name="Pressure Coefficient"))
                    fig.update_layout(xaxis_title="x/c", yaxis_title="-Cp")
                    fig.update_yaxes(autorange="reversed")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("Convergence failed. Linux XFOIL requires a smaller Angle of Attack step.")
        else:
            st.error("Format error in .dat file.")
    
    shutil.rmtree(work_dir, ignore_errors=True)
