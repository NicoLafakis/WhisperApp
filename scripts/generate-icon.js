/**
 * Generate a simple JARVIS icon
 * This creates a basic blue "J" icon for the application
 */

const fs = require('fs');
const path = require('path');

// Create a simple 256x256 PNG with a "J" letter
// This is a minimal implementation - for production, use a proper icon

// ICO file format header for a 256x256 32-bit icon
function createIcoFile() {
  const assetsDir = path.join(__dirname, '..', 'assets');

  // Ensure assets directory exists
  if (!fs.existsSync(assetsDir)) {
    fs.mkdirSync(assetsDir, { recursive: true });
  }

  // Create a simple 16x16 ICO file with JARVIS "J" logo
  // ICO Header (6 bytes)
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);      // Reserved (must be 0)
  header.writeUInt16LE(1, 2);      // Image type (1 = ICO)
  header.writeUInt16LE(1, 4);      // Number of images

  // ICO Directory Entry (16 bytes per image)
  const entry = Buffer.alloc(16);
  entry.writeUInt8(0, 0);           // Width (0 = 256)
  entry.writeUInt8(0, 1);           // Height (0 = 256)
  entry.writeUInt8(0, 2);           // Color palette
  entry.writeUInt8(0, 3);           // Reserved
  entry.writeUInt16LE(1, 4);        // Color planes
  entry.writeUInt16LE(32, 6);       // Bits per pixel

  // Create a simple 32x32 BMP image data (BITMAPINFOHEADER + pixel data)
  const width = 32;
  const height = 32;
  const bitsPerPixel = 32;
  const rowSize = Math.ceil((width * bitsPerPixel) / 32) * 4;
  const pixelDataSize = rowSize * height;

  // BMP Info Header (40 bytes)
  const bmpHeader = Buffer.alloc(40);
  bmpHeader.writeUInt32LE(40, 0);           // Header size
  bmpHeader.writeInt32LE(width, 4);         // Width
  bmpHeader.writeInt32LE(height * 2, 8);    // Height (doubled for ICO)
  bmpHeader.writeUInt16LE(1, 12);           // Planes
  bmpHeader.writeUInt16LE(32, 14);          // Bits per pixel
  bmpHeader.writeUInt32LE(0, 16);           // Compression
  bmpHeader.writeUInt32LE(pixelDataSize, 20); // Image size

  // Create pixel data (BGRA format, bottom-up)
  const pixelData = Buffer.alloc(pixelDataSize);

  // Background color (dark blue/accent)
  const bgR = 10, bgG = 132, bgB = 255, bgA = 255;
  // Text color (white)
  const fgR = 255, fgG = 255, fgB = 255, fgA = 255;

  // Simple "J" pattern for 32x32
  const jPattern = [
    "00000000000000000000000000000000",
    "00000000000000000000000000000000",
    "00000000001111111111100000000000",
    "00000000001111111111100000000000",
    "00000000001111111111100000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00000000000000111100000000000000",
    "00111100000000111100000000000000",
    "00111100000000111100000000000000",
    "00111100000001111100000000000000",
    "00011110000011111000000000000000",
    "00001111111111110000000000000000",
    "00000111111111100000000000000000",
    "00000011111111000000000000000000",
    "00000000000000000000000000000000",
    "00000000000000000000000000000000",
    "00000000000000000000000000000000",
  ];

  // Fill pixel data (bottom-up, BGRA)
  for (let y = 0; y < height; y++) {
    const row = jPattern[height - 1 - y]; // Bottom-up
    for (let x = 0; x < width; x++) {
      const offset = y * rowSize + x * 4;
      if (row && row[x] === '1') {
        // Foreground (white J)
        pixelData[offset] = fgB;
        pixelData[offset + 1] = fgG;
        pixelData[offset + 2] = fgR;
        pixelData[offset + 3] = fgA;
      } else {
        // Background (blue)
        pixelData[offset] = bgB;
        pixelData[offset + 1] = bgG;
        pixelData[offset + 2] = bgR;
        pixelData[offset + 3] = bgA;
      }
    }
  }

  // AND mask (transparency mask) - all zeros for fully opaque
  const andMaskRowSize = Math.ceil(width / 8);
  const andMaskPaddedRowSize = Math.ceil(andMaskRowSize / 4) * 4;
  const andMask = Buffer.alloc(andMaskPaddedRowSize * height);

  const imageData = Buffer.concat([bmpHeader, pixelData, andMask]);

  // Update entry with sizes
  entry.writeUInt8(width, 0);       // Width
  entry.writeUInt8(height, 1);      // Height
  entry.writeUInt32LE(imageData.length, 8);  // Image data size
  entry.writeUInt32LE(6 + 16, 12);  // Offset to image data (header + entry)

  // Combine all parts
  const icoFile = Buffer.concat([header, entry, imageData]);

  const outputPath = path.join(assetsDir, 'icon.ico');
  fs.writeFileSync(outputPath, icoFile);
  console.log(`Icon created at: ${outputPath}`);
  console.log(`Icon size: ${icoFile.length} bytes`);
}

createIcoFile();
