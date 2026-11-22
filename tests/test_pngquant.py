#!/usr/bin/env python3
"""
Test suite for Didit app.

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
    import didit
    print("PASS: Module imports successfully")
except Exception as e:
    print(f"FAIL: Import error: {{e}}")
    sys.exit(1)

# Without --pngquant the app must pick the binary shipped in the project
# folder, not a Homebrew/PATH one.
from didit import find_pngquant
path = find_pngquant()
if path and os.path.realpath(path) == os.path.realpath('{PNGQUANT_PATH}'):
    print(f"PASS: uses project pngquant at {{path}}")
else:
    print(f"FAIL: expected {PNGQUANT_PATH}, got {{path}}")
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


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def decode_png(data):
    """Strictly decode a non-interlaced 8-bit-or-less PNG with the stdlib.

    Returns (width, height, palette_len, rows of (r, g, b) tuples). Raises
    ValueError on anything malformed: missing/misplaced signature, bad CRC,
    trailing bytes, wrong IDAT size. This is what catches pngquant output
    polluted by log text, which a magic-bytes check at offset 0 misses when
    the log is prepended (or passes when the file was written via --output).
    """
    import struct
    import zlib

    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"no PNG signature at offset 0 (starts with {data[:16]!r})")
    pos, chunks = 8, []
    while pos < len(data):
        if pos + 8 > len(data):
            raise ValueError("truncated chunk header")
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        if zlib.crc32(ctype + body) != crc:
            raise ValueError(f"bad CRC in {ctype!r} chunk")
        chunks.append((ctype, body))
        pos += 12 + length
        if ctype == b"IEND":
            break
    if pos != len(data):
        raise ValueError(f"{len(data) - pos} trailing bytes after IEND")
    if not chunks or chunks[0][0] != b"IHDR" or chunks[-1][0] != b"IEND":
        raise ValueError("IHDR must be first and IEND last")

    w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
    if interlace or depth > 8:
        raise ValueError(f"unsupported PNG (depth={depth}, interlace={interlace})")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    plte = b"".join(b for t, b in chunks if t == b"PLTE")
    palette = [tuple(plte[i:i + 3]) for i in range(0, len(plte), 3)]
    raw = zlib.decompress(b"".join(b for t, b in chunks if t == b"IDAT"))
    stride = (w * channels * depth + 7) // 8
    if len(raw) != h * (stride + 1):
        raise ValueError(f"IDAT is {len(raw)} bytes, expected {h * (stride + 1)}")

    bpp = max(1, channels * depth // 8)
    prev, rows = bytearray(stride), []
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
            elif f != 0:
                raise ValueError(f"bad filter type {f}")
        prev = line
        if depth < 8:
            per = 8 // depth
            vals = [(line[x // per] >> (8 - depth * (x % per + 1))) & ((1 << depth) - 1) for x in range(w)]
        else:
            vals = list(line)
        if ctype == 3:
            rows.append([palette[v] for v in vals])
        elif ctype in (0, 4):
            rows.append([(v, v, v) for v in vals[::channels]])
        else:
            rows.append([tuple(vals[x * channels:x * channels + 3]) for x in range(w)])
    return w, h, len(palette), rows


def candidate_pngquants():
    """Every pngquant the app could end up using, not just the project one.

    The app's find_pngquant() falls back to Homebrew/PATH, and pngquant 2.x and
    3.x behave differently, so the endpoint must be tested against each.
    """
    seen, out = set(), []
    for c in [PNGQUANT_PATH, "/opt/homebrew/bin/pngquant", "/usr/local/bin/pngquant",
              shutil.which("pngquant")]:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            real = os.path.realpath(c)
            if real not in seen:
                seen.add(real)
                out.append(c)
    return out


def test_app_quantize_endpoint():
    """Run the app's real /prepare -> /quantize HTTP handlers and decode the result.

    Fails if the bytes the UI receives are not a clean PNG, have more colors
    than requested, the wrong size, or pixels far from the source.
    """
    print("\nTest 4: Testing app /quantize endpoint output...")

    src_path = TEST_IMAGE
    if not os.path.isfile(src_path):
        print("  SKIP: no test image")
        return True

    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer

    sys.path.insert(0, PROJECT_ROOT)
    try:
        import didit as app
    except Exception as e:
        print(f"  FAIL: cannot import app: {e}")
        return False

    server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def post(path, body):
        req = urllib.request.Request(base + path, data=body, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()

    ok = True
    try:
        with open(src_path, "rb") as fh:
            original = fh.read()
        ext = os.path.splitext(src_path)[1].lstrip(".")
        # Small width keeps the pure-Python decode fast.
        prepared = post(f"/prepare?width=200&ext={ext}", original)
        sw, sh, _, src_rows = decode_png(prepared)

        binaries = candidate_pngquants()
        if not binaries:
            print("  FAIL: no pngquant binary found")
            return False
        for binary in binaries:
            app.PNGQUANT = binary
            version = subprocess.run([binary, "--version"], capture_output=True, text=True).stdout.strip()
            for colors, nofs, max_err in [(2, 0, 80), (8, 0, 30), (64, 0, 12), (64, 1, 12)]:
                label = f"{binary} ({version}) colors={colors} nofs={nofs}"
                try:
                    out = post(f"/quantize?colors={colors}&nofs={nofs}", prepared)
                    w, h, plte, rows = decode_png(out)
                except Exception as e:
                    print(f"  FAIL: {label}: {e}")
                    ok = False
                    continue
                if (w, h) != (sw, sh):
                    print(f"  FAIL: {label}: size {w}x{h}, expected {sw}x{sh}")
                    ok = False
                    continue
                if plte == 0 or plte > colors:
                    print(f"  FAIL: {label}: palette has {plte} colors, requested {colors}")
                    ok = False
                    continue
                total = sum(abs(a - b) for r1, r2 in zip(src_rows, rows)
                            for p1, p2 in zip(r1, r2) for a, b in zip(p1, p2))
                err = total / (w * h * 3)
                if err > max_err:
                    print(f"  FAIL: {label}: mean pixel error {err:.1f} > {max_err}")
                    ok = False
                    continue
                print(f"  PASS: {label}: {len(out):,} bytes, {plte} colors, mean err {err:.1f}")
    except Exception as e:
        print(f"  FAIL: endpoint exception: {e}")
        ok = False
    finally:
        server.shutdown()
    return ok


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
    """Build the app with PyInstaller and check it ships the project's pngquant."""
    print("\nTest 3: Testing app build...")
    print("  Building app with PyInstaller...")
    try:
        result = subprocess.run(
            [PYTHON_EXEC, "-m", "PyInstaller", "--noconfirm", "Didit.spec"],
            cwd=PROJECT_ROOT, capture_output=True, timeout=600, text=True,
        )
    except Exception as e:
        print(f"  FAIL: Build exception: {e}")
        return False
    if result.returncode != 0:
        print(f"  FAIL: Build failed with code {result.returncode}")
        print(f"        stderr: {result.stderr[-2000:]}")
        return False
    print("  PASS: App built successfully")

    exe = os.path.join(BUILD_DIR, "Contents", "MacOS", "Didit")
    if not os.access(exe, os.X_OK):
        print(f"  FAIL: executable not found at {exe}")
        return False

    bundled = [os.path.join(root, "pngquant") for root, _, names in os.walk(BUILD_DIR)
               if "pngquant" in names]
    if not bundled:
        print("  FAIL: pngquant is not bundled in the app")
        return False
    # PyInstaller re-signs binaries on macOS, so compare behaviour, not bytes.
    def version(path):
        return subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5).stdout.strip()
    try:
        got, want = version(bundled[0]), version(PNGQUANT_PATH)
    except Exception as e:
        print(f"  FAIL: bundled pngquant does not run: {e}")
        return False
    if got != want:
        print(f"  FAIL: bundled pngquant is {got!r}, project one is {want!r}")
        return False
    print(f"  PASS: app bundles the project pngquant ({os.path.relpath(bundled[0], BUILD_DIR)})")

    return test_app_module()


def main():
    parser = argparse.ArgumentParser(description="Test Didit app")
    parser.add_argument("--build", action="store_true", help="Test built app")
    parser.add_argument("--generate", "-g", action="store_true", 
                        help="Generate actual output files for manual verification")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Didit - Test Suite")
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

    # Test 4: the bytes the UI actually receives from /quantize
    results.append(("app /quantize output", test_app_quantize_endpoint()))

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
