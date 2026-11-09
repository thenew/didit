#!/usr/bin/env python3
"""
Test suite for PNG Quant Preview app.

Tests:
1. pngquant binary exists and is executable
2. pngquant can process an image
3. Built app module can be imported and pngquant can be found

Usage:
    python3 tests/test_pngquant.py
    python3 tests/test_pngquant.py --build  # Also test built app module
"""

import os
import subprocess
import sys
import tempfile
import argparse
import shutil

# Project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PNGQUANT_PATH = os.path.join(PROJECT_ROOT, "pngquant")
TEST_IMAGE = os.path.join(PROJECT_ROOT, "test.png")
BUILD_DIR = os.path.join(PROJECT_ROOT, "dist", "Didit.app")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "test_output")

# Use venv Python if available
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
if os.path.isfile(VENV_PYTHON):
    PYTHON_EXEC = VENV_PYTHON
else:
    PYTHON_EXEC = sys.executable


def test_pngquant_binary_exists():
    """Test that pngquant binary exists and is executable."""
    print("Test 1: Checking pngquant binary...")
    
    if not os.path.isfile(PNGQUANT_PATH):
        print(f"  FAIL: pngquant not found at {PNGQUANT_PATH}")
        return False
    
    if not os.access(PNGQUANT_PATH, os.X_OK):
        print(f"  FAIL: pngquant is not executable at {PNGQUANT_PATH}")
        return False
    
    print(f"  PASS: pngquant binary exists and is executable")
    print(f"        Size: {os.path.getsize(PNGQUANT_PATH)} bytes")
    
    # Test version
    try:
        result = subprocess.run(
            [PNGQUANT_PATH, "--version"],
            capture_output=True,
            timeout=5,
            text=True
        )
        print(f"        Version: {result.stdout.strip()}")
        print("  PASS: pngquant --version works")
        return True
    except Exception as e:
        print(f"  FAIL: Could not get pngquant version: {e}")
        return False


def test_pngquant_processing():
    """Test that pngquant can process a test image."""
    print("\nTest 2: Testing pngquant image processing...")
    
    if not os.path.isfile(TEST_IMAGE):
        print(f"  SKIP: Test image not found at {TEST_IMAGE}")
        return True
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_png = os.path.join(tmpdir, "input.png")
        output_png = os.path.join(tmpdir, "output.png")
        
        # Copy test image to temp dir
        shutil.copy2(TEST_IMAGE, input_png)
        
        # Run pngquant on it
        try:
            result = subprocess.run(
                [PNGQUANT_PATH, "--quality=50-80", "--speed=1", "-f", "--output", output_png, input_png],
                capture_output=True,
                timeout=30,
                text=True
            )
            
            if result.returncode != 0:
                print(f"  FAIL: pngquant returned {result.returncode}")
                print(f"        stderr: {result.stderr}")
                return False
            
            if not os.path.isfile(output_png):
                print(f"  FAIL: Output file not created")
                return False
            
            # Verify output is a valid PNG by checking magic bytes
            with open(output_png, 'rb') as f:
                header = f.read(8)
            
            # PNG magic bytes: \x89PNG\r\n\x1a\n
            if header[:4] != b'\x89PNG':
                print(f"  FAIL: Output file is not a valid PNG (magic bytes mismatch)")
                print(f"        Header: {header}")
                return False
            
            input_size = os.path.getsize(input_png)
            output_size = os.path.getsize(output_png)
            
            # For most images, pngquant should reduce size (unless already highly optimized)
            if output_size > input_size * 2:
                print(f"  WARN: Output file is much larger than input ({output_size} > {input_size})")
            
            ratio = (output_size / input_size) * 100
            
            print(f"  PASS: pngquant processed image successfully")
            print(f"        Input:  {input_size:,} bytes")
            print(f"        Output: {output_size:,} bytes ({ratio:.1f}%)")
            print(f"        Valid PNG: Yes (magic bytes verified)")
            return True
            
        except subprocess.TimeoutExpired:
            print(f"  FAIL: pngquant timed out")
            return False
        except Exception as e:
            print(f"  FAIL: Exception: {e}")
            return False


def test_app_module():
    """Test that the app module can be imported and finds pngquant."""
    print("\nTest 3: Testing app module...")
    
    # Use venv python to ensure dependencies are available
    test_script = f"""
import sys
import os
sys.path.insert(0, '{PROJECT_ROOT}')
os.chdir('{PROJECT_ROOT}')

# Test import
try:
    import pngquant_preview_app
    print("PASS: Module imports successfully")
except Exception as e:
    print(f"FAIL: Import error: {{e}}")
    sys.exit(1)

# Test pngquant detection
from pngquant_preview_app import find_pngquant
path = find_pngquant('{PNGQUANT_PATH}')
if path and os.path.isfile(path):
    print(f"PASS: pngquant found at {{path}}")
else:
    print("FAIL: pngquant not found")
    sys.exit(1)

print("PASS: App module test passed")
"""
    
    try:
        result = subprocess.run(
            [PYTHON_EXEC, "-c", test_script],
            capture_output=True,
            timeout=10,
            text=True
        )
        
        if result.returncode != 0:
            print(f"  FAIL: App module test failed")
            print(f"        stdout: {result.stdout}")
            print(f"        stderr: {result.stderr}")
            return False
        
        print(f"  {result.stdout.strip()}")
        return True
        
    except Exception as e:
        print(f"  FAIL: App test exception: {e}")
        return False


def test_app_processing():
    """Test the app's actual image processing pipeline.
    
    This simulates what the app does:
    1. Convert input to PNG (using sips)
    2. Run pngquant with different color settings
    3. Save output files that user can manually verify
    """
    print("\nTest 3: Testing app image processing pipeline...")
    
    if not os.path.isfile(TEST_IMAGE):
        print(f"  SKIP: Test image not found at {TEST_IMAGE}")
        return True
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"  Output files will be saved to: {OUTPUT_DIR}")
    
    # Use macOS sips to convert to PNG (what the app does)
    SIPS = "/usr/bin/sips"
    if not os.path.isfile(SIPS):
        print("  SKIP: sips not available (macOS only)")
        return True
    
    # Step 1: Convert to PNG
    temp_png = os.path.join(OUTPUT_DIR, "temp_input.png")
    try:
        result = subprocess.run(
            [SIPS, "-s", "format", "png", TEST_IMAGE, "--out", temp_png],
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0 or not os.path.isfile(temp_png):
            print(f"  WARN: sips conversion failed, using original image")
            temp_png = TEST_IMAGE
    except Exception as e:
        print(f"  WARN: sips failed: {e}, using original image")
        temp_png = TEST_IMAGE
    
    # Step 2: Run pngquant with various color settings (like the app does)
    test_colors = [2, 8, 16, 32, 64]
    
    for colors in test_colors:
        output_file = os.path.join(OUTPUT_DIR, f"test_{colors}_colors.png")
        
        try:
            result = subprocess.run(
                [PNGQUANT_PATH, "-v", str(colors), "-f", "--output", output_file, temp_png],
                capture_output=True,
                timeout=30,
                text=True
            )
            
            if result.returncode != 0:
                print(f"  FAIL: pngquant failed for {colors} colors")
                print(f"        stderr: {result.stderr}")
                return False
            
            if not os.path.isfile(output_file):
                print(f"  FAIL: Output file not created for {colors} colors")
                return False
            
            # Verify it's a valid PNG
            with open(output_file, 'rb') as f:
                header = f.read(8)
            if header[:4] != b'\x89PNG':
                print(f"  FAIL: Output for {colors} colors is not a valid PNG")
                return False
            
            size = os.path.getsize(output_file)
            print(f"  PASS: {colors} colors -> {size:,} bytes ({output_file})")
            
        except subprocess.TimeoutExpired:
            print(f"  FAIL: pngquant timed out for {colors} colors")
            return False
        except Exception as e:
            print(f"  FAIL: Exception for {colors} colors: {e}")
            return False
    
    print(f"\n  SUCCESS: All test files created in {OUTPUT_DIR}")
    print(f"  You can manually verify these files are valid images.")
    return True


def test_app_build():
    """Test that the app can be built."""
    print("\nTest 3: Testing app build...")
    
    # Check if app is already built
    if os.path.isdir(BUILD_DIR):
        print(f"  INFO: App already built at {BUILD_DIR}")
    else:
        # Build the app
        print("  Building app with py2app...")
        try:
            result = subprocess.run(
                [sys.executable, "setup.py", "py2app", "-A"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                timeout=120,
                text=True
            )
            
            if result.returncode != 0:
                print(f"  FAIL: Build failed with code {result.returncode}")
                print(f"        stdout: {result.stdout}")
                print(f"        stderr: {result.stderr}")
                return False
            
            print("  PASS: App built successfully")
            
        except subprocess.TimeoutExpired:
            print(f"  FAIL: Build timed out")
            return False
        except Exception as e:
            print(f"  FAIL: Build exception: {e}")
            return False
    
    # Verify the built app structure
    macos_dir = os.path.join(BUILD_DIR, "Contents", "MacOS")
    if not os.path.isdir(macos_dir):
        print(f"  FAIL: MacOS directory not found in built app")
        return False
    
    # Find the executable
    executables = [f for f in os.listdir(macos_dir) if os.path.isfile(os.path.join(macos_dir, f))]
    app_exe = None
    for exe in executables:
        if exe.startswith("Didit") or exe.startswith("pngquant"):
            app_exe = exe
            break
    
    if not app_exe:
        print(f"  FAIL: Executable not found in {macos_dir}")
        print(f"        Available files: {executables}")
        return False
    
    print(f"  PASS: Built app verified (executable: {app_exe})")
    
    # Now test the module
    return test_app_module()


def main():
    parser = argparse.ArgumentParser(description="Test PNG Quant Preview app")
    parser.add_argument("--build", action="store_true", help="Test built app")
    parser.add_argument("--generate", "-g", action="store_true", 
                        help="Generate actual output files for manual verification")
    args = parser.parse_args()
    
    print("=" * 60)
    print("PNG Quant Preview - Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test 1: pngquant binary
    results.append(("pngquant binary", test_pngquant_binary_exists()))
    
    # Test 2: pngquant processing
    results.append(("pngquant processing", test_pngquant_processing()))
    
    # Test 3: App processing (generates files) or module/ build test
    if args.generate:
        results.append(("app processing (generates files)", test_app_processing()))
    elif args.build:
        results.append(("app build", test_app_build()))
    else:
        results.append(("app module", test_app_module()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        if result:
            passed += 1
            print(f"  PASS: {name}")
        else:
            failed += 1
            print(f"  FAIL: {name}")
    
    print(f"\nResults: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("\nSome tests FAILED!")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
