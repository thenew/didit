# Didit

A native macOS desktop application for previewing PNG image compression using [pngquant](https://pngquant.org/). It provides a visual interface to see how different color quantization settings affect your images before saving them.

Didit allows you to drag & drop multiple images, preview different compression levels, and download optimized versions.

## Features

- **Multi-file support**: Drag & drop or open multiple images at once
- Preview 10 different color quantization levels per file
- Adjustable color count (2-247 colors)
- Resize images by width while maintaining aspect ratio (default: 1200px)
- Toggle dithering on/off
- Toggle pixelated rendering
- Real-time preview updates
- Save individual optimized versions with one click
- **Bulk download**: Select multiple output files and download them all at once
- **Zoom mode**: Toggle between 100% size and fit-to-grid view

## Screenshots

The app displays your source image alongside 10 preview thumbnails showing different compression levels. Each preview shows the file size reduction and can be clicked to save that version.

## Requirements

- macOS (tested on recent versions)
- Python 3.7+
- [pngquant](https://pngquant.org/) binary
- Required Python packages: `webview`, `py2app` (for building)

## Installation

### 1. Install Dependencies

```bash
# Install Python packages
pip install webview py2app

# Install pngquant
# Option A: Using Homebrew
brew install pngquant

# Option B: Manual download
# Download from https://pngquant.org/ and place the binary in the project folder
```

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
3. (Optional) Test that the app can be built and the module loads correctly
4. (Optional) **Generate actual output PNG files** in `test_output/` that you can manually verify

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
python3 pngquant_preview_app.py

# Or specify a custom pngquant path
python3 pngquant_preview_app.py --pngquant /path/to/pngquant
```

### Building the Standalone App

#### Using py2app (Recommended)

```bash
# Standard build
python3 setup.py py2app

# Fast build for testing (alias mode - no code copying)
python3 setup.py py2app -A
```

The built application will be created in the `dist/` directory as `Didit.app`.

#### Using PyInstaller

Alternatively, you can use PyInstaller:

```bash
pyinstaller --windowed --icon=icon.icns --add-data pngquant:. Didit.spec
```

Note: The `Didit.spec` file is already configured for PyInstaller.

## Project Structure

```
.
├── pngquant_preview_app.py    # Main application code
├── setup.py                   # py2app build configuration
├── Didit.spec                 # PyInstaller build configuration
├── icon.icns                  # Application icon (macOS)
├── icon.iconset/              # Icon source files
├── icon.png                   # Icon in PNG format
├── pngquant                   # pngquant binary (should be here for building)
├── pq_libs/                   # Supporting libraries for pngquant
├── tests/                     # Test suite
│   ├── test_pngquant.py       # Automated tests
│   └── run_tests.sh           # Convenience test runner
├── build/                     # Build artifacts (generated)
├── dist/                      # Built application (generated)
├── w/                         # Test/work images
└── test.png                   # Test image
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

Edit the `PAGE` HTML template in `pngquant_preview_app.py` and modify the JavaScript to generate more preview thumbnails.

### Changing Default Settings

Modify the default values in the HTML form (in the `PAGE` variable):
- Default colors: Change the `value` attribute of `#s` input
- Default width: Change the `placeholder` of `#w` input
- Default dither/nofs: Modify the `checked` state of `#nd` checkbox

## Troubleshooting

### pngquant not found

If you get an error that pngquant is not found:
- Ensure pngquant is installed and in your PATH
- Or place the pngquant binary in the project directory
- Or run with `--pngquant /path/to/pngquant`

### Build errors

- Make sure all dependencies are installed
- For py2app: `pip install py2app`
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
- [py2app](https://py2app.readthedocs.io/) - For building macOS applications
