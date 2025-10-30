#!/usr/bin/env python3
"""
Mini-Omni Troubleshooting Script

This script helps diagnose and fix common issues with Mini-Omni setup.
Run this before starting the server if you encounter problems.
"""

import os
import sys
from pathlib import Path
import shutil

def check_python_version():
    """Check if Python version is compatible."""
    print("\n=== Python Version Check ===")
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major != 3 or version.minor < 8:
        print("✗ ERROR: Python 3.8+ required")
        return False
    else:
        print("✓ Python version is compatible")
        return True

def check_dependencies():
    """Check if all required dependencies are installed."""
    print("\n=== Dependencies Check ===")
    
    required_packages = [
        'torch',
        'lightning', 
        'snac',
        'whisper',
        'soundfile',
        'tqdm',
        'huggingface_hub',
        'tokenizers',
        'fire'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} - MISSING")
            missing.append(package)
    
    if missing:
        print(f"\nMissing packages: {missing}")
        print("Install with: pip install " + " ".join(missing))
        return False
    return True

def check_checkpoint_directory():
    """Check checkpoint directory and files."""
    print("\n=== Checkpoint Directory Check ===")
    
    ckpt_dir = "./checkpoint"
    ckpt_path = Path(ckpt_dir)
    
    if not ckpt_path.exists():
        print(f"✗ Checkpoint directory {ckpt_dir} does not exist")
        print("This is normal for first run - it will be downloaded automatically")
        return True
    
    print(f"✓ Checkpoint directory exists: {ckpt_dir}")
    
    # Check critical files
    critical_files = [
        "tokenizer.json",
        "tokenizer_config.json",
        "model_config.yaml", 
        "lit_model.pth"
    ]
    
    all_files = list(ckpt_path.glob("*"))
    print(f"Files in directory: {[f.name for f in all_files]}")
    
    missing_files = []
    for file in critical_files:
        file_path = ckpt_path / file
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"✓ {file} ({size:,} bytes)")
        else:
            print(f"✗ {file} - MISSING")
            missing_files.append(file)
    
    if missing_files:
        print(f"\nMissing critical files: {missing_files}")
        print("Run: rm -rf ./checkpoint && python3 server.py --ip '0.0.0.0' --port 60808")
        return False
    
    return True

def check_gpu_availability():
    """Check GPU availability and CUDA."""
    print("\n=== GPU/CUDA Check ===")
    
    try:
        import torch
        
        if torch.cuda.is_available():
            print(f"✓ CUDA available: {torch.cuda.get_device_name(0)}")
            print(f"✓ CUDA version: {torch.version.cuda}")
            print(f"✓ GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
            return True
        else:
            print("✗ CUDA not available - will use CPU (slower)")
            return False
            
    except Exception as e:
        print(f"✗ Error checking GPU: {e}")
        return False

def check_port_availability():
    """Check if the default port is available."""
    print("\n=== Port Availability Check ===")
    
    import socket
    
    port = 60808
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    
    try:
        result = sock.connect_ex(('0.0.0.0', port))
        if result == 0:
            print(f"✗ Port {port} is already in use")
            sock.close()
            return False
        else:
            print(f"✓ Port {port} is available")
            sock.close() 
            return True
    except Exception as e:
        print(f"✗ Error checking port: {e}")
        sock.close()
        return False

def fix_checkpoint_issues():
    """Attempt to fix checkpoint issues."""
    print("\n=== Fixing Checkpoint Issues ===")
    
    ckpt_dir = "./checkpoint"
    
    if Path(ckpt_dir).exists():
        print(f"Removing corrupted checkpoint directory: {ckpt_dir}")
        shutil.rmtree(ckpt_dir)
        print("✓ Checkpoint directory removed")
    
    print("Checkpoint will be re-downloaded on next run")
    return True

def check_sample_files():
    """Check if sample audio files exist."""
    print("\n=== Sample Files Check ===")
    
    sample_dir = "./data/samples"
    sample_path = Path(sample_dir)
    
    if not sample_path.exists():
        print(f"✗ Sample directory {sample_dir} does not exist")
        return False
        
    audio_files = list(sample_path.glob("*.wav"))
    if audio_files:
        print(f"✓ Found {len(audio_files)} sample audio files")
        return True
    else:
        print(f"✗ No audio files found in {sample_dir}")
        return False

def run_basic_test():
    """Run a basic import test."""
    print("\n=== Basic Import Test ===")
    
    try:
        print("Testing imports...")
        from inference import OmniInference
        print("✓ Core imports successful")
        
        # Test tokenizer specifically
        from litgpt import Tokenizer
        print("✓ Tokenizer import successful")
        
        return True
        
    except Exception as e:
        print(f"✗ Import test failed: {e}")
        return False

def main():
    """Main troubleshooting function."""
    print("Mini-Omni Troubleshooting Script")
    print("=" * 50)
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies), 
        ("GPU/CUDA", check_gpu_availability),
        ("Port Availability", check_port_availability),
        ("Checkpoint Directory", check_checkpoint_directory),
        ("Sample Files", check_sample_files),
        ("Basic Imports", run_basic_test)
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"✗ {name} check failed with error: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    passed = sum(results.values())
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name}: {status}")
    
    print(f"\nOverall: {passed}/{total} checks passed")
    
    # Recommendations
    if not all(results.values()):
        print("\n" + "=" * 50)
        print("RECOMMENDATIONS")
        print("=" * 50)
        
        if not results.get("Dependencies", True):
            print("1. Install missing dependencies:")
            print("   pip install -r requirements.txt")
        
        if not results.get("Checkpoint Directory", True):
            print("2. Fix checkpoint issues:")
            print("   rm -rf ./checkpoint")
            print("   python3 server.py --ip '0.0.0.0' --port 60808")
        
        if not results.get("GPU/CUDA", True):
            print("3. GPU not available - model will run slower on CPU")
            print("   Consider using a GPU-enabled environment")
        
        if not results.get("Port Availability", True):
            print("4. Port in use - try a different port:")
            print("   python3 server.py --ip '0.0.0.0' --port 60809")
        
        if not results.get("Sample Files", True):
            print("5. No sample files - server will still work for API calls")
            print("   Add .wav files to ./data/samples/ for testing")
    else:
        print("\n✓ All checks passed! You should be able to run:")
        print("   python3 server.py --ip '0.0.0.0' --port 60808")
    
    return all(results.values())

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)