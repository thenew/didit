# Didit

A native macOS desktop application for previewing PNG image compression using [pngquant](https://pngquant.org/). It provides a visual interface to see how different color quantization settings affect your images before saving them.

Didit allows you to drag & drop multiple images, preview different compression levels, and download optimized versions.

## Features

- **Multi-file support**: Drag & drop or open multiple images at once
- Preview 4 color quantization levels per file
- Color count slider (2–256 colors, 4 consecutive previews)
- Resize images by width while maintaining aspect ratio (default: 1200px)
- Toggle dithering on/off
- Real-time preview updates
- Save individual optimized versions with one click
- **Bulk download**: Select multiple output files and download them all at once
- **Zoom mode**: Toggle between 100% (natural) size and fit-to-grid view

## Screenshots

The app displays your source image alongside 10 preview thumbnails showing different compression levels. Each preview shows the file size reduction and can be clicked to save that version.

## Requirements

- macOS (tested on recent versions)
- Python 3.7+
- The `pngquant` binary in the project folder (shipped with the repo, bundled into the app)
- Required Python packages: `pywebview`, `pyinstaller` (for building)

## Installation

### 1. Install Dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install pywebview pyinstaller
```

The app always uses the `pngquant` binary in the project folder (or the copy bundled inside `Didit.app`). A Homebrew/PATH pngquant is only used as a fallback if that binary is missing.

## Running the Tests

Before running the app, verify everything works:

```bash
# Run all basic tests (pngquant binary and processing)
python3 tests/test_pngquant.py

# Run all tests including app build test
python3 tests/test_pngquant.py --build

# Generate actual output files for manual verification
python3 tests/test_pngquant.py --generate

# Run all tests with file generation
python3 tests/test_pngquant.py --build --generate

# Or use the convenience script
./tests/run_tests.sh
./tests/run_tests.sh --build
./tests/run_tests.sh --generate
```

The tests will:

1. Verify the pngquant binary exists and is executable
2. Test that pngquant can process the test image
3. Check the app picks the project's pngquant (with `--build`: build with PyInstaller and check the app bundles it)
4. Run the app's real `/prepare` → `/quantize` endpoints against every pngquant found (project, Homebrew, PATH) and fully decode the returned PNGs (structure, palette size, pixel accuracy)
5. (Optional, `--generate`) **Generate actual output PNG files** in `test_output/` that you can manually verify

**Generated files:**

- `test_output/test_2_colors.png` - 2 color palette
- `test_output/test_8_colors.png` - 8 color palette
- `test_output/test_16_colors.png` - 16 color palette
- `test_output/test_32_colors.png` - 32 color palette
- `test_output/test_64_colors.png` - 64 color palette

## Running the App

### Development Mode

For quick testing during development:

```bash
# Run directly with Python
python3 didit.py
```

### Building the Standalone App

```bash
.venv/bin/pyinstaller --noconfirm Didit.spec
```

The app is created at `dist/Didit.app`. `Didit.spec` bundles the `pngquant` binary from the project folder, and the build stops if it is missing.

## Project Structure

```
.
├── didit.py                   # Main application code
├── Didit.spec                 # PyInstaller build configuration
├── icon.icns                  # Application icon (macOS)
├── pngquant                   # pngquant binary, bundled into the app
├── tests/                     # Test suite
│   ├── test_pngquant.py       # Automated tests
│   └── run_tests.sh           # Convenience test runner
└── test.png                   # Test image (not committed)
```

## How It Works

The application:

1. Launches a local HTTP server to handle image processing
2. Opens a native macOS window using the `webview` library
3. Allows you to drag & drop or open an image
4. Converts the image to PNG using macOS's built-in `sips` tool
5. Runs `pngquant` with different color settings to generate previews
6. Displays all previews with their file sizes
7. Lets you click any preview to save that version

## Customization

### Adding More Preview Levels

Edit the `PAGE` HTML template in `didit.py` and modify the JavaScript to generate more preview thumbnails.

### Changing Default Settings

Modify the default values in the HTML form (in the `PAGE` variable):

- Default colors: Change the `value` attribute of `#s` input
- Default width: Change the `placeholder` of `#w` input
- Default dither/nofs: Modify the `checked` state of `#nd` checkbox

## Troubleshooting

### pngquant not found

If you get an error that pngquant is not found:

- Make sure the `pngquant` binary is in the project folder and executable (`chmod +x pngquant`)
- Or run with `--pngquant /path/to/pngquant`

### Build errors

- Make sure all dependencies are installed
- `.venv/bin/pip install pyinstaller`
- For macOS: Ensure you have Xcode command line tools installed

### Image processing errors

The app uses macOS's built-in `sips` tool for format conversion. If you have issues:

- Ensure you're running on macOS
- Check that the input file is a valid image

## License

This project is provided as-is. The pngquant binary has its own license (see https://pngquant.org/).

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Acknowledgments

- [pngquant](https://pngquant.org/) - The excellent PNG compression tool
- [pywebview](https://pywebview.flowrl.com/) - For the native window embedding
- [PyInstaller](https://pyinstaller.org/) - For building the macOS app
