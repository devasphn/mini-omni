# Mini-Omni Fixes & Troubleshooting

## 🔧 Issues Fixed

This repository includes important fixes for common Mini-Omni deployment issues:

### 1. Tokenizer NotImplementedError Fix

**Issue**: `NotImplementedError` when initializing the tokenizer due to missing tokenizer files.

**Fix**: Enhanced error handling in `litgpt/tokenizer.py` with:
- Better error messages showing available files
- Specific troubleshooting instructions
- Automatic detection of missing tokenizer files

### 2. Enhanced Model Loading

**Improvements**: Added comprehensive debugging and error handling in `inference.py`:
- Step-by-step model loading with progress indicators
- Verification of downloaded files
- Better error messages for troubleshooting
- Enhanced download process with file verification

### 3. Troubleshooting Script

**New**: Added `troubleshoot.py` script to diagnose common issues:
- Python version compatibility check
- Dependencies verification
- GPU/CUDA availability check
- Port availability check
- Checkpoint file verification
- Automatic problem detection and solutions

## 🚀 Quick Start (Fixed Version)

### Step 1: Run Troubleshoot Script

```bash
# Check for common issues
python3 troubleshoot.py
```

### Step 2: Install Dependencies

```bash
# Install requirements
pip install -r requirements.txt

# If you get dependency errors, install individually:
pip install torch lightning snac whisper soundfile tqdm huggingface_hub tokenizers fire
```

### Step 3: Start Server

```bash
# For RunPod deployment
python3 server.py --ip '0.0.0.0' --port 60808
```

## 🔍 Troubleshooting Common Issues

### Issue 1: NotImplementedError in tokenizer.py

**Error**:
```
NotImplementedError
```

**Solution**:
1. Delete the checkpoint directory: `rm -rf ./checkpoint`
2. Re-run the server to download fresh files
3. Check network connectivity to Hugging Face

### Issue 2: Missing Dependencies

**Error**: Various import errors

**Solution**:
```bash
# Run troubleshoot script to identify missing packages
python3 troubleshoot.py

# Install missing packages as recommended
pip install [missing_packages]
```

### Issue 3: CUDA/GPU Issues

**Error**: CUDA-related errors or slow performance

**Solution**:
- The model works on CPU but will be slower
- For GPU acceleration, ensure CUDA is properly installed
- Check with: `python3 -c "import torch; print(torch.cuda.is_available())"`

### Issue 4: Port Already in Use

**Error**: Port binding errors

**Solution**:
```bash
# Use a different port
python3 server.py --ip '0.0.0.0' --port 60809
```

### Issue 5: Download Issues

**Error**: Failed to download model files

**Solution**:
1. Check internet connectivity
2. Clear any partial downloads: `rm -rf ./checkpoint`
3. Try manual download from: https://huggingface.co/gpt-omni/mini-omni
4. Ensure sufficient disk space (>3GB required)

## 📁 File Structure After Fixes

```
mini-omni/
├── inference.py          # Enhanced with better error handling
├── litgpt/
│   └── tokenizer.py      # Fixed NotImplementedError
├── server.py             # Original server code
├── troubleshoot.py       # New troubleshooting script
├── requirements.txt      # Dependencies
└── checkpoint/           # Auto-downloaded model files
    ├── tokenizer.json
    ├── tokenizer_config.json
    ├── model_config.yaml
    └── lit_model.pth
```

## 🌐 RunPod Specific Instructions

### Network Configuration
- Uses HTTP/TCP only (no UDP required)
- Single port configuration (default: 60808)
- Perfect for RunPod's 10-port limit

### Deployment Commands
```bash
# 1. Clone your fixed repository
git clone https://github.com/YOUR_USERNAME/mini-omni.git
cd mini-omni

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run troubleshoot script
python3 troubleshoot.py

# 4. Start server (will auto-download model on first run)
python3 server.py --ip '0.0.0.0' --port 60808
```

### API Testing
```bash
# Test the API endpoint
curl -X POST http://YOUR_RUNPOD_URL:60808/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?"}'
```

## 📊 Performance Expectations

- **Model Size**: ~2.8GB download
- **RAM Usage**: 4-6GB during inference
- **GPU Memory**: 3-4GB (if using GPU)
- **First Response**: 10-30 seconds (model loading)
- **Subsequent Responses**: 1-5 seconds

## 🔧 Advanced Configuration

### Custom Checkpoint Directory
```python
# In your code
from inference import OmniInference

# Use custom checkpoint location
model = OmniInference(ckpt_dir='/path/to/checkpoints', device='cuda:0')
```

### Environment Variables
```bash
# Set custom download cache
export HF_HOME=/path/to/cache

# Disable progress bars for headless deployment
export HF_HUB_DISABLE_PROGRESS_BARS=1
```

## ⚡ Performance Optimizations

1. **GPU Usage**: Ensure CUDA is available for best performance
2. **Memory**: Close unnecessary processes to free RAM
3. **Storage**: Use SSD for faster model loading
4. **Network**: Stable internet for initial model download

## 🆘 Getting Help

If you're still experiencing issues:

1. **Run the troubleshoot script**: `python3 troubleshoot.py`
2. **Check the logs**: Look for specific error messages
3. **Verify file integrity**: Ensure all checkpoint files downloaded completely
4. **Network issues**: Try downloading from a different network
5. **Resource constraints**: Ensure sufficient RAM and disk space

## 📝 License

This project maintains the original MIT License from Mini-Omni, allowing full commercial use and modification.

---

**Note**: These fixes ensure Mini-Omni works reliably in production environments, especially on RunPod and similar cloud platforms with networking restrictions.