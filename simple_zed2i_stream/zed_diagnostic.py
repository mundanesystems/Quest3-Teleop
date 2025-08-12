import os
import sys

print("🔍 ZED SDK Diagnostic Tool")
print("=" * 50)

# Check if pyzed is installed
print("\n1. Checking if pyzed is installed...")
try:
    import pkg_resources
    pyzed_package = None
    for package in pkg_resources.working_set:
        if 'pyzed' in str(package):
            pyzed_package = package
            break
    
    if pyzed_package:
        print(f"✅ pyzed package found: {pyzed_package}")
    else:
        print("❌ pyzed package not found")
except Exception as e:
    print(f"❌ Error checking packages: {e}")

# Check ZED SDK installation paths
print("\n2. Checking ZED SDK installation...")
zed_paths = [
    r"C:\Program Files (x86)\ZED SDK",
    r"C:\Program Files\ZED SDK"
]

for path in zed_paths:
    if os.path.exists(path):
        print(f"✅ Found ZED SDK at: {path}")
        # List contents
        try:
            contents = os.listdir(path)
            print(f"   Contents: {', '.join(contents[:10])}{'...' if len(contents) > 10 else ''}")
        except Exception as e:
            print(f"   Error listing contents: {e}")
    else:
        print(f"❌ Not found: {path}")

# Check for specific DLL files
print("\n3. Checking for ZED DLL files...")
dll_paths = [
    r"C:\Program Files (x86)\ZED SDK\bin\sl_zed64.dll",
    r"C:\Program Files\ZED SDK\bin\sl_zed64.dll"
]

for dll_path in dll_paths:
    if os.path.exists(dll_path):
        print(f"✅ Found DLL: {dll_path}")
    else:
        print(f"❌ Not found: {dll_path}")

# Check PATH environment variable
print("\n4. Checking PATH environment...")
path_env = os.environ.get('PATH', '')
zed_in_path = False
for path_part in path_env.split(';'):
    if 'ZED SDK' in path_part:
        print(f"✅ ZED in PATH: {path_part}")
        zed_in_path = True

if not zed_in_path:
    print("❌ ZED SDK not found in PATH environment variable")

# Check CUDA installation
print("\n5. Checking CUDA...")
cuda_paths = [
    r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA",
    r"C:\Program Files (x86)\NVIDIA GPU Computing Toolkit\CUDA"
]

for cuda_path in cuda_paths:
    if os.path.exists(cuda_path):
        print(f"✅ Found CUDA at: {cuda_path}")
        try:
            versions = os.listdir(cuda_path)
            print(f"   Versions: {', '.join(versions)}")
        except:
            pass
    else:
        print(f"❌ Not found: {cuda_path}")

# Try importing pyzed with detailed error
print("\n6. Testing pyzed import...")
try:
    import pyzed.sl as sl
    print("✅ pyzed.sl imported successfully!")
    
    # Try creating a camera object
    try:
        camera = sl.Camera()
        print("✅ ZED Camera object created successfully!")
    except Exception as e:
        print(f"❌ Error creating Camera object: {e}")
        
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("\nDetailed error analysis:")
    
    # Check if it's a DLL issue
    if "DLL load failed" in str(e):
        print("   🔍 This is a DLL loading issue")
        print("   Possible causes:")
        print("   - Missing CUDA libraries")
        print("   - ZED SDK bin directory not in PATH")
        print("   - CUDA version mismatch")
        print("   - Missing Visual C++ Redistributables")
    elif "No module named" in str(e):
        print("   🔍 This is a module not found issue")
        print("   - pyzed package not installed")
        print("   - Wrong Python environment")

print("\n" + "=" * 50)
print("Diagnostic complete!")
