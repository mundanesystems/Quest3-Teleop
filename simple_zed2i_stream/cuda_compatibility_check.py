import os
import sys

print("🔍 ZED SDK CUDA Compatibility Checker")
print("=" * 50)

# Check what CUDA libraries the ZED DLL depends on
print("\n1. Checking ZED DLL dependencies...")

# Try to get detailed error information
print("\n2. Testing import with detailed error tracking...")
try:
    # Add both CUDA paths to help with discovery
    old_path = os.environ.get('PATH', '')
    os.environ['PATH'] = (
        r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin;'
        r'C:\Program Files (x86)\ZED SDK\bin;'
        r'C:\Program Files (x86)\ZED SDK\dependencies\opencv_3.1.0\x64;'
        + old_path
    )
    
    # Try the import with more verbose error reporting
    import pyzed.sl as sl
    print("✅ SUCCESS! ZED SDK imported successfully!")
    
except ImportError as e:
    error_msg = str(e)
    print(f"❌ Import failed: {error_msg}")
    
    # Check if it mentions specific CUDA version requirements
    if "cuda" in error_msg.lower():
        print("   🔍 CUDA-related error detected")
    if "12" in error_msg:
        print("   🎯 Likely needs CUDA 12.x")
    if "11" in error_msg:
        print("   🎯 Likely needs CUDA 11.x")

# Check the ZED SDK release notes or version info
print("\n3. Checking ZED SDK version info...")
version_files = [
    r"C:\Program Files (x86)\ZED SDK\doc\API\index.html",
    r"C:\Program Files (x86)\ZED SDK\doc\release_notes.txt",
    r"C:\Program Files (x86)\ZED SDK\README.txt"
]

for file_path in version_files:
    if os.path.exists(file_path):
        print(f"✅ Found: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()[:2000]  # First 2000 chars
                if 'cuda' in content.lower() or 'CUDA' in content:
                    print("   📄 Contains CUDA information")
                    # Look for version numbers
                    import re
                    cuda_versions = re.findall(r'CUDA\s*(?:version\s*)?(\d+\.?\d*)', content, re.IGNORECASE)
                    if cuda_versions:
                        print(f"   🎯 Found CUDA versions mentioned: {cuda_versions}")
        except Exception as e:
            print(f"   ❌ Error reading file: {e}")
    else:
        print(f"❌ Not found: {file_path}")

print("\n" + "=" * 50)
print("CUDA compatibility check complete!")

# Provide recommendation
print("\n💡 RECOMMENDATION:")
print("Based on ZED SDK 5.0, you likely need CUDA 12.x")
print("Options:")
print("1. Install CUDA 12.6 (latest 12.x) alongside CUDA 13.0")
print("2. Use the working OpenCV fallback (already successful)")
print("3. Wait for ZED SDK 6.0 with CUDA 13.x support")
